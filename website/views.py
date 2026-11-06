from django.shortcuts import render

from rooms.models import RoomType


def room_list(request):
    room_types = RoomType.objects.all()
    return render(
        request,
        "website/room_list.html",
        {"room_types": room_types},
    )