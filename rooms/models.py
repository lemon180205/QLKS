import uuid

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


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        CHECKED_IN = "checked_in", "Đang lưu trú"
        CHECKED_OUT = "checked_out", "Đã trả phòng"
        CANCELLED = "cancelled", "Đã hủy"

    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name="booking_requests",
        verbose_name="Loại phòng",
    )
    reference_code = models.UUIDField(
        "Mã yêu cầu",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    guest_name = models.CharField("Tên khách", max_length=120)
    email = models.EmailField("Email")
    phone = models.CharField("Số điện thoại", max_length=20)
    check_in = models.DateField("Ngày nhận phòng")
    check_out = models.DateField("Ngày trả phòng")
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