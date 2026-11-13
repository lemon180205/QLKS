from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rooms.models import BookingRequest, RoomType


class RoomCatalogTests(TestCase):
    def test_room_list_displays_seeded_types_inventory_and_services(self):
        response = self.client.get(reverse("website:room_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phòng đơn tiêu chuẩn")
        self.assertContains(response, "Phòng Suite VIP")
        self.assertContains(response, "Phòng VIP")
        self.assertContains(response, "Bữa sáng")
        self.assertEqual(response.content.decode().count("10 phòng"), 5)

    def test_room_detail_displays_tier_and_nightly_price(self):
        room_type = RoomType.objects.get(name="Phòng Suite VIP")

        response = self.client.get(
            reverse("website:room_detail", args=[room_type.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phòng VIP")
        self.assertContains(response, "2200000")

    def test_search_shows_matching_available_room_types(self):
        check_in = timezone.localdate() + timedelta(days=7)
        check_out = check_in + timedelta(days=2)

        response = self.client.get(
            reverse("website:room_list"),
            {
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "guest_count": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phòng còn trống theo ngày")
        self.assertContains(response, "10 phòng còn trống")
        self.assertNotContains(response, "Phòng đơn tiêu chuẩn")

    def test_search_rejects_checkout_before_checkin(self):
        check_in = timezone.localdate() + timedelta(days=5)

        response = self.client.get(
            reverse("website:room_list"),
            {
                "check_in": check_in.isoformat(),
                "check_out": check_in.isoformat(),
                "guest_count": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ngày trả phòng phải sau ngày nhận phòng.")


class BookingRequestTests(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")
        self.check_in = timezone.localdate() + timedelta(days=14)
        self.check_out = self.check_in + timedelta(days=3)
        self.url = reverse(
            "website:booking_request",
            args=[self.room_type.pk],
        )

    def booking_data(self, **overrides):
        data = {
            "guest_name": "Nguyen Van A",
            "email": "guest@example.com",
            "phone": "0900000000",
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "guest_count": 2,
        }
        data.update(overrides)
        return data

    def test_guest_can_submit_booking_request(self):
        response = self.client.post(
            self.url,
            self.booking_data(),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)
        self.assertEqual(booking.nightly_rate, self.room_type.price_per_night)
        self.assertEqual(
            booking.total_price,
            self.room_type.price_per_night * 3,
        )
        self.assertContains(response, str(booking.reference_code))
        self.assertContains(response, "đang chờ khách sạn xác nhận")

    def test_booking_rejects_too_many_guests(self):
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

    def test_search_and_booking_respect_reserved_inventory(self):
        for index in range(10):
            BookingRequest.objects.create(
                room_type=self.room_type,
                guest_name=f"Guest {index}",
                email=f"guest{index}@example.com",
                phone="0900000000",
                check_in=self.check_in,
                check_out=self.check_out,
                guest_count=1,
                nightly_rate=Decimal("650000"),
                total_price=Decimal("1300000"),
            )

        search_response = self.client.get(
            reverse("website:room_list"),
            {
                "check_in": self.check_in.isoformat(),
                "check_out": self.check_out.isoformat(),
                "guest_count": 2,
            },
        )
        booking_response = self.client.post(
            self.url,
            self.booking_data(),
        )

        self.assertNotContains(search_response, "Phòng đôi tiêu chuẩn")
        self.assertEqual(booking_response.status_code, 200)
        self.assertContains(booking_response, "hiện không còn phòng trống")
        self.assertEqual(BookingRequest.objects.count(), 10)
