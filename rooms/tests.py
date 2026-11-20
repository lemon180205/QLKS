from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BookingPayment, BookingRequest, Room, RoomType, Service


class InitialHotelDataTests(TestCase):
    def test_inventory_contains_expected_room_mix(self):
        self.assertEqual(Room.objects.count(), 50)
        self.assertEqual(
            Room.objects.filter(room_type__tier=RoomType.Tier.STANDARD).count(),
            30,
        )
        self.assertEqual(
            Room.objects.filter(room_type__tier=RoomType.Tier.VIP).count(),
            20,
        )
        self.assertEqual(RoomType.objects.count(), 5)

    def test_initial_services_are_available(self):
        self.assertEqual(Service.objects.count(), 3)
        self.assertEqual(Service.objects.filter(is_available=True).count(), 3)

    def test_admin_dashboard_shows_inventory_and_management_links(self):
        user = get_user_model().objects.create_superuser(
            username="hotel-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tổng số phòng")
        self.assertContains(response, "Phòng thường")
        self.assertContains(response, "Phòng VIP")
        self.assertContains(
            response,
            reverse("admin:rooms_service_changelist"),
        )
        self.assertContains(
            response,
            reverse("admin:rooms_bookingrequest_changelist"),
        )
        self.assertContains(response, "Yêu cầu đặt phòng chờ xác nhận")
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertContains(response, "sidebar-app-group")
        self.assertContains(response, "sidebar-group-arrow")

    def test_service_management_is_available_in_admin(self):
        user = get_user_model().objects.create_superuser(
            username="service-admin",
            email="services@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:rooms_service_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bữa sáng")
        self.assertContains(response, "Giặt ủi theo kg")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ReceptionistBookingAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="receptionist",
            email="reception@example.com",
            password="test-password",
            is_staff=True,
        )
        content_types = ContentType.objects.filter(app_label__in=("rooms", "accounts"))
        permissions = Permission.objects.filter(
            content_type__in=content_types,
            codename__in=(
                "add_bookingrequest",
                "change_bookingrequest",
                "view_bookingrequest",
                "view_room",
                "view_roomtype",
                "view_user",
            ),
        )
        self.staff.user_permissions.set(permissions)
        self.client.force_login(self.staff)
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")
        self.check_in = timezone.localdate() + timedelta(days=30)
        self.url = reverse("admin:rooms_bookingrequest_add")

    def booking_data(self, **overrides):
        data = {
            "room_type": self.room_type.pk,
            "guest_name": "Guest by phone",
            "email": "",
            "phone": "0933333333",
            "customer": "",
            "check_in": self.check_in.isoformat(),
            "check_out": (self.check_in + timedelta(days=2)).isoformat(),
            "guest_count": 2,
            "status": "confirmed",
            "payment_status": "at_hotel",
            "_save": "Lưu",
        }
        data.update(overrides)
        return data

    def test_receptionist_can_create_phone_booking_from_admin(self):
        response = self.client.post(self.url, self.booking_data())

        booking = BookingRequest.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(booking.phone, "0933333333")
        self.assertEqual(booking.email, "")
        self.assertEqual(booking.channel, BookingRequest.Channel.STAFF)
        self.assertEqual(booking.created_by, self.staff)
        self.assertEqual(booking.total_price, self.room_type.price_per_night * 2)

    def test_receptionist_cannot_book_above_room_capacity(self):
        response = self.client.post(
            self.url,
            self.booking_data(guest_count=self.room_type.capacity + 1),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BookingRequest.objects.count(), 0)
        self.assertContains(
            response,
            f"Loại phòng này tối đa {self.room_type.capacity} khách.",
        )

    def test_status_change_preserves_booking_price_snapshot(self):
        response = self.client.post(
            self.url,
            self.booking_data(status=BookingRequest.Status.PENDING),
        )
        self.assertEqual(response.status_code, 302)
        booking = BookingRequest.objects.get()
        original_rate = booking.nightly_rate
        original_total = booking.total_price

        self.room_type.price_per_night += 100000
        self.room_type.save(update_fields=("price_per_night",))
        change_url = reverse(
            "admin:rooms_bookingrequest_change",
            args=[booking.pk],
        )
        self.client.post(
            change_url,
            self.booking_data(status=BookingRequest.Status.CONFIRMED),
        )

        booking.refresh_from_db()
        self.assertEqual(booking.nightly_rate, original_rate)
        self.assertEqual(booking.total_price, original_total)

    def test_receptionist_cannot_cancel_while_momo_payment_is_pending(self):
        booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Guest with pending payment",
            phone="0933333333",
            check_in=self.check_in,
            check_out=self.check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CONFIRMED,
            payment_status=BookingRequest.PaymentStatus.PENDING,
        )
        BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
        )

        response = self.client.post(
            reverse("admin:rooms_bookingrequest_change", args=[booking.pk]),
            self.booking_data(status=BookingRequest.Status.CANCELLED),
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(booking.status, BookingRequest.Status.CONFIRMED)
        self.assertContains(response, "Giao dịch đang xử lý")
