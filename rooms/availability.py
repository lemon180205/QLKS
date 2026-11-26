from collections import defaultdict

from django.db.models import Count, Q
from django.utils import timezone

from .models import BookingRequest, Room


RESERVING_BOOKING_STATUSES = (
    BookingRequest.Status.CONFIRMED,
    BookingRequest.Status.CHECKED_IN,
)


def get_reserving_bookings(check_in, check_out):
    return (
        BookingRequest.objects.filter(check_in__lt=check_out)
        .filter(
            Q(check_out__gt=check_in)
            | Q(status=BookingRequest.Status.CHECKED_IN)
        )
        .filter(
            Q(status__in=RESERVING_BOOKING_STATUSES)
            | Q(
                status=BookingRequest.Status.PENDING,
                payment_status=BookingRequest.PaymentStatus.PENDING,
            )
        )
    )


def get_available_room_counts(
    room_types,
    check_in,
    check_out,
    exclude_booking_id=None,
):
    room_type_ids = [room_type.pk for room_type in room_types]
    if not room_type_ids:
        return {}

    room_statuses = [Room.Status.READY]
    if check_in > timezone.localdate():
        room_statuses.append(Room.Status.CLEANING)

    room_counts = dict(
        Room.objects.filter(
            room_type_id__in=room_type_ids,
            status__in=room_statuses,
        )
        .values("room_type_id")
        .annotate(total=Count("pk"))
        .values_list("room_type_id", "total")
    )

    reservations = get_reserving_bookings(check_in, check_out).filter(
        room_type_id__in=room_type_ids
    )
    if exclude_booking_id is not None:
        reservations = reservations.exclude(pk=exclude_booking_id)
    events_by_room_type = defaultdict(lambda: defaultdict(int))
    for reservation in reservations.values(
        "room_type_id",
        "check_in",
        "check_out",
        "status",
    ):
        start = max(reservation["check_in"], check_in)
        reservation_end = reservation["check_out"]
        if reservation["status"] == BookingRequest.Status.CHECKED_IN:
            reservation_end = max(reservation_end, check_out)
        end = min(reservation_end, check_out)

        events = events_by_room_type[reservation["room_type_id"]]
        events[start] += 1
        events[end] -= 1

    available_counts = {}
    for room_type_id in room_type_ids:
        occupied = 0
        max_occupied = 0
        events = events_by_room_type[room_type_id]
        for event_date in sorted(events):
            occupied += events[event_date]
            max_occupied = max(max_occupied, occupied)
        available_counts[room_type_id] = max(
            0,
            room_counts.get(room_type_id, 0) - max_occupied,
        )
    return available_counts


def get_available_room_count(
    room_type,
    check_in,
    check_out,
    exclude_booking_id=None,
):
    return get_available_room_counts(
        [room_type],
        check_in,
        check_out,
        exclude_booking_id=exclude_booking_id,
    ).get(room_type.pk, 0)
