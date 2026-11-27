from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from .models import BookingRequest, Room


LABELS = {
    "available": "Trống, sẵn sàng",
    "reserved": "Đã giữ chỗ",
    "occupied": "Đang có khách",
    "cleaning": "Đang dọn",
    "maintenance": "Bảo trì",
}


def build_room_map():
    today = timezone.localdate()

    # Bao gồm khách chưa check-out, kể cả đã quá ngày trả dự kiến.
    bookings = BookingRequest.objects.filter(
        Q(status=BookingRequest.Status.CHECKED_IN)
        | (
            Q(check_in__lte=today, check_out__gt=today)
            & (
                Q(status=BookingRequest.Status.CONFIRMED)
                | Q(
                    status=BookingRequest.Status.PENDING,
                    payment_status=BookingRequest.PaymentStatus.PENDING,
                )
            )
        )
    ).order_by("check_in", "pk")

    by_room = defaultdict(list)
    unassigned_count = 0

    for booking in bookings:
        if booking.assigned_room_id:
            by_room[booking.assigned_room_id].append(booking)
        else:
            unassigned_count += 1

    floors = defaultdict(list)
    counts = {key: 0 for key in LABELS}

    rooms = Room.objects.select_related("room_type").order_by(
        "floor",
        "number",
    )

    for room in rooms:
        reservations = by_room[room.pk]

        occupied = any(
            booking.status == BookingRequest.Status.CHECKED_IN
            for booking in reservations
        )

        if occupied:
            state = "occupied"
        elif room.status == Room.Status.MAINTENANCE:
            state = "maintenance"
        elif room.status == Room.Status.CLEANING:
            state = "cleaning"
        elif reservations:
            state = "reserved"
        else:
            state = "available"

        warning = ""

        if len(reservations) > 1:
            warning = "Có nhiều đơn cùng gán phòng: cần kiểm tra."
        elif reservations and room.status != Room.Status.READY:
            warning = (
                "Phòng có đơn lưu trú nhưng đang dọn hoặc bảo trì."
            )

        floors[room.floor].append(
            {
                "room": room,
                "state": state,
                "label": LABELS[state],
                "warning": warning,
            }
        )

        counts[state] += 1

    return {
        "today": today,
        "floors": dict(floors),
        "legend": [
            {
                "state": key,
                "label": label,
                "count": counts[key],
            }
            for key, label in LABELS.items()
        ],
        "unassigned_count": unassigned_count,
        "total_rooms": sum(counts.values()),
    }