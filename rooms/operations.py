from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import BookingRequest, Room


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

    overlapping = BookingRequest.objects.filter(
        assigned_room=room,
        status__in=(
            BookingRequest.Status.PENDING,
            BookingRequest.Status.CONFIRMED,
        ),
        check_in__lt=booking.check_out,
        check_out__gt=booking.check_in,
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


@transaction.atomic
def check_out_booking(booking_id):
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

    room = Room.objects.select_for_update().get(
        pk=booking.assigned_room_id
    )

    booking.status = BookingRequest.Status.CHECKED_OUT
    booking.actual_check_out = timezone.now()

    booking.save(
        update_fields=(
            "status",
            "actual_check_out",
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