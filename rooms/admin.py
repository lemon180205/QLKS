from django.contrib import admin

from .models import BookingRequest, Room, RoomType, Service


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "capacity", "price_per_night")
    search_fields = ("name",)
    list_filter = ("tier", "capacity")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "room_type", "floor", "status")
    list_filter = ("room_type", "floor", "status")
    search_fields = ("number",)
    list_select_related = ("room_type",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available")
    list_editable = ("price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "guest_name",
        "room_type",
        "check_in",
        "check_out",
        "guest_count",
        "total_price",
        "status",
    )
    list_filter = ("status", "check_in", "room_type")
    search_fields = ("reference_code", "guest_name", "email", "phone")
    list_select_related = ("room_type",)
    readonly_fields = ("reference_code", "nightly_rate", "total_price", "created_at")
    date_hierarchy = "check_in"