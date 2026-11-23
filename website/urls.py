from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.room_list, name="room_list"),
    path("phong/<int:pk>/", views.room_detail, name="room_detail"),
    path("dat-phong/<int:pk>/", views.booking_request, name="booking_request"),
    path(
        "dat-phong/xac-nhan/<uuid:reference_code>/",
        views.booking_confirmation,
        name="booking_confirmation",
    ),
    path(
        "thanh-toan/momo/<int:pk>/",
        views.initiate_momo_payment,
        name="initiate_momo_payment",
    ),
    path(
        "thanh-toan/momo/return/",
        views.momo_return,
        name="momo_return",
    ),
    path(
        "thanh-toan/momo/ipn/",
        views.momo_ipn,
        name="momo_ipn",
    ),
]