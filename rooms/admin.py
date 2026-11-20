from django import forms
from django.contrib import admin
from django.utils import timezone

from .availability import ACTIVE_BOOKING_STATUSES
from .models import BookingPayment, BookingRequest, Room, RoomType, Service
from website.notifications import send_booking_email


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "capacity", "price_per_night")
    search_fields = ("name",)
    list_filter = ("tier", "capacity")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("number", "room_type", "floor", "status")
    list_filter = ("room_type", "floor", "status")
    search_fields = ("number",)
    list_select_related = ("room_type",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available")
    list_editable = ("price", "is_available")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    class BookingRequestAdminForm(forms.ModelForm):
        class Meta:
            model = BookingRequest
            fields = (
                "room_type",
                "guest_name",
                "email",
                "phone",
                "customer",
                "check_in",
                "check_out",
                "guest_count",
                "status",
                "payment_status",
            )
            widgets = {
                "check_in": forms.DateInput(attrs={"type": "date"}),
                "check_out": forms.DateInput(attrs={"type": "date"}),
            }

        def clean(self):
            cleaned_data = super().clean()
            room_type = cleaned_data.get("room_type")
            check_in = cleaned_data.get("check_in")
            check_out = cleaned_data.get("check_out")
            guest_count = cleaned_data.get("guest_count")
            status = cleaned_data.get("status")

            if check_in and check_in < timezone.localdate():
                self.add_error("check_in", "Ngày nhận phòng không thể ở quá khứ.")
            if check_in and check_out and check_out <= check_in:
                self.add_error(
                    "check_out",
                    "Ngày trả phòng phải sau ngày nhận phòng.",
                )
            if room_type and guest_count and guest_count > room_type.capacity:
                self.add_error(
                    "guest_count",
                    f"Loại phòng này tối đa {room_type.capacity} khách.",
                )
            if self.instance.pk and status == BookingRequest.Status.CANCELLED:
                existing_booking = BookingRequest.objects.get(pk=self.instance.pk)
                if (
                    existing_booking.status != BookingRequest.Status.CANCELLED
                    and (
                        existing_booking.payment_status
                        in (
                            BookingRequest.PaymentStatus.PENDING,
                            BookingRequest.PaymentStatus.PAID,
                        )
                        or existing_booking.payment_attempts.filter(
                            status=BookingPayment.Status.PENDING
                        ).exists()
                    )
                ):
                    self.add_error(
                        "status",
                        "Giao dịch đang xử lý hoặc đã thanh toán. Hãy xác minh "
                        "và xử lý hoàn tiền trước khi hủy.",
                    )
            if (
                room_type
                and check_in
                and check_out
                and check_out > check_in
                and not (guest_count and guest_count > room_type.capacity)
            ):
                ready_rooms = room_type.rooms.filter(
                    status=Room.Status.READY
                ).count()
                overlapping_bookings = BookingRequest.objects.filter(
                    room_type=room_type,
                    status__in=ACTIVE_BOOKING_STATUSES,
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                )
                if self.instance.pk:
                    overlapping_bookings = overlapping_bookings.exclude(
                        pk=self.instance.pk
                    )
                if overlapping_bookings.count() >= ready_rooms:
                    raise forms.ValidationError(
                        "Không còn phòng trống cho loại phòng và thời gian này."
                    )
            return cleaned_data

    form = BookingRequestAdminForm
    list_display = (
        "reference_code",
        "guest_name",
        "phone",
        "room_type",
        "check_in",
        "check_out",
        "guest_count",
        "total_price",
        "status",
        "payment_status",
        "channel",
    )
    list_filter = ("status", "payment_status", "channel", "check_in", "room_type")
    search_fields = (
        "reference_code",
        "guest_name",
        "email",
        "phone",
        "customer__username",
    )
    list_select_related = ("room_type", "customer", "created_by")
    autocomplete_fields = ("customer",)
    readonly_fields = (
        "reference_code",
        "nightly_rate",
        "total_price",
        "created_at",
        "created_by",
        "channel",
    )
    date_hierarchy = "check_in"
    ordering = ("check_in", "room_type")
    fieldsets = (
        (
            "Thông tin khách",
            {"fields": ("guest_name", "phone", "email", "customer")},
        ),
        (
            "Lịch đặt phòng",
            {"fields": ("room_type", "check_in", "check_out", "guest_count")},
        ),
        (
            "Xử lý",
            {"fields": ("status", "payment_status", "channel", "created_by")},
        ),
        (
            "Thanh toán và hệ thống",
            {
                "fields": (
                    "nightly_rate",
                    "total_price",
                    "reference_code",
                    "created_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = BookingRequest.objects.get(pk=obj.pk).status
        else:
            obj.channel = BookingRequest.Channel.STAFF
            obj.created_by = request.user

        if not change or {"room_type", "check_in", "check_out"}.intersection(
            form.changed_data
        ):
            obj.nightly_rate = obj.room_type.price_per_night
            obj.total_price = (
                obj.nightly_rate * (obj.check_out - obj.check_in).days
            )
        else:
            existing_booking = BookingRequest.objects.get(pk=obj.pk)
            obj.nightly_rate = existing_booking.nightly_rate
            obj.total_price = existing_booking.total_price
        super().save_model(request, obj, form, change)

        if not change or previous_status != obj.status:
            subject = (
                "Khách sạn đã tạo đặt phòng cho bạn"
                if not change
                else "Cập nhật trạng thái đặt phòng"
            )
            send_booking_email(
                obj,
                subject,
                (
                    f"Xin chào {obj.guest_name},\n\n"
                    f"Mã đặt phòng: {obj.reference_code}\n"
                    f"Loại phòng: {obj.room_type}\n"
                    f"Thời gian: {obj.check_in} - {obj.check_out}\n"
                    f"Trạng thái: {obj.get_status_display()}\n"
                    f"Tổng tiền dự kiến: {obj.total_price:,.0f} VNĐ."
                ),
            )


@admin.register(BookingPayment)
class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "booking",
        "amount",
        "status",
        "transaction_id",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "order_id",
        "transaction_id",
        "booking__reference_code",
        "booking__guest_name",
        "booking__phone",
    )
    list_select_related = ("booking", "booking__room_type")
    readonly_fields = tuple(
        field.name for field in BookingPayment._meta.fields
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False