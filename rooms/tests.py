from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    BookingCounterPayment,
    BookingPayment,
    BookingRequest,
    BookingServiceUsage,
    Room,
    RoomType,
    Service,
)
from .operations import check_in_booking, check_out_booking


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

    def create_checked_in_booking(self):
        return BookingRequest.objects.create(
            room_type=self.room_type,
            assigned_room=Room.objects.filter(
                room_type=self.room_type,
                status=Room.Status.READY,
            ).first(),
            guest_name="Guest checking out",
            phone="0933333333",
            check_in=self.check_in,
            check_out=self.check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CHECKED_IN,
        )

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

    def test_receptionist_records_service_usage_at_current_price(self):
        booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Guest using hotel services",
            phone="0933333333",
            check_in=self.check_in,
            check_out=self.check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CHECKED_IN,
        )
        service = Service.objects.get(name="Bữa sáng")
        original_price = service.price
        post_data = self.booking_data(status=BookingRequest.Status.CHECKED_IN)
        post_data.update(
            {
                "service_usages-TOTAL_FORMS": "1",
                "service_usages-INITIAL_FORMS": "0",
                "service_usages-MIN_NUM_FORMS": "0",
                "service_usages-MAX_NUM_FORMS": "1000",
                "service_usages-0-service": str(service.pk),
                "service_usages-0-quantity": "2",
            }
        )

        response = self.client.post(
            reverse("admin:rooms_bookingrequest_change", args=[booking.pk]),
            post_data,
        )

        usage = BookingServiceUsage.objects.get(booking=booking)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usage.quantity, 2)
        self.assertEqual(usage.unit_price, original_price)

        service.price += 10000
        service.save(update_fields=("price",))
        usage.refresh_from_db()
        self.assertEqual(usage.unit_price, original_price)

    def test_receptionist_cannot_record_services_before_check_in(self):
        booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Guest not checked in",
            phone="0933333333",
            check_in=self.check_in,
            check_out=self.check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CONFIRMED,
        )
        service = Service.objects.get(name="Bữa sáng")
        post_data = self.booking_data(status=BookingRequest.Status.CONFIRMED)
        post_data.update(
            {
                "service_usages-TOTAL_FORMS": "1",
                "service_usages-INITIAL_FORMS": "0",
                "service_usages-MIN_NUM_FORMS": "0",
                "service_usages-MAX_NUM_FORMS": "1000",
                "service_usages-0-service": str(service.pk),
                "service_usages-0-quantity": "1",
            }
        )

        response = self.client.post(
            reverse("admin:rooms_bookingrequest_change", args=[booking.pk]),
            post_data,
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(BookingServiceUsage.objects.exists())

    def test_service_history_does_not_block_editing_checked_out_booking(self):
        booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Guest already checked out",
            phone="0933333333",
            check_in=self.check_in,
            check_out=self.check_in + timedelta(days=2),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CHECKED_OUT,
        )
        service = Service.objects.get(name="Bữa sáng")
        usage = BookingServiceUsage.objects.create(
            booking=booking,
            service=service,
            quantity=1,
            unit_price=service.price,
        )
        post_data = self.booking_data(
            status=BookingRequest.Status.CHECKED_OUT,
            guest_name="Updated guest details",
        )
        post_data.update(
            {
                "service_usages-TOTAL_FORMS": "1",
                "service_usages-INITIAL_FORMS": "1",
                "service_usages-MIN_NUM_FORMS": "0",
                "service_usages-MAX_NUM_FORMS": "1000",
                "service_usages-0-id": str(usage.pk),
                "service_usages-0-booking": str(booking.pk),
            }
        )

        response = self.client.post(
            reverse("admin:rooms_bookingrequest_change", args=[booking.pk]),
            post_data,
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(booking.guest_name, "Updated guest details")

    def test_checkout_page_shows_momo_service_and_remaining_amounts(self):
        booking = self.create_checked_in_booking()
        service = Service.objects.get(name="Bữa sáng")
        BookingServiceUsage.objects.create(
            booking=booking,
            service=service,
            quantity=2,
            unit_price=service.price,
        )
        momo_amount = booking.total_price - 1000
        BookingPayment.objects.create(
            booking=booking,
            amount=momo_amount,
            status=BookingPayment.Status.PAID,
        )

        response = self.client.get(
            reverse("admin:rooms_bookingrequest_checkout", args=[booking.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{booking.total_price:.0f} VNĐ")
        self.assertContains(response, f"{service.price * 2:.0f} VNĐ")
        self.assertContains(response, f"{momo_amount:.0f} VNĐ")
        self.assertContains(
            response,
            f"{service.price * 2 + 1000:.0f} VNĐ",
        )

    def test_checkout_collects_balance_once_and_checks_out_room(self):
        booking = self.create_checked_in_booking()
        service = Service.objects.get(name="Bữa sáng")
        BookingServiceUsage.objects.create(
            booking=booking,
            service=service,
            quantity=2,
            unit_price=service.price,
        )
        BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status=BookingPayment.Status.PAID,
        )
        checkout_url = reverse(
            "admin:rooms_bookingrequest_checkout",
            args=[booking.pk],
        )
        post_data = {
            "expected_amount": str(service.price * 2),
            "payment_method": BookingCounterPayment.Method.CASH,
        }

        response = self.client.post(checkout_url, post_data)
        payment = BookingCounterPayment.objects.get(booking=booking)
        booking.refresh_from_db()
        booking.assigned_room.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.amount, service.price * 2)
        self.assertEqual(payment.method, BookingCounterPayment.Method.CASH)
        self.assertEqual(payment.received_by, self.staff)
        self.assertIsNotNone(payment.received_at)
        self.assertEqual(booking.status, BookingRequest.Status.CHECKED_OUT)
        self.assertEqual(booking.payment_status, BookingRequest.PaymentStatus.PAID)
        self.assertEqual(booking.assigned_room.status, Room.Status.CLEANING)

        duplicate_response = self.client.post(checkout_url, post_data)

        self.assertEqual(duplicate_response.status_code, 302)
        self.assertEqual(BookingCounterPayment.objects.filter(booking=booking).count(), 1)

    def test_counter_collection_splits_unpaid_room_and_service_revenue(self):
        booking = self.create_checked_in_booking()
        service = Service.objects.get(name="Bữa sáng")
        BookingServiceUsage.objects.create(
            booking=booking,
            service=service,
            quantity=1,
            unit_price=service.price,
        )
        checkout_url = reverse(
            "admin:rooms_bookingrequest_checkout",
            args=[booking.pk],
        )

        response = self.client.post(
            checkout_url,
            {
                "expected_amount": str(booking.total_price + service.price),
                "payment_method": BookingCounterPayment.Method.BANK_TRANSFER,
            },
        )

        payment = BookingCounterPayment.objects.get(booking=booking)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.room_amount, booking.total_price)
        self.assertEqual(payment.service_amount, service.price)
        self.assertEqual(
            payment.amount,
            payment.room_amount + payment.service_amount,
        )

    def test_checkout_waits_for_pending_momo_transaction(self):
        booking = self.create_checked_in_booking()
        BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status=BookingPayment.Status.PENDING,
        )
        checkout_url = reverse(
            "admin:rooms_bookingrequest_checkout",
            args=[booking.pk],
        )

        response = self.client.get(checkout_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hãy đợi giao dịch hoàn tất")
        self.client.post(
            checkout_url,
            {
                "expected_amount": str(booking.total_price),
                "payment_method": BookingCounterPayment.Method.CASH,
            },
        )
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.Status.CHECKED_IN)
        self.assertFalse(BookingCounterPayment.objects.exists())

    def test_fully_paid_booking_checks_out_without_counter_payment(self):
        booking = self.create_checked_in_booking()
        BookingPayment.objects.create(
            booking=booking,
            amount=booking.total_price,
            status=BookingPayment.Status.PAID,
        )
        checkout_url = reverse(
            "admin:rooms_bookingrequest_checkout",
            args=[booking.pk],
        )

        response = self.client.post(
            checkout_url,
            {"expected_amount": "0", "payment_method": ""},
        )

        booking.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(booking.status, BookingRequest.Status.CHECKED_OUT)
        self.assertFalse(BookingCounterPayment.objects.exists())

    def test_checkout_refreshes_if_balance_changed_since_page_load(self):
        booking = self.create_checked_in_booking()
        checkout_url = reverse(
            "admin:rooms_bookingrequest_checkout",
            args=[booking.pk],
        )
        self.client.get(checkout_url)
        BookingPayment.objects.create(
            booking=booking,
            amount=1000,
            status=BookingPayment.Status.PAID,
        )

        response = self.client.post(
            checkout_url,
            {
                "expected_amount": str(booking.total_price),
                "payment_method": BookingCounterPayment.Method.CASH,
            },
        )

        booking.refresh_from_db()
        self.assertRedirects(response, checkout_url, fetch_redirect_response=False)
        self.assertEqual(booking.status, BookingRequest.Status.CHECKED_IN)
        self.assertFalse(BookingCounterPayment.objects.exists())

    def test_monthly_revenue_uses_receipt_time_and_excludes_failed_payments(self):
        room_booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Room paid in October",
            phone="0933333333",
            check_in=date(2026, 10, 30),
            check_out=date(2026, 11, 1),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CHECKED_OUT,
        )
        momo_paid_at = timezone.make_aware(datetime(2026, 10, 31, 23, 30))
        BookingPayment.objects.create(
            booking=room_booking,
            amount=room_booking.total_price,
            status=BookingPayment.Status.PAID,
            paid_at=momo_paid_at,
        )

        service = Service.objects.get(name="Bữa sáng")
        service_total = service.price * 2
        BookingServiceUsage.objects.create(
            booking=room_booking,
            service=service,
            quantity=2,
            unit_price=service.price,
        )
        counter_payment = BookingCounterPayment.objects.create(
            booking=room_booking,
            amount=service_total,
            room_amount=0,
            service_amount=service_total,
            method=BookingCounterPayment.Method.CASH,
            received_by=self.staff,
        )
        counter_received_at = timezone.make_aware(
            datetime(2026, 11, 1, 0, 30)
        )
        BookingCounterPayment.objects.filter(pk=counter_payment.pk).update(
            received_at=counter_received_at
        )

        failed_booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Failed MoMo booking",
            phone="0933333334",
            check_in=date(2026, 11, 10),
            check_out=date(2026, 11, 12),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CONFIRMED,
        )
        failed_payment = BookingPayment.objects.create(
            booking=failed_booking,
            amount=failed_booking.total_price,
            status=BookingPayment.Status.FAILED,
            failed_at=timezone.make_aware(datetime(2026, 11, 5, 12)),
        )
        BookingPayment.objects.filter(pk=failed_payment.pk).update(
            created_at=timezone.make_aware(datetime(2026, 10, 31, 12))
        )

        unpaid_booking = BookingRequest.objects.create(
            room_type=self.room_type,
            guest_name="Unpaid booking",
            phone="0933333335",
            check_in=date(2026, 11, 15),
            check_out=date(2026, 11, 17),
            guest_count=2,
            nightly_rate=self.room_type.price_per_night,
            total_price=self.room_type.price_per_night * 2,
            status=BookingRequest.Status.CONFIRMED,
        )
        report_url = reverse("admin:rooms_bookingrequest_monthly_revenue")
        changelist_response = self.client.get(
            reverse("admin:rooms_bookingrequest_changelist")
        )
        self.assertEqual(changelist_response.status_code, 200)
        self.assertContains(changelist_response, report_url)

        november_response = self.client.get(
            report_url,
            {"month": "11", "year": "2026"},
        )
        november = november_response.context["report"]
        self.assertEqual(november["room_revenue"], 0)
        self.assertEqual(november["service_revenue"], service_total)
        self.assertEqual(november["total_revenue"], service_total)
        self.assertEqual(november["counter_revenue"], service_total)
        self.assertEqual(len(november["failed_transactions"]), 1)
        self.assertEqual(
            {item["booking"].pk for item in november["unpaid_bookings"]},
            {failed_booking.pk, unpaid_booking.pk},
        )

        october_response = self.client.get(
            report_url,
            {"month": "10", "year": "2026"},
        )
        october = october_response.context["report"]
        self.assertEqual(october["room_revenue"], room_booking.total_price)
        self.assertEqual(october["service_revenue"], 0)
        self.assertEqual(october["total_revenue"], room_booking.total_price)
        self.assertFalse(october["failed_transactions"])


class BookingOperationTests(TestCase):
    def setUp(self):
        self.room_type = RoomType.objects.get(name="Phòng đôi tiêu chuẩn")
        self.room = Room.objects.create(
            number="991",
            room_type=self.room_type,
            status=Room.Status.READY,
        )
        self.today = timezone.localdate()

    def create_booking(self, status, **overrides):
        values = {
            "room_type": self.room_type,
            "assigned_room": self.room,
            "guest_name": "Operations test guest",
            "phone": "0900000000",
            "check_in": self.today,
            "check_out": self.today + timedelta(days=2),
            "guest_count": 2,
            "nightly_rate": self.room_type.price_per_night,
            "total_price": self.room_type.price_per_night * 2,
            "status": status,
        }
        values.update(overrides)
        return BookingRequest.objects.create(**values)

    def test_check_in_records_time_and_changes_confirmed_booking(self):
        booking = self.create_booking(BookingRequest.Status.CONFIRMED)

        checked_in = check_in_booking(booking.pk)

        self.assertEqual(checked_in.status, BookingRequest.Status.CHECKED_IN)
        self.assertIsNotNone(checked_in.actual_check_in)

    def test_check_in_rejects_unconfirmed_booking(self):
        booking = self.create_booking(BookingRequest.Status.PENDING)

        with self.assertRaises(ValidationError):
            check_in_booking(booking.pk)

    def test_check_in_rejects_room_reserved_by_payment_in_progress(self):
        booking = self.create_booking(BookingRequest.Status.CONFIRMED)
        self.create_booking(
            BookingRequest.Status.PENDING,
            guest_name="Guest paying for the same room",
            payment_status=BookingRequest.PaymentStatus.PENDING,
        )

        with self.assertRaises(ValidationError):
            check_in_booking(booking.pk)

    def test_check_out_collects_once_and_marks_room_for_cleaning(self):
        booking = self.create_booking(BookingRequest.Status.CHECKED_IN)

        checked_out = check_out_booking(
            booking.pk,
            payment_method=BookingCounterPayment.Method.CASH,
            expected_amount=booking.total_price,
        )

        self.room.refresh_from_db()
        self.assertEqual(checked_out.status, BookingRequest.Status.CHECKED_OUT)
        self.assertIsNotNone(checked_out.actual_check_out)
        self.assertEqual(self.room.status, Room.Status.CLEANING)
        self.assertEqual(
            BookingCounterPayment.objects.filter(booking=booking).count(),
            1,
        )
        with self.assertRaises(ValidationError):
            check_out_booking(
                booking.pk,
                payment_method=BookingCounterPayment.Method.CASH,
            )
        self.assertEqual(
            BookingCounterPayment.objects.filter(booking=booking).count(),
            1,
        )
