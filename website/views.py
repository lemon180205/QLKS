import json
import logging
import uuid

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from rooms.availability import get_available_room_count
from rooms.models import BookingPayment, BookingRequest, RoomType, Service

from .forms import BookingRequestForm, RoomSearchForm
from .notifications import send_booking_email
from .payments import (
    MomoConfigurationError,
    MomoGatewayError,
    create_momo_payment,
    verify_momo_signature,
)

logger = logging.getLogger(__name__)


def room_list(request):
    search_form = RoomSearchForm(request.GET if request.GET else None)
    room_types = RoomType.objects.annotate(room_count=Count("rooms"))
    available_counts = {}
    has_availability_search = False

    if search_form.is_valid():
        check_in = search_form.cleaned_data.get("check_in")
        check_out = search_form.cleaned_data.get("check_out")
        guest_count = search_form.cleaned_data.get("guest_count")
        if guest_count:
            room_types = room_types.filter(capacity__gte=guest_count)
        if check_in and check_out:
            has_availability_search = True
            available_counts = {
                room_type.pk: get_available_room_count(
                    room_type,
                    check_in,
                    check_out,
                )
                for room_type in room_types
            }
            room_types = room_types.filter(
                pk__in=[
                    room_type_id
                    for room_type_id, available_count in available_counts.items()
                    if available_count
                ]
            )

    room_cards = [
        (room_type, available_counts.get(room_type.pk))
        for room_type in room_types
    ]

    return render(
        request,
        "website/room_list.html",
        {
            "room_cards": room_cards,
            "search_form": search_form,
            "available_counts": available_counts,
            "has_availability_search": has_availability_search,
            "services": Service.objects.filter(is_available=True),
        },
    )


def room_detail(request, pk):
    room_type = get_object_or_404(RoomType, pk=pk)

    return render(
        request,
        "website/room_detail.html",
        {"room_type": room_type},
    )


@login_required
def booking_request(request, pk):
    room_type = get_object_or_404(RoomType, pk=pk)
    initial = {
        key: request.GET[key]
        for key in ("check_in", "check_out", "guest_count")
        if key in request.GET
    }
    initial.setdefault(
        "guest_name",
        request.user.get_full_name() or request.user.get_username(),
    )
    initial.setdefault("email", request.user.email)
    initial.setdefault("phone", request.user.phone)
    form = BookingRequestForm(
        request.POST if request.method == "POST" else None,
        room_type=room_type,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        booking = None
        with transaction.atomic():
            room_type = RoomType.objects.select_for_update().get(pk=room_type.pk)
            if get_available_room_count(
                room_type,
                form.cleaned_data["check_in"],
                form.cleaned_data["check_out"],
            ) < 1:
                form.add_error(
                    None,
                    "Phòng vừa hết chỗ trong khoảng ngày đã chọn. Vui lòng chọn ngày khác.",
                )
            else:
                form.room_type = room_type
                booking = form.save(commit=False)
                booking.customer = request.user
                booking.channel = BookingRequest.Channel.WEBSITE
                booking.save()
        if booking:
            email_sent = send_booking_email(
                booking,
                "Khách sạn đã nhận yêu cầu đặt phòng",
                (
                    f"Xin chào {booking.guest_name},\n\n"
                    "Khách sạn đã nhận yêu cầu đặt phòng của bạn.\n"
                    f"Mã đặt phòng: {booking.reference_code}\n"
                    f"Loại phòng: {booking.room_type}\n"
                    f"Thời gian: {booking.check_in} - {booking.check_out}\n"
                    f"Tổng dự kiến: {booking.total_price:,.0f} VNĐ\n\n"
                    "Yêu cầu sẽ được xác nhận sau khi thanh toán thành công "
                    "hoặc được lễ tân xác nhận."
                ),
            )
            messages.success(
                request,
                (
                    f"Đã tạo yêu cầu đặt phòng {booking.reference_code}. "
                    "Bạn có thể theo dõi tại mục Đặt phòng của tôi."
                ),
            )
            if not email_sent:
                messages.warning(
                    request,
                    "Yêu cầu đã được lưu nhưng email chưa gửi được. "
                    "Vui lòng kiểm tra cấu hình SMTP hoặc liên hệ lễ tân.",
                )
            return redirect("accounts:bookings")

    return render(
        request,
        "website/booking_request.html",
        {"room_type": room_type, "form": form},
    )


@login_required
@require_POST
def initiate_momo_payment(request, pk):
    with transaction.atomic():
        booking = get_object_or_404(
            BookingRequest.objects.select_for_update(),
            pk=pk,
            customer=request.user,
        )
        if booking.status not in (
            BookingRequest.Status.PENDING,
            BookingRequest.Status.CONFIRMED,
        ):
            messages.error(request, "Yêu cầu này không thể thanh toán.")
            return redirect("accounts:bookings")
        if booking.payment_status == BookingRequest.PaymentStatus.PAID:
            messages.info(request, "Yêu cầu này đã được thanh toán.")
            return redirect("accounts:bookings")

        pending_payment = booking.payment_attempts.filter(
            status=BookingPayment.Status.PENDING
        ).first()
        if pending_payment and pending_payment.pay_url:
            return redirect(pending_payment.pay_url)
        if pending_payment:
            messages.info(
                request,
                "Giao dịch đang được khởi tạo. Vui lòng thử lại sau ít phút.",
            )
            return redirect("accounts:bookings")

        payment = BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
        )
        booking.payment_status = BookingRequest.PaymentStatus.PENDING
        booking.save(update_fields=("payment_status",))

    try:
        pay_url = create_momo_payment(payment)
    except (MomoConfigurationError, MomoGatewayError) as exc:
        with transaction.atomic():
            payment = BookingPayment.objects.select_for_update().get(pk=payment.pk)
            payment.status = BookingPayment.Status.FAILED
            payment.save(update_fields=("status",))
            booking = BookingRequest.objects.select_for_update().get(
                pk=payment.booking_id
            )
            if booking.payment_status == BookingRequest.PaymentStatus.PENDING:
                booking.payment_status = BookingRequest.PaymentStatus.FAILED
                booking.save(update_fields=("payment_status",))
        logger.warning("MoMo payment setup failed for booking %s: %s", pk, exc)
        messages.error(request, str(exc))
        return redirect("accounts:bookings")

    payment.pay_url = pay_url
    payment.save(update_fields=("pay_url",))
    return redirect(pay_url)


@login_required
def momo_return(request):
    try:
        order_id = uuid.UUID(request.GET.get("orderId", ""))
    except ValueError:
        return render(
            request,
            "website/payment_result.html",
            {"payment": None},
            status=400,
        )
    payment = get_object_or_404(
        BookingPayment.objects.select_related("booking", "booking__room_type"),
        order_id=order_id,
        booking__customer=request.user,
    )
    return render(
        request,
        "website/payment_result.html",
        {"payment": payment},
    )


@csrf_exempt
@require_POST
def momo_ipn(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"resultCode": 1, "message": "Invalid JSON"},
            status=400,
        )
    if not isinstance(payload, dict) or not verify_momo_signature(payload):
        logger.warning("Rejected MoMo IPN with an invalid signature.")
        return JsonResponse(
            {"resultCode": 1, "message": "Invalid signature"},
            status=400,
        )
    try:
        order_id = uuid.UUID(str(payload.get("orderId", "")))
        result_code = int(payload.get("resultCode"))
        amount = int(payload.get("amount"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"resultCode": 1, "message": "Invalid transaction data"},
            status=400,
        )
    if payload.get("partnerCode") != settings.MOMO_PARTNER_CODE:
        return JsonResponse(
            {"resultCode": 1, "message": "Invalid partner"},
            status=400,
        )

    send_payment_email = False
    with transaction.atomic():
        payment = (
            BookingPayment.objects.select_for_update()
            .select_related("booking")
            .filter(order_id=order_id)
            .first()
        )
        if (
            payment is None
            or str(payment.request_id) != str(payload.get("requestId"))
            or amount != int(payment.amount)
        ):
            logger.warning("Rejected MoMo IPN for unknown or mismatched order.")
            return JsonResponse(
                {"resultCode": 1, "message": "Transaction mismatch"},
                status=400,
            )
        if payment.status == BookingPayment.Status.PAID:
            return JsonResponse(
                {
                    "partnerCode": settings.MOMO_PARTNER_CODE,
                    "orderId": str(payment.order_id),
                    "requestId": str(payment.request_id),
                    "resultCode": 0,
                    "message": "Success",
                }
            )

        booking = BookingRequest.objects.select_for_update().get(
            pk=payment.booking_id
        )
        if result_code == 0:
            payment.status = BookingPayment.Status.PAID
            payment.transaction_id = str(payload.get("transId", ""))
            payment.paid_at = timezone.now()
            booking.payment_status = BookingRequest.PaymentStatus.PAID
            if booking.status in (
                BookingRequest.Status.PENDING,
                BookingRequest.Status.CONFIRMED,
            ):
                booking.status = BookingRequest.Status.CONFIRMED
            elif booking.status == BookingRequest.Status.CANCELLED:
                logger.error(
                    "Payment succeeded after booking %s was cancelled; "
                    "manual refund review is required.",
                    booking.reference_code,
                )
            send_payment_email = True
        else:
            payment.status = BookingPayment.Status.FAILED
            if booking.payment_status == BookingRequest.PaymentStatus.PENDING:
                booking.payment_status = BookingRequest.PaymentStatus.FAILED
        payment.save(
            update_fields=("status", "transaction_id", "paid_at")
        )
        booking.save(update_fields=("payment_status", "status"))

    if send_payment_email:
        send_booking_email(
            booking,
            "Thanh toán đặt phòng thành công",
            (
                f"Xin chào {booking.guest_name},\n\n"
                f"Khách sạn đã nhận thanh toán cho mã đặt phòng "
                f"{booking.reference_code}.\n"
                f"Tổng tiền: {payment.amount:,.0f} VNĐ."
            ),
        )

    return JsonResponse(
        {
            "partnerCode": settings.MOMO_PARTNER_CODE,
            "orderId": str(payment.order_id),
            "requestId": str(payment.request_id),
            "resultCode": 0,
            "message": "Success",
        }
    )