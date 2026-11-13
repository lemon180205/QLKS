from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from rooms.availability import get_available_room_count
from rooms.models import RoomType, Service

from .forms import BookingRequestForm, RoomSearchForm


def room_list(request):
    search_form = RoomSearchForm(request.GET if request.GET else None)
    room_types = RoomType.objects.annotate(room_count=Count("rooms"))
    available_counts = {}
    has_availability_search = False

    if search_form.is_valid():
        check_in = search_form.cleaned_data.get("check_in")
        check_out = search_form.cleaned_data.get("check_out")
        guest_count = search_form.cleaned_data.get("guest_count")
        if guest_count:
            room_types = room_types.filter(capacity__gte=guest_count)
        if check_in and check_out:
            has_availability_search = True
            available_counts = {
                room_type.pk: get_available_room_count(
                    room_type,
                    check_in,
                    check_out,
                )
                for room_type in room_types
            }
            room_types = room_types.filter(
                pk__in=[
                    room_type_id
                    for room_type_id, available_count in available_counts.items()
                    if available_count
                ]
            )

    room_cards = [
        (room_type, available_counts.get(room_type.pk))
        for room_type in room_types
    ]

    return render(
        request,
        "website/room_list.html",
        {
            "room_cards": room_cards,
            "search_form": search_form,
            "available_counts": available_counts,
            "has_availability_search": has_availability_search,
            "services": Service.objects.filter(is_available=True),
        },
    )


def room_detail(request, pk):
    room_type = get_object_or_404(RoomType, pk=pk)

    return render(
        request,
        "website/room_detail.html",
        {"room_type": room_type},
    )


def booking_request(request, pk):
    room_type = get_object_or_404(RoomType, pk=pk)
    initial = {
        key: request.GET[key]
        for key in ("check_in", "check_out", "guest_count")
        if key in request.GET
    }
    form = BookingRequestForm(
        request.POST if request.method == "POST" else None,
        room_type=room_type,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            room_type = RoomType.objects.select_for_update().get(pk=room_type.pk)
            if get_available_room_count(
                room_type,
                form.cleaned_data["check_in"],
                form.cleaned_data["check_out"],
            ) < 1:
                form.add_error(
                    None,
                    "Phòng vừa hết chỗ trong khoảng ngày đã chọn. Vui lòng chọn ngày khác.",
                )
            else:
                form.room_type = room_type
                booking = form.save()
                messages.success(
                    request,
                    (
                        f"Đã gửi yêu cầu đặt phòng. Mã yêu cầu: "
                        f"{booking.reference_code}. Yêu cầu đang chờ khách sạn "
                        "xác nhận tình trạng phòng trước khi hoàn tất đặt phòng."
                    ),
                )
                return redirect("website:room_list")

    return render(
        request,
        "website/booking_request.html",
        {"room_type": room_type, "form": form},
    )