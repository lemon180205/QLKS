from .models import BookingRequest, Room


ACTIVE_BOOKING_STATUSES = (
    BookingRequest.Status.PENDING,
    BookingRequest.Status.CONFIRMED,
    BookingRequest.Status.CHECKED_IN,
)


def get_available_room_count(room_type, check_in, check_out):
    ready_rooms = getattr(room_type, "ready_room_count", None)
    if ready_rooms is None:
        ready_rooms = Room.objects.filter(
            room_type=room_type,
            status=Room.Status.READY,
        ).count()
    active_bookings = BookingRequest.objects.filter(
        room_type=room_type,
        status__in=ACTIVE_BOOKING_STATUSES,
        check_in__lt=check_out,
        check_out__gt=check_in,
    ).count()
    return max(0, ready_rooms - active_bookings)
