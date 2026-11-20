from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("dang-ky/", views.register, name="register"),
    path(
        "dang-nhap/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path(
        "dang-xuat/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("dat-phong/", views.bookings, name="bookings"),
    path(
        "dat-phong/<int:pk>/huy/",
        views.cancel_booking,
        name="cancel_booking",
    ),
]
