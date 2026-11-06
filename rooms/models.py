from django.core.validators import MinValueValidator
from django.db import models


class RoomType(models.Model):
    name = models.CharField(
        "Tên loại phòng",
        max_length=100,
        unique=True,
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