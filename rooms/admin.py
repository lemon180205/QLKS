from django.contrib import admin

from .models import Room, RoomType


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "price_per_night")
    search_fields = ("name",)
    list_filter = ("capacity",)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "room_type", "floor", "status")
    list_filter = ("room_type", "floor", "status")
    search_fields = ("number",)
    list_select_related = ("room_type",)