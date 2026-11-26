from datetime import datetime
from decimal import Decimal

from django.db.models import Prefetch, Sum
from django.utils import timezone

from .models import (
    BookingCounterPayment,
    BookingPayment,
    BookingRequest,
    BookingServiceUsage,
)


def build_monthly_revenue_report(year, month):
    next_month_year = year + (month // 12)
    next_month = month % 12 + 1
    period_start = timezone.make_aware(datetime(year, month, 1))
    period_end = timezone.make_aware(
        datetime(next_month_year, next_month, 1)
    )

    momo_payments = BookingPayment.objects.filter(
        status=BookingPayment.Status.PAID,
        paid_at__gte=period_start,
        paid_at__lt=period_end,
    )
    momo_revenue = momo_payments.aggregate(total=Sum("amount"))["total"] or Decimal(
        "0"
    )

    counter_payments = BookingCounterPayment.objects.filter(
        received_at__gte=period_start,
        received_at__lt=period_end,
    )
    counter_totals = counter_payments.aggregate(
        room=Sum("room_amount"),
        services=Sum("service_amount"),
        total=Sum("amount"),
    )
    counter_room_revenue = counter_totals["room"] or Decimal("0")
    service_revenue = counter_totals["services"] or Decimal("0")
    room_revenue = momo_revenue + counter_room_revenue

    failed_transactions = (
        BookingPayment.objects.filter(
            status=BookingPayment.Status.FAILED,
            failed_at__gte=period_start,
            failed_at__lt=period_end,
        )
        .select_related("booking")
        .order_by("created_at")
    )

    unpaid_bookings = []
    bookings = (
        BookingRequest.objects.exclude(status=BookingRequest.Status.CANCELLED)
        .select_related("assigned_room", "counter_payment")
        .prefetch_related(
            Prefetch(
                "service_usages",
                queryset=BookingServiceUsage.objects.only(
                    "booking_id",
                    "quantity",
                    "unit_price",
                ),
            ),
            Prefetch(
                "payment_attempts",
                queryset=BookingPayment.objects.filter(
                    status=BookingPayment.Status.PAID
                ).only("booking_id", "amount"),
                to_attr="successful_payment_attempts",
            ),
        )
    )
    for booking in bookings:
        service_total = sum(
            (
                usage.unit_price * usage.quantity
                for usage in booking.service_usages.all()
            ),
            Decimal("0"),
        )
        momo_paid = sum(
            (
                payment.amount
                for payment in booking.successful_payment_attempts
            ),
            Decimal("0"),
        )
        counter_payment = getattr(booking, "counter_payment", None)
        counter_paid = counter_payment.amount if counter_payment else Decimal("0")
        amount_due = max(
            booking.total_price + service_total - momo_paid - counter_paid,
            Decimal("0"),
        )
        if amount_due:
            unpaid_bookings.append(
                {
                    "booking": booking,
                    "amount_due": amount_due,
                }
            )

    unpaid_bookings.sort(
        key=lambda item: (-item["amount_due"], item["booking"].check_in)
    )
    return {
        "year": year,
        "month": month,
        "room_revenue": room_revenue,
        "service_revenue": service_revenue,
        "total_revenue": room_revenue + service_revenue,
        "momo_revenue": momo_revenue,
        "counter_revenue": counter_totals["total"] or Decimal("0"),
        "failed_transactions": failed_transactions,
        "unpaid_bookings": unpaid_bookings,
    }
