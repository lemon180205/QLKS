from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.room_list, name="room_list"),
    path("phong/<int:pk>/", views.room_detail, name="room_detail"),
]