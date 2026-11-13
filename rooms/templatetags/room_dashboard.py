from django import template
from django.db.models import Count, Q

from rooms.models import BookingRequest, Room, RoomType, Service

register = template.Library()


@register.simple_tag
def hotel_dashboard_data():
    room_counts = Room.objects.aggregate(
        total=Count("pk"),
        ready=Count("pk", filter=Q(status=Room.Status.READY)),
        cleaning=Count("pk", filter=Q(status=Room.Status.CLEANING)),
        maintenance=Count("pk", filter=Q(status=Room.Status.MAINTENANCE)),
        standard=Count("pk", filter=Q(room_type__tier=RoomType.Tier.STANDARD)),
        vip=Count("pk", filter=Q(room_type__tier=RoomType.Tier.VIP)),
    )
    room_type_count = RoomType.objects.count()
    service_counts = Service.objects.aggregate(
        total=Count("pk"),
        available=Count("pk", filter=Q(is_available=True)),
    )
    pending_booking_count = BookingRequest.objects.filter(
        status=BookingRequest.Status.PENDING
    ).count()
    floor_distribution = list(
        Room.objects.values("floor").annotate(total=Count("pk")).order_by("floor")
    )
    for floor in floor_distribution:
        floor["percentage"] = round(
            floor["total"] * 100 / room_counts["total"]
        ) if room_counts["total"] else 0

    return {
        "room_counts": room_counts,
        "room_type_count": room_type_count,
        "service_counts": service_counts,
        "pending_booking_count": pending_booking_count,
        "floor_distribution": floor_distribution,
    }
