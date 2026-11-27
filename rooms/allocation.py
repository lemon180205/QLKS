from django.db import transaction
from django.utils import timezone

from .availability import get_reserving_bookings
from .models import BookingRequest, Room


@transaction.atomic
def find_available_room(
    room_type,
    check_in,
    check_out,
    booking_id=None,
):
    if booking_id:
        BookingRequest.objects.select_for_update().get(
            pk=booking_id
        )

    statuses = [Room.Status.READY]

    # Phòng đang dọn được phép phân cho ngày đến tương lai.
    if check_in > timezone.localdate():
        statuses.append(Room.Status.CLEANING)

    # Khóa các phòng ứng viên trong giao dịch hiện tại.
    rooms = list(
        Room.objects.select_for_update()
        .filter(
            room_type=room_type,
            status__in=statuses,
        )
        .order_by("floor", "number", "pk")
    )

    unavailable_ids = set(
        get_reserving_bookings(check_in, check_out)
        .exclude(pk=booking_id)
        .exclude(assigned_room_id=None)
        .values_list("assigned_room_id", flat=True)
    )

    return next(
        (
            room
            for room in rooms
            if room.pk not in unavailable_ids
        ),
        None,
    )