from django.urls import path

from .api_views import (
    BookingCancelAPIView,
    BookingCreateAPIView,
    MyBookingListAPIView,
    RoomTypeListAPIView,
    RoomTypeDetailAPIView,
)

app_name = "rooms_api"

urlpatterns = [
    path(
        "room-types/",
        RoomTypeListAPIView.as_view(),
        name="room-type-list",
    ),
    path(
        "bookings/",
        BookingCreateAPIView.as_view(),
        name="booking-create",
    ),
        path(
        "bookings/mine/",
        MyBookingListAPIView.as_view(),
        name="my-bookings",
    ),
    path(
        "bookings/<int:pk>/cancel/",
        BookingCancelAPIView.as_view(),
        name="booking-cancel",
    ),
    path(
        "room-types/<int:pk>/",
        RoomTypeDetailAPIView.as_view(),
        name="room-type-detail",
    ),
]