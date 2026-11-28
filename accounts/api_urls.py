from django.urls import path

from .api_views import CurrentUserAPIView, RegisterAPIView

app_name = "accounts_api"

urlpatterns = [
    path(
        "me/",
        CurrentUserAPIView.as_view(),
        name="current-user",
    ),
    path(
        "register/",
        RegisterAPIView.as_view(),
        name="register",
    ),
]