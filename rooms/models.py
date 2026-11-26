import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class RoomType(models.Model):
    class Tier(models.TextChoices):
        STANDARD = "standard", "Phòng thường"
        VIP = "vip", "Phòng VIP"

    name = models.CharField(
        "Tên loại phòng",
        max_length=100,
        unique=True,
    )
    tier = models.CharField(
        "Phân hạng",
        max_length=10,
        choices=Tier.choices,
        default=Tier.STANDARD,
    )
    capacity = models.PositiveSmallIntegerField(
        "Số khách tối đa",
        validators=[MinValueValidator(1)],
    )
    price_per_night = models.DecimalField(
        "Giá mỗi đêm (VNĐ)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(1)],
    )
    description = models.TextField(
        "Mô tả",
        blank=True,
    )
    image = models.ImageField(
        "Ảnh đại diện",
        upload_to="room_types/",
        blank=True,
    )

    class Meta:
        verbose_name = "Loại phòng"
        verbose_name_plural = "Loại phòng"
        ordering = ["price_per_night", "name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Sẵn sàng"
        CLEANING = "cleaning", "Đang dọn"
        MAINTENANCE = "maintenance", "Bảo trì"

    number = models.CharField(
        "Số phòng",
        max_length=10,
        unique=True,
    )
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="rooms",
        verbose_name="Loại phòng",
    )
    floor = models.PositiveSmallIntegerField(
        "Tầng",
        default=1,
    )
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=Status.choices,
        default=Status.READY,
    )

    class Meta:
        verbose_name = "Phòng"
        verbose_name_plural = "Phòng"
        ordering = ["number"]

    def __str__(self):
        return f"Phòng {self.number}"


class Service(models.Model):
    class Category(models.TextChoices):
        DINING = "dining", "Ăn uống"
        LAUNDRY = "laundry", "Giặt ủi"
        OTHER = "other", "Khác"

    name = models.CharField("Tên dịch vụ", max_length=100, unique=True)
    category = models.CharField(
        "Danh mục",
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    description = models.TextField("Mô tả", blank=True)
    price = models.DecimalField(
        "Giá dịch vụ (VNĐ)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    is_available = models.BooleanField("Đang phục vụ", default=True)

    class Meta:
        verbose_name = "Dịch vụ"
        verbose_name_plural = "Dịch vụ"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class BookingServiceUsage(models.Model):
    booking = models.ForeignKey(
        "BookingRequest",
        on_delete=models.PROTECT,
        related_name="service_usages",
        verbose_name="Yêu cầu đặt phòng",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="booking_usages",
        verbose_name="Dịch vụ",
    )
    quantity = models.PositiveIntegerField(
        "Số lượng",
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        "Đơn giá tại thời điểm sử dụng (VNĐ)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)],
        editable=False,
    )
    used_at = models.DateTimeField(
        "Thời điểm sử dụng",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Dịch vụ phát sinh"
        verbose_name_plural = "Dịch vụ phát sinh"
        ordering = ["used_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="booking_service_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="booking_service_unit_price_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.service} x {self.quantity} - {self.booking}"


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        CHECKED_IN = "checked_in", "Đang lưu trú"
        CHECKED_OUT = "checked_out", "Đã trả phòng"
        CANCELLED = "cancelled", "Đã hủy"

    class Channel(models.TextChoices):
        WEBSITE = "website", "Website"
        STAFF = "staff", "Lễ tân"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Chưa thanh toán"
        PENDING = "pending", "Đang thanh toán"
        PAID = "paid", "Đã thanh toán"
        FAILED = "failed", "Thanh toán thất bại"
        AT_HOTEL = "at_hotel", "Thanh toán tại khách sạn"

    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="booking_requests",
        verbose_name="Loại phòng",
    )

    assigned_room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="assigned_bookings",
        null=True,
        blank=True,
        verbose_name="Phòng được gán",
    )
    reference_code = models.UUIDField(
        "Mã yêu cầu",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    guest_name = models.CharField("Tên khách", max_length=120)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Số điện thoại", max_length=20)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="hotel_bookings",
        null=True,
        blank=True,
        verbose_name="Tài khoản khách",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_hotel_bookings",
        null=True,
        blank=True,
        editable=False,
        verbose_name="Nhân viên tạo",
    )
    channel = models.CharField(
        "Kênh đặt phòng",
        max_length=10,
        choices=Channel.choices,
        default=Channel.WEBSITE,
    )
    check_in = models.DateField("Ngày nhận phòng")
    check_out = models.DateField("Ngày trả phòng")
    actual_check_in = models.DateTimeField(
        "Thời gian nhận phòng thực tế",
        null=True,
        blank=True,
        editable=False,
    )

    actual_check_out = models.DateTimeField(
        "Thời gian trả phòng thực tế",
        null=True,
        blank=True,
        editable=False,
    )

    guest_count = models.PositiveSmallIntegerField(
        "Số khách",
        validators=[MinValueValidator(1)],
    )
    guest_count = models.PositiveSmallIntegerField(
        "Số khách",
        validators=[MinValueValidator(1)],


    
    )
    nightly_rate = models.DecimalField(
        "Giá mỗi đêm tại thời điểm đặt (VNĐ)",
        max_digits=12,
        decimal_places=0,
    )
    total_price = models.DecimalField(
        "Tổng tiền dự kiến (VNĐ)",
        max_digits=12,
        decimal_places=0,
    )
    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_status = models.CharField(
        "Trạng thái thanh toán",
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    created_at = models.DateTimeField("Ngày gửi yêu cầu", auto_now_add=True)

    class Meta:
        verbose_name = "Yêu cầu đặt phòng"
        verbose_name_plural = "Yêu cầu đặt phòng"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(check_out__gt=F("check_in")),
                name="booking_checkout_after_checkin",
            ),
            models.CheckConstraint(
                condition=Q(guest_count__gte=1),
                name="booking_guest_count_positive",
            ),
        ]

    def __str__(self):
        return f"{self.guest_name} - {self.room_type} ({self.check_in})"


class BookingPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Đang thanh toán"
        PAID = "paid", "Đã thanh toán"
        FAILED = "failed", "Thanh toán thất bại"

    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
        verbose_name="Yêu cầu đặt phòng",
    )
    order_id = models.UUIDField("Mã giao dịch", default=uuid.uuid4, unique=True)
    request_id = models.UUIDField("Mã yêu cầu MoMo", default=uuid.uuid4, unique=True)
    amount = models.DecimalField("Số tiền (VNĐ)", max_digits=12, decimal_places=0)
    pay_url = models.URLField("Đường dẫn thanh toán", max_length=500, blank=True)
    status = models.CharField(
        "Trạng thái",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    transaction_id = models.CharField(
        "Mã giao dịch MoMo",
        max_length=64,
        blank=True,
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    paid_at = models.DateTimeField("Ngày thanh toán", null=True, blank=True)
    failed_at = models.DateTimeField(
        "Thời điểm thanh toán thất bại",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Giao dịch thanh toán"
        verbose_name_plural = "Giao dịch thanh toán"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="booking_payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.order_id} - {self.get_status_display()}"


class BookingCounterPayment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Tiền mặt"
        BANK_TRANSFER = "bank_transfer", "Chuyển khoản"
        CARD = "card", "Thẻ"

    booking = models.OneToOneField(
        BookingRequest,
        on_delete=models.PROTECT,
        related_name="counter_payment",
        verbose_name="Yêu cầu đặt phòng",
    )
    amount = models.DecimalField(
        "Số tiền đã thu (VNĐ)",
        max_digits=24,
        decimal_places=0,
    )
    room_amount = models.DecimalField(
        "Tiền phòng thu tại quầy (VNĐ)",
        max_digits=24,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    service_amount = models.DecimalField(
        "Tiền dịch vụ thu tại quầy (VNĐ)",
        max_digits=24,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    method = models.CharField(
        "Phương thức thu",
        max_length=20,
        choices=Method.choices,
    )
    received_at = models.DateTimeField(
        "Thời điểm thu",
        auto_now_add=True,
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="hotel_counter_payments",
        null=True,
        blank=True,
        verbose_name="Nhân viên thu",
    )

    class Meta:
        verbose_name = "Khoản thu tại quầy"
        verbose_name_plural = "Khoản thu tại quầy"
        ordering = ["-received_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="booking_counter_payment_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(room_amount__gte=0) & Q(service_amount__gte=0),
                name="booking_counter_payment_parts_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(amount=F("room_amount") + F("service_amount")),
                name="booking_counter_payment_parts_match_amount",
            ),
        ]

    def __str__(self):
        return f"{self.booking} - {self.amount:,.0f} VNĐ"