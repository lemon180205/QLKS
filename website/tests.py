import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rooms.models import BookingPayment, BookingRequest, RoomType


def momo_signature(data, fields):
    raw = "&".join(
        f"{key}={settings.MOMO_ACCESS_KEY if key == 'accessKey' else data.get(key, '')}"
        for key in fields
    )
    return hmac.new(
        settings.MOMO_SECRET_KEY.encode(),
        raw.encode(),
        hashlib.sha256,
    ).hexdigest()


class FakeGatewayResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.data


class RoomCatalogTests(TestCase):
    def test_room_list_displays_seeded_types_inventory_and_services(self):
        response = self.client.get(reverse("website:room_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "check_in=None")
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


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class BookingRequestTests(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")
        self.check_in = timezone.localdate() + timedelta(days=14)
        self.check_out = self.check_in + timedelta(days=3)
        self.url = reverse(
            "website:booking_request",
            args=[self.room_type.pk],
        )
        self.customer = get_user_model().objects.create_user(
            username="guest",
            email="guest@example.com",
            phone="0900000000",
            password="test-password",
        )
        self.client.force_login(self.customer)

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
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.nightly_rate, self.room_type.price_per_night)
        self.assertEqual(
            booking.total_price,
            self.room_type.price_per_night * 3,
        )
        self.assertContains(response, str(booking.reference_code))
        self.assertContains(response, "Đặt phòng của tôi")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(booking.reference_code), mail.outbox[0].body)

    def test_booking_requires_customer_account(self):
        self.client.logout()

        response = self.client.post(self.url, self.booking_data())

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
        )
        self.assertEqual(BookingRequest.objects.count(), 0)

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


class CustomerAccountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="customer",
            email="customer@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")

    def create_booking(self, **overrides):
        check_in = timezone.localdate() + timedelta(days=12)
        values = {
            "room_type": self.room_type,
            "guest_name": "Customer",
            "email": "customer@example.com",
            "phone": "0911111111",
            "customer": self.user,
            "check_in": check_in,
            "check_out": check_in + timedelta(days=2),
            "guest_count": 2,
            "nightly_rate": self.room_type.price_per_night,
            "total_price": self.room_type.price_per_night * 2,
        }
        values.update(overrides)
        return BookingRequest.objects.create(**values)

    def test_account_only_lists_own_bookings(self):
        own_booking = self.create_booking()
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="test-password",
        )
        other_booking = self.create_booking(
            customer=other_user,
            guest_name="Other",
        )

        response = self.client.get(reverse("accounts:bookings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(own_booking.reference_code))
        self.assertNotContains(response, str(other_booking.reference_code))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_customer_can_cancel_unpaid_booking(self):
        booking = self.create_booking()

        response = self.client.post(
            reverse("accounts:cancel_booking", args=[booking.pk])
        )

        booking.refresh_from_db()
        self.assertRedirects(response, reverse("accounts:bookings"))
        self.assertEqual(booking.status, BookingRequest.Status.CANCELLED)
        self.assertEqual(len(mail.outbox), 1)

    def test_customer_cannot_cancel_paid_booking(self):
        booking = self.create_booking(
            payment_status=BookingRequest.PaymentStatus.PAID,
        )

        self.client.post(reverse("accounts:cancel_booking", args=[booking.pk]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)

    def test_customer_cannot_cancel_booking_with_payment_in_progress(self):
        booking = self.create_booking(
            payment_status=BookingRequest.PaymentStatus.PENDING,
        )
        BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
        )

        self.client.post(reverse("accounts:cancel_booking", args=[booking.pk]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    MOMO_PARTNER_CODE="TEST_PARTNER",
    MOMO_ACCESS_KEY="test-access-key",
    MOMO_SECRET_KEY="test-secret-key",
    MOMO_ENDPOINT="https://test-payment.momo.vn/v2/gateway/api/create",
    MOMO_REDIRECT_URL="https://hotel.example.test/thanh-toan/momo/return/",
    MOMO_IPN_URL="https://hotel.example.test/thanh-toan/momo/ipn/",
)
class MomoPaymentTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username="momo-customer",
            email="momo@example.com",
            password="test-password",
        )
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")
        check_in = timezone.localdate() + timedelta(days=18)
        self.booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="MoMo Customer",
            email="momo@example.com",
            phone="0922222222",
            customer=self.customer,
            check_in=check_in,
            check_out=check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
        )

    def notification_payload(self, **overrides):
        payload = {
            "partnerCode": settings.MOMO_PARTNER_CODE,
            "orderId": str(self.payment.order_id),
            "requestId": str(self.payment.request_id),
            "amount": int(self.payment.amount),
            "orderInfo": "Hotel booking",
            "orderType": "momo_wallet",
            "transId": "123456789",
            "resultCode": 0,
            "message": "Successful.",
            "payType": "qr",
            "responseTime": 1790000000000,
            "extraData": "",
        }
        payload.update(overrides)
        payload["signature"] = momo_signature(
            payload,
            (
                "accessKey",
                "amount",
                "extraData",
                "message",
                "orderId",
                "orderInfo",
                "orderType",
                "partnerCode",
                "payType",
                "requestId",
                "responseTime",
                "resultCode",
                "transId",
            ),
        )
        return payload

    def set_payment(self):
        self.payment = BookingPayment.objects.create(
            booking=self.booking,
            amount=self.booking.total_price,
        )

    def test_payment_request_uses_signed_gateway_payload(self):
        from .payments import create_momo_payment

        self.set_payment()
        response_data = {
            "partnerCode": settings.MOMO_PARTNER_CODE,
            "requestId": str(self.payment.request_id),
            "orderId": str(self.payment.order_id),
            "amount": int(self.payment.amount),
            "orderInfo": "Hotel booking",
            "orderType": "momo_wallet",
            "transId": 0,
            "resultCode": 0,
            "message": "Successful.",
            "payType": "",
            "responseTime": 1790000000000,
            "extraData": "",
            "payUrl": "https://test-payment.momo.vn/pay/example",
        }
        response_data["signature"] = momo_signature(
            response_data,
            (
                "accessKey",
                "amount",
                "extraData",
                "message",
                "orderId",
                "orderInfo",
                "orderType",
                "partnerCode",
                "payType",
                "requestId",
                "responseTime",
                "resultCode",
                "transId",
            ),
        )

        with patch(
            "website.payments.urlopen",
            return_value=FakeGatewayResponse(response_data),
        ) as gateway:
            pay_url = create_momo_payment(self.payment)

        request_payload = json.loads(gateway.call_args.args[0].data)
        self.assertEqual(pay_url, response_data["payUrl"])
        self.assertEqual(request_payload["amount"], int(self.payment.amount))
        self.assertEqual(
            request_payload["signature"],
            momo_signature(
                request_payload,
                (
                    "accessKey",
                    "amount",
                    "extraData",
                    "ipnUrl",
                    "orderId",
                    "orderInfo",
                    "partnerCode",
                    "redirectUrl",
                    "requestId",
                    "requestType",
                ),
            ),
        )

    def test_valid_signed_ipn_confirms_booking_once(self):
        self.set_payment()
        payload = self.notification_payload()

        response = self.client.post(
            reverse("website:momo_ipn"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        duplicate_response = self.client.post(
            reverse("website:momo_ipn"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(self.payment.status, BookingPayment.Status.PAID)
        self.assertEqual(
            self.booking.payment_status,
            BookingRequest.PaymentStatus.PAID,
        )
        self.assertEqual(self.booking.status, BookingRequest.Status.CONFIRMED)
        self.assertEqual(len(mail.outbox), 1)

    def test_invalid_or_mismatched_ipn_does_not_confirm_booking(self):
        self.set_payment()
        payload = self.notification_payload(amount=int(self.payment.amount) + 1)
        malformed_signature_payload = self.notification_payload()
        malformed_signature_payload["signature"] = ["not-a-signature"]

        malformed_response = self.client.post(
            reverse("website:momo_ipn"),
            data=json.dumps(malformed_signature_payload),
            content_type="application/json",
        )
        response = self.client.post(
            reverse("website:momo_ipn"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(malformed_response.status_code, 400)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.payment.status, BookingPayment.Status.PENDING)
        self.assertEqual(
            self.booking.payment_status,
            BookingRequest.PaymentStatus.UNPAID,
        )
