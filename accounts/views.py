from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from rooms.models import BookingRequest

from .forms import CustomerRegistrationForm
from website.notifications import send_booking_email


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:bookings")

    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Tài khoản của bạn đã được tạo.")
        return redirect("accounts:bookings")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def bookings(request):
    reservations = BookingRequest.objects.filter(
        customer=request.user
    ).select_related("room_type").prefetch_related("payment_attempts")
    return render(
        request,
        "accounts/bookings.html",
        {"bookings": reservations},
    )


@login_required
@require_POST
def cancel_booking(request, pk):
    with transaction.atomic():
        booking = get_object_or_404(
            BookingRequest.objects.select_for_update(),
            pk=pk,
            customer=request.user,
        )
        can_cancel = (
            booking.status
            in (
                BookingRequest.Status.PENDING,
                BookingRequest.Status.CONFIRMED,
            )
            and booking.payment_status
            not in (
                BookingRequest.PaymentStatus.PENDING,
                BookingRequest.PaymentStatus.PAID,
            )
        )
        if can_cancel:
            booking.status = BookingRequest.Status.CANCELLED
            booking.save(update_fields=("status",))

    if not can_cancel:
        messages.error(
            request,
            "Không thể hủy yêu cầu này trực tuyến khi giao dịch đang xử lý "
            "hoặc đã thanh toán. Vui lòng liên hệ lễ tân.",
        )
    else:
        messages.success(request, "Yêu cầu đặt phòng đã được hủy.")
        if not send_booking_email(
            booking,
            "Yêu cầu đặt phòng đã được hủy",
            (
                f"Xin chào {booking.guest_name},\n\n"
                f"Yêu cầu đặt phòng {booking.reference_code} đã được hủy."
            ),
        ):
            messages.warning(
                request,
                "Yêu cầu đã được hủy nhưng email chưa gửi được.",
            )
    return redirect("accounts:bookings")
