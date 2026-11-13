from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Room, RoomType, Service


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
