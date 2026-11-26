from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .operations import (
    check_in_booking,
    check_out_booking,
    finish_room_cleaning,
    get_checkout_summary,
)
from .reporting import build_monthly_revenue_report

from .availability import (
    RESERVING_BOOKING_STATUSES,
    get_available_room_count,
    get_reserving_bookings,
)
from .models import (
    BookingCounterPayment,
    BookingPayment,
    BookingRequest,
    BookingServiceUsage,
    Room,
    RoomType,
    Service,
)
from website.notifications import send_booking_email


class BookingCheckoutForm(forms.Form):
    expected_amount = forms.DecimalField(
        min_value=0,
        decimal_places=0,
        widget=forms.HiddenInput,
    )
    payment_method = forms.ChoiceField(
        label="Phương thức thu tại quầy",
        choices=[
            ("", "---------"),
            *BookingCounterPayment.Method.choices,
        ],
        required=False,
    )

    def __init__(self, *args, amount_due, **kwargs):
        super().__init__(*args, **kwargs)
        self.amount_due = amount_due
        self.fields["expected_amount"].initial = amount_due
        self.fields["payment_method"].required = amount_due > 0

    def clean_expected_amount(self):
        expected_amount = self.cleaned_data["expected_amount"]
        if expected_amount != self.amount_due:
            raise forms.ValidationError(
                "Số tiền cần thu đã thay đổi. Vui lòng kiểm tra lại hóa đơn.",
                code="amount_changed",
            )
        return expected_amount


class MonthlyRevenueForm(forms.Form):
    month = forms.IntegerField(
        label="Tháng",
        min_value=1,
        max_value=12,
    )
    year = forms.IntegerField(
        label="Năm",
        min_value=2000,
        max_value=9998,
    )


class BookingServiceUsageForm(forms.ModelForm):
    class Meta:
        model = BookingServiceUsage
        fields = ("service", "quantity")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["service"].queryset = Service.objects.filter(
                pk=self.instance.service_id
            )
            self.fields["service"].disabled = True
        else:
            self.fields["service"].queryset = Service.objects.filter(
                is_available=True
            )

    def clean(self):
        cleaned_data = super().clean()
        booking = self.instance.booking

        if booking.status != BookingRequest.Status.CHECKED_IN and (
            self.instance._state.adding or self.has_changed()
        ):
            raise forms.ValidationError(
                "Chỉ ghi nhận dịch vụ khi khách đang lưu trú."
            )

        service = cleaned_data.get("service")
        if self.instance._state.adding and service and not service.is_available:
            self.add_error("service", "Dịch vụ hiện không còn phục vụ.")

        return cleaned_data

    def save(self, commit=True):
        usage = super().save(commit=False)
        if usage._state.adding:
            usage.unit_price = usage.service.price

        if commit:
            usage.save()
            self.save_m2m()
        return usage


class BookingServiceUsageInline(admin.TabularInline):
    model = BookingServiceUsage
    form = BookingServiceUsageForm
    fields = ("service", "quantity", "unit_price", "used_at")
    readonly_fields = ("unit_price", "used_at")
    extra = 0
    can_delete = False

    def has_view_permission(self, request, obj=None):
        return (
            request.user.has_perm("rooms.view_bookingrequest")
            or request.user.has_perm("rooms.change_bookingrequest")
        )

    def has_add_permission(self, request, obj=None):
        return bool(
            obj
            and obj.status == BookingRequest.Status.CHECKED_IN
            and request.user.has_perm("rooms.change_bookingrequest")
        )

    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


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
    actions = ("mark_cleaning_finished",)



    @admin.action(
        description="Xác nhận phòng đã dọn xong",
        permissions=["change"],
    )
    def mark_cleaning_finished(self, request, queryset):
        success_count = 0

        for room_id in queryset.values_list("pk", flat=True):
            try:
                room = finish_room_cleaning(room_id)
            except ValidationError as exc:
                self.message_user(
                    request,
                    f"Phòng ID {room_id}: {' '.join(exc.messages)}",
                    level="warning",
                )
            else:
                success_count += 1

        if success_count:
            self.message_user(
                request,
                f"Đã chuyển {success_count} phòng về Sẵn sàng.",
                level="success",
            )


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
                "assigned_room",
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
            existing = None

            if self.instance.pk:
                existing = BookingRequest.objects.get(
                    pk=self.instance.pk
                )
            room_type = cleaned_data.get("room_type")
            check_in = cleaned_data.get("check_in")
            check_out = cleaned_data.get("check_out")
            guest_count = cleaned_data.get("guest_count")
            status = cleaned_data.get("status")
            payment_status = cleaned_data.get("payment_status")
            reserves_inventory = status in RESERVING_BOOKING_STATUSES or (
                status == BookingRequest.Status.PENDING
                and payment_status == BookingRequest.PaymentStatus.PENDING
            )

            if (
                check_in
                and check_in < timezone.localdate()
                and (
                    not self.instance.pk
                    or "check_in" in self.changed_data
                )
            ):
                self.add_error(
                    "check_in",
                    "Ngày nhận phòng không thể ở quá khứ.",
                )
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
                available_count = get_available_room_count(
                    room_type,
                    check_in,
                    check_out,
                    exclude_booking_id=self.instance.pk,
                )
                if available_count < 1:
                    raise forms.ValidationError(
                        "Không còn phòng trống cho loại phòng và thời gian này."
                    )



            assigned_room = cleaned_data.get("assigned_room")

            if assigned_room and room_type:
                if assigned_room.room_type_id != room_type.pk:
                    self.add_error(
                        "assigned_room",
                        "Phòng phải thuộc đúng loại phòng đã đặt.",
                    )

                if (
                    assigned_room.status == Room.Status.MAINTENANCE
                    and reserves_inventory
                ):
                    self.add_error(
                        "assigned_room",
                        "Phòng đang bảo trì, không thể gán.",
                    )

                if (
                    check_in
                    and check_out
                    and check_out > check_in
                    and reserves_inventory
                ):
                    conflicts = get_reserving_bookings(
                        check_in,
                        check_out,
                    ).filter(
                        assigned_room=assigned_room,
                    ).exclude(pk=self.instance.pk)

                    if conflicts.exists():
                        self.add_error(
                            "assigned_room",
                            "Phòng đã được gán cho đơn khác trong thời gian này.",
                        )



                

            previous_status = existing.status if existing else None

            protected_statuses = (
                BookingRequest.Status.CHECKED_IN,
                BookingRequest.Status.CHECKED_OUT,
            )

            if status != previous_status:
                if (
                    status in protected_statuses
                    or previous_status in protected_statuses
                ):
                    self.add_error(
                        "status",
                        "Hãy dùng thao tác Check-in hoặc Check-out "
                        "trong danh sách đơn đặt phòng.",
                    )

            if (
                existing
                and previous_status in protected_statuses
            ):
                locked_fields = {
                    "room_type",
                    "assigned_room",
                    "check_in",
                    "check_out",
                }

                if locked_fields.intersection(self.changed_data):
                    raise forms.ValidationError(
                        "Không được đổi phòng hoặc lịch đặt của đơn "
                        "đang lưu trú hay đã trả phòng bằng form này."
                    )

            return cleaned_data

    form = BookingRequestAdminForm
    inlines = (BookingServiceUsageInline,)
    change_list_template = "admin/rooms/bookingrequest/change_list.html"
    list_display = (
        "reference_code",
        "guest_name",
        "phone",
        "room_type",
        "assigned_room",
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
    list_select_related = ("room_type", "customer", "created_by", "assigned_room")
    autocomplete_fields = ("customer",)
    readonly_fields = (
        "reference_code",
        "nightly_rate",
        "total_price",
        "created_at",
        "created_by",
        "channel",
        "actual_check_in",
        "actual_check_out",
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
                {
                    "fields": (
                        "room_type",
                        "assigned_room",
                        "check_in",
                        "check_out",
                        "guest_count",
                    )
                },
            ),
                    (
            "Nhận và trả phòng thực tế",
            {
                "fields": (
                    "actual_check_in",
                    "actual_check_out",
                )
            },
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
    actions = (
        "check_in_selected",
        "check_out_selected",
    )

    def get_inlines(self, request, obj):
        if obj is None:
            return ()
        return super().get_inlines(request, obj)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "monthly-revenue/",
                self.admin_site.admin_view(self.monthly_revenue_view),
                name="rooms_bookingrequest_monthly_revenue",
            ),
            path(
                "<path:object_id>/checkout/",
                self.admin_site.admin_view(self.checkout_view),
                name="rooms_bookingrequest_checkout",
            ),
        ]
        return custom_urls + urls

    def monthly_revenue_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied

        today = timezone.localdate()
        initial = {"month": today.month, "year": today.year}
        form = MonthlyRevenueForm(request.GET or None, initial=initial)
        report = None
        if not request.GET:
            report = build_monthly_revenue_report(**initial)
        elif form.is_valid():
            report = build_monthly_revenue_report(
                year=form.cleaned_data["year"],
                month=form.cleaned_data["month"],
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Báo cáo doanh thu theo tháng",
            "opts": self.model._meta,
            "form": form,
            "report": report,
            "change_list_url": reverse(
                "admin:rooms_bookingrequest_changelist"
            ),
        }
        return TemplateResponse(
            request,
            "admin/rooms/bookingrequest/monthly_revenue.html",
            context,
        )

    def checkout_view(self, request, object_id):
        booking = self.get_object(request, object_id)
        if booking is None:
            raise Http404
        if not self.has_change_permission(request, booking):
            raise PermissionDenied

        change_url = reverse(
            "admin:rooms_bookingrequest_change",
            args=(booking.pk,),
        )
        if booking.status != BookingRequest.Status.CHECKED_IN:
            self.message_user(
                request,
                "Chỉ chốt tiền cho đơn đang lưu trú.",
                level="warning",
            )
            return HttpResponseRedirect(change_url)

        summary = get_checkout_summary(booking)
        if request.method == "POST":
            form = BookingCheckoutForm(
                request.POST,
                amount_due=summary["amount_due"],
            )
            if form.is_valid():
                try:
                    check_out_booking(
                        booking.pk,
                        payment_method=form.cleaned_data["payment_method"],
                        expected_amount=form.cleaned_data["expected_amount"],
                        received_by=request.user,
                    )
                except ValidationError as exc:
                    self.message_user(
                        request,
                        " ".join(exc.messages),
                        level="error",
                    )
                    booking.refresh_from_db()
                    if booking.status != BookingRequest.Status.CHECKED_IN:
                        return HttpResponseRedirect(change_url)
                    return HttpResponseRedirect(request.path)

                if summary["amount_due"]:
                    self.message_user(
                        request,
                        f"Đã thu {summary['amount_due']:,.0f} VNĐ và check-out "
                        f"phòng {booking.assigned_room.number}.",
                        level="success",
                    )
                else:
                    self.message_user(
                        request,
                        f"Đã check-out phòng {booking.assigned_room.number}; "
                        "đơn đã được thanh toán đủ.",
                        level="success",
                    )
                return HttpResponseRedirect(change_url)
            if form.has_error("expected_amount", "amount_changed"):
                self.message_user(
                    request,
                    "Số tiền cần thu đã thay đổi. Hãy kiểm tra hóa đơn mới.",
                    level="warning",
                )
                return HttpResponseRedirect(request.path)
        else:
            form = BookingCheckoutForm(amount_due=summary["amount_due"])

        context = {
            **self.admin_site.each_context(request),
            "title": f"Chốt tiền - {booking}",
            "opts": self.model._meta,
            "booking": booking,
            "summary": summary,
            "form": form,
            "change_url": change_url,
            "can_confirm": not summary["has_pending_momo"],
        }
        return TemplateResponse(
            request,
            "admin/rooms/bookingrequest/checkout.html",
            context,
        )

    @admin.action(
        description="Check-in đơn đã chọn",
        permissions=["change"],
    )
    def check_in_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Vui lòng chọn đúng một đơn để check-in.",
                level="warning",
            )
            return

        try:
            booking = check_in_booking(queryset.get().pk)
        except ValidationError as exc:
            self.message_user(
                request,
                " ".join(exc.messages),
                level="error",
            )
            return

        self.message_user(
            request,
            f"Đã check-in phòng {booking.assigned_room.number}.",
            level="success",
        )

    @admin.action(
        description="Chốt tiền và check-out đơn đã chọn",
        permissions=["change"],
    )
    def check_out_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Vui lòng chọn đúng một đơn để check-out.",
                level="warning",
            )
            return

        return HttpResponseRedirect(
            reverse(
                "admin:rooms_bookingrequest_checkout",
                args=(queryset.get().pk,),
            )
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

    def save_formset(self, request, form, formset, change):
        if formset.model is BookingServiceUsage and any(
            inline_form.has_changed() for inline_form in formset.forms
        ):
            booking = BookingRequest.objects.select_for_update().get(
                pk=form.instance.pk
            )
            if booking.status != BookingRequest.Status.CHECKED_IN:
                self.message_user(
                    request,
                    "Đơn đã không còn ở trạng thái lưu trú; "
                    "không thể ghi hoặc sửa dịch vụ.",
                    level="error",
                )
                return

        super().save_formset(request, form, formset, change)


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


@admin.register(BookingCounterPayment)
class BookingCounterPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "amount",
        "method",
        "received_at",
        "received_by",
    )
    list_filter = ("method", "received_at")
    search_fields = (
        "booking__reference_code",
        "booking__guest_name",
        "booking__phone",
    )
    list_select_related = ("booking", "received_by")
    readonly_fields = tuple(
        field.name for field in BookingCounterPayment._meta.fields
    )
    date_hierarchy = "received_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False