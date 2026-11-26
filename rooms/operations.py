from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from .availability import get_reserving_bookings
from .models import (
    BookingCounterPayment,
    BookingPayment,
    BookingRequest,
    Room,
)


@transaction.atomic
def check_in_booking(booking_id):
    booking = BookingRequest.objects.select_for_update().get(
        pk=booking_id
    )

    if booking.status != BookingRequest.Status.CONFIRMED:
        raise ValidationError(
            "Chỉ nhận phòng cho đơn đã được xác nhận."
        )

    if not booking.assigned_room_id:
        raise ValidationError(
            "Vui lòng gán phòng trước khi check-in."
        )

    today = timezone.localdate()

    if not booking.check_in <= today < booking.check_out:
        raise ValidationError(
            "Hôm nay không nằm trong thời gian lưu trú. "
            "Hãy kiểm tra lại lịch đặt phòng."
        )

    room = Room.objects.select_for_update().get(
        pk=booking.assigned_room_id
    )

    if room.room_type_id != booking.room_type_id:
        raise ValidationError(
            "Phòng được gán không đúng loại phòng đã đặt."
        )

    if room.status != Room.Status.READY:
        raise ValidationError(
            "Phòng chưa sẵn sàng: đang dọn hoặc bảo trì."
        )

    # Khách ở quá ngày trả dự kiến vẫn được coi là đang chiếm phòng.
    occupied = BookingRequest.objects.filter(
        assigned_room=room,
        status=BookingRequest.Status.CHECKED_IN,
    ).exclude(pk=booking.pk)

    if occupied.exists():
        raise ValidationError(
            "Phòng này đang có khách chưa check-out."
        )

    overlapping = get_reserving_bookings(
        booking.check_in,
        booking.check_out,
    ).filter(
        assigned_room=room,
    ).exclude(pk=booking.pk)

    if overlapping.exists():
        raise ValidationError(
            "Phòng được gán đang trùng lịch với đơn khác."
        )

    booking.status = BookingRequest.Status.CHECKED_IN
    booking.actual_check_in = timezone.now()

    booking.save(
        update_fields=(
            "status",
            "actual_check_in",
        )
    )

    return booking


def get_checkout_summary(booking):
    service_total = booking.service_usages.aggregate(
        total=Sum(
            ExpressionWrapper(
                F("quantity") * F("unit_price"),
                output_field=DecimalField(max_digits=24, decimal_places=0),
            )
        )
    )["total"] or Decimal("0")
    momo_paid = booking.payment_attempts.filter(
        status=BookingPayment.Status.PAID
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total = booking.total_price + service_total

    return {
        "room_total": booking.total_price,
        "service_total": service_total,
        "momo_paid": momo_paid,
        "total": total,
        "amount_due": max(total - momo_paid, Decimal("0")),
        "has_pending_momo": booking.payment_attempts.filter(
            status=BookingPayment.Status.PENDING
        ).exists(),
    }


@transaction.atomic
def check_out_booking(
    booking_id,
    *,
    payment_method=None,
    expected_amount=None,
    received_by=None,
):
    booking = BookingRequest.objects.select_for_update().get(
        pk=booking_id
    )

    if booking.status != BookingRequest.Status.CHECKED_IN:
        raise ValidationError(
            "Chỉ trả phòng cho đơn đang lưu trú."
        )

    if not booking.assigned_room_id:
        raise ValidationError(
            "Đơn đang lưu trú chưa có phòng được gán."
        )

    summary = get_checkout_summary(booking)
    if summary["has_pending_momo"]:
        raise ValidationError(
            "Đơn đang có giao dịch MoMo xử lý. Hãy đợi giao dịch hoàn tất "
            "trước khi chốt tiền."
        )
    if (
        expected_amount is not None
        and summary["amount_due"] != expected_amount
    ):
        raise ValidationError(
            "Số tiền cần thu đã thay đổi. Vui lòng kiểm tra lại hóa đơn."
        )
    if summary["amount_due"] > 0:
        if not payment_method:
            raise ValidationError(
                "Vui lòng chọn phương thức thu tại quầy."
            )
        if payment_method not in BookingCounterPayment.Method.values:
            raise ValidationError(
                "Phương thức thu tại quầy không hợp lệ."
            )
        if BookingCounterPayment.objects.filter(booking=booking).exists():
            raise ValidationError(
                "Đơn này đã có khoản thu tại quầy."
            )
        room_amount = min(
            summary["amount_due"],
            max(summary["room_total"] - summary["momo_paid"], Decimal("0")),
        )
        BookingCounterPayment.objects.create(
            booking=booking,
            amount=summary["amount_due"],
            room_amount=room_amount,
            service_amount=summary["amount_due"] - room_amount,
            method=payment_method,
            received_by=received_by,
        )

    room = Room.objects.select_for_update().get(
        pk=booking.assigned_room_id
    )

    booking.status = BookingRequest.Status.CHECKED_OUT
    booking.actual_check_out = timezone.now()
    booking.payment_status = BookingRequest.PaymentStatus.PAID

    booking.save(
        update_fields=(
            "status",
            "actual_check_out",
            "payment_status",
        )
    )

    # Giữ nguyên trạng thái bảo trì nếu nhân viên đã đánh dấu trước.
    if room.status != Room.Status.MAINTENANCE:
        room.status = Room.Status.CLEANING
        room.save(update_fields=("status",))

    return booking


@transaction.atomic
def finish_room_cleaning(room_id):
    room = Room.objects.select_for_update().get(pk=room_id)

    if room.status != Room.Status.CLEANING:
        raise ValidationError(
            "Chỉ xác nhận dọn xong cho phòng đang dọn."
        )

    if BookingRequest.objects.filter(
        assigned_room=room,
        status=BookingRequest.Status.CHECKED_IN,
    ).exists():
        raise ValidationError(
            "Phòng vẫn có khách đang lưu trú."
        )

    room.status = Room.Status.READY
    room.save(update_fields=("status",))

    return room