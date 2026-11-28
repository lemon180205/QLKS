from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import BookingRequest, Room, RoomType


class BookingAPITests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="api-test-customer",
        )
        self.other_user = User.objects.create_user(
            username="api-test-other",
        )

        self.room_type = RoomType.objects.create(
            name="Loại phòng kiểm thử API",
            capacity=2,
            price_per_night=500000,
        )

        Room.objects.create(
            number="API001",
            room_type=self.room_type,
        )

        self.check_in = timezone.localdate() + timedelta(days=7)
        self.check_out = self.check_in + timedelta(days=1)

        self.booking = self.make_booking(self.user)
        self.other_booking = self.make_booking(self.other_user)

        self.client = APIClient()
        token = RefreshToken.for_user(self.user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def make_booking(self, customer):
        return BookingRequest.objects.create(
            customer=customer,
            room_type=self.room_type,
            guest_name="Khách kiểm thử",
            email="guest@example.com",
            phone="0900000000",
            check_in=self.check_in,
            check_out=self.check_out,
            guest_count=2,
            nightly_rate=500000,
            total_price=500000,
        )

    def test_requires_jwt(self):
        client = APIClient()

        response = client.get("/api/bookings/mine/")

        self.assertEqual(response.status_code, 401)

    def test_only_lists_own_bookings(self):
        response = self.client.get("/api/bookings/mine/")

        self.assertEqual(response.status_code, 200)

        ids = [item["id"] for item in response.data]

        self.assertIn(self.booking.pk, ids)
        self.assertNotIn(self.other_booking.pk, ids)

    def test_cannot_cancel_another_customers_booking(self):
        response = self.client.post(
            f"/api/bookings/{self.other_booking.pk}/cancel/"
        )

        self.assertEqual(response.status_code, 404)

        self.other_booking.refresh_from_db()

        self.assertEqual(
            self.other_booking.status,
            BookingRequest.Status.PENDING,
        )

    def test_can_cancel_own_unpaid_booking(self):
        response = self.client.post(
            f"/api/bookings/{self.booking.pk}/cancel/"
        )

        self.assertEqual(response.status_code, 200)

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            BookingRequest.Status.CANCELLED,
        )

    def test_create_uses_server_price_and_jwt_customer(self):
        response = self.client.post(
            "/api/bookings/",
            {
                "room_type": self.room_type.pk,
                "guest_name": "Khách đặt qua API",
                "email": "booking@example.com",
                "phone": "0900000000",
                "check_in": self.check_in.isoformat(),
                "check_out": self.check_out.isoformat(),
                "guest_count": 2,

                # Cố gửi dữ liệu không được phép quyết định.
                "total_price": "1",
                "customer": self.other_user.pk,
                "status": "confirmed",
                "payment_status": "paid",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        booking = BookingRequest.objects.get(
            pk=response.data["id"]
        )

        self.assertEqual(booking.customer_id, self.user.pk)
        self.assertEqual(booking.total_price, Decimal("500000"))
        self.assertEqual(
            booking.status,
            BookingRequest.Status.PENDING,
        )
        self.assertEqual(
            booking.payment_status,
            BookingRequest.PaymentStatus.UNPAID,
        )