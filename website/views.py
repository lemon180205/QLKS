from django.shortcuts import get_object_or_404, render

from rooms.models import RoomType


def room_list(request):
    room_types = RoomType.objects.all()
    return render(
        request,
        "website/room_list.html",
        {"room_types": room_types},
    )
def room_detail(request, pk):
    room_type = get_object_or_404(RoomType, pk=pk)

    return render(
        request,
        "website/room_detail.html",
        {"room_type": room_type},
    )