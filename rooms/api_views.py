from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


from website.forms import BookingRequestForm, RoomSearchForm

from .availability import (
    get_available_room_count,
    get_available_room_counts,
)
from .models import BookingRequest, RoomType
from .serializers import BookingSerializer, RoomTypeSerializer


class RoomTypeListAPIView(generics.ListAPIView):
    serializer_class = RoomTypeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        form = RoomSearchForm(self.request.query_params)

        if not form.is_valid():
            raise ValidationError({
                field: list(errors)
                for field, errors in form.errors.items()
            })

        room_types = RoomType.objects.all().order_by(
            "price_per_night",
            "name",
        )

        guest_count = form.cleaned_data.get("guest_count")
        check_in = form.cleaned_data.get("check_in")
        check_out = form.cleaned_data.get("check_out")

        if guest_count:
            room_types = room_types.filter(
                capacity__gte=guest_count
            )

        if check_in and check_out:
            room_types = list(room_types)

            available_counts = get_available_room_counts(
                room_types,
                check_in,
                check_out,
            )

            return [
                room_type
                for room_type in room_types
                if available_counts.get(room_type.pk, 0) > 0
            ]

        return room_types
class BookingRoomInputSerializer(serializers.Serializer):
    room_type = serializers.PrimaryKeyRelatedField(
        queryset=RoomType.objects.all(),
    )


class BookingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        room_input = BookingRoomInputSerializer(data=request.data)
        room_input.is_valid(raise_exception=True)

        room_type = room_input.validated_data["room_type"]

        # Dùng lại các kiểm tra ngày, sức chứa và phòng trống.
        form = BookingRequestForm(
            data=request.data,
            room_type=room_type,
        )

        if not form.is_valid():
            raise ValidationError({
                field: list(errors)
                for field, errors in form.errors.items()
            })

        with transaction.atomic():
            room_type = RoomType.objects.select_for_update().get(
                pk=room_type.pk
            )

            available_count = get_available_room_count(
                room_type,
                form.cleaned_data["check_in"],
                form.cleaned_data["check_out"],
            )

            if available_count < 1:
                raise ValidationError({
                    "detail": (
                        "Phòng vừa hết chỗ trong thời gian đã chọn. "
                        "Vui lòng tìm lại."
                    )
                })

            form.room_type = room_type
            booking = form.save(commit=False)

            # Tài khoản lấy từ JWT, không lấy từ dữ liệu khách gửi.
            booking.customer = request.user
            booking.channel = BookingRequest.Channel.WEBSITE
            booking.status = BookingRequest.Status.PENDING
            booking.payment_status = BookingRequest.PaymentStatus.UNPAID
            booking.save()

        return Response(
            BookingSerializer(
                booking,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )
class MyBookingListAPIView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            BookingRequest.objects
            .filter(customer=self.request.user)
            .select_related("room_type")
            .order_by("-created_at", "-pk")
        )
class BookingCancelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        with transaction.atomic():
            booking = get_object_or_404(
                BookingRequest.objects.select_for_update(),
                pk=pk,
                customer=request.user,
            )

            if booking.status not in (
                BookingRequest.Status.PENDING,
                BookingRequest.Status.CONFIRMED,
            ):
                raise ValidationError({
                    "detail": "Đơn này không còn được phép hủy."
                })

            payment_blocked = (
                booking.payment_status in (
                    BookingRequest.PaymentStatus.PENDING,
                    BookingRequest.PaymentStatus.PAID,
                )
                or booking.payment_attempts.filter(
                    status="pending"
                ).exists()
            )

            if payment_blocked:
                raise ValidationError({
                    "detail": (
                        "Đơn đang xử lý thanh toán hoặc đã thanh toán. "
                        "Vui lòng liên hệ khách sạn để được hỗ trợ."
                    )
                })

            booking.status = BookingRequest.Status.CANCELLED
            booking.save(update_fields=("status",))

        return Response(
            BookingSerializer(
                booking,
                context={"request": request},
            ).data
        )
class RoomTypeDetailAPIView(generics.RetrieveAPIView):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    permission_classes = [AllowAny]