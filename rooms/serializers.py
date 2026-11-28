from rest_framework import serializers
from .models import BookingRequest, RoomType


class RoomTypeSerializer(serializers.ModelSerializer):
    tier_display = serializers.CharField(
        source="get_tier_display",
        read_only=True,
    )

    class Meta:
        model = RoomType
        fields = (
            "id",
            "name",
            "tier",
            "tier_display",
            "capacity",
            "price_per_night",
            "description",
            "image",
        )
        read_only_fields = fields
class BookingSerializer(serializers.ModelSerializer):
    code = serializers.CharField(
        source="display_code",
        read_only=True,
    )

    room_type_name = serializers.CharField(
        source="room_type.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    payment_status_display = serializers.CharField(
        source="get_payment_status_display",
        read_only=True,
    )

    class Meta:
        model = BookingRequest

        fields = (
            "id",
            "code",
            "room_type",
            "room_type_name",
            "guest_name",
            "email",
            "phone",
            "check_in",
            "check_out",
            "guest_count",
            "nightly_rate",
            "total_price",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "created_at",
        )

        read_only_fields = fields