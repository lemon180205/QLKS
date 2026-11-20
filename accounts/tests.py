from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CustomerRegistrationTests(TestCase):
    def test_account_urls_are_grouped_under_account_prefix(self):
        self.assertEqual(reverse("accounts:register"), "/tai-khoan/dang-ky/")
        self.assertEqual(reverse("accounts:bookings"), "/tai-khoan/dat-phong/")

    def test_customer_can_register_with_email_and_phone(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-customer",
                "first_name": "An",
                "last_name": "Nguyen",
                "email": "an@example.com",
                "phone": "0944444444",
                "password1": "Strong-test-password-2026",
                "password2": "Strong-test-password-2026",
            },
        )

        user = get_user_model().objects.get(username="new-customer")
        self.assertRedirects(response, reverse("accounts:bookings"))
        self.assertEqual(user.email, "an@example.com")
        self.assertEqual(user.phone, "0944444444")
        self.assertFalse(user.is_staff)
        self.assertIn("_auth_user_id", self.client.session)

    def test_duplicate_email_is_rejected(self):
        get_user_model().objects.create_user(
            username="existing",
            email="an@example.com",
            password="Strong-test-password-2026",
        )

        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new-customer",
                "email": "AN@example.com",
                "phone": "0944444444",
                "password1": "Strong-test-password-2026",
                "password2": "Strong-test-password-2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username="new-customer").exists()
        )
        self.assertContains(response, "Email này đã được sử dụng.")
