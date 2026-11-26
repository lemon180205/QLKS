from decimal import Decimal

import django.core.validators
from django.db import migrations, models
from django.db.models import Sum


def split_existing_counter_payments(apps, schema_editor):
    database = schema_editor.connection.alias
    CounterPayment = apps.get_model("rooms", "BookingCounterPayment")
    BookingPayment = apps.get_model("rooms", "BookingPayment")

    payments = CounterPayment.objects.using(database).select_related("booking")
    for payment in payments.iterator():
        momo_paid = (
            BookingPayment.objects.using(database)
            .filter(
                booking_id=payment.booking_id,
                status="paid",
                paid_at__lte=payment.received_at,
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        unpaid_room = max(payment.booking.total_price - momo_paid, Decimal("0"))
        payment.room_amount = min(payment.amount, unpaid_room)
        payment.service_amount = payment.amount - payment.room_amount
        payment.save(
            using=database,
            update_fields=("room_amount", "service_amount"),
        )


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0010_booking_counter_payment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingcounterpayment",
            name="amount",
            field=models.DecimalField(
                decimal_places=0,
                max_digits=24,
                verbose_name="Số tiền đã thu (VNĐ)",
            ),
        ),
        migrations.AddField(
            model_name="bookingcounterpayment",
            name="room_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=24,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Tiền phòng thu tại quầy (VNĐ)",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="bookingcounterpayment",
            name="service_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=24,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Tiền dịch vụ thu tại quầy (VNĐ)",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            split_existing_counter_payments,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="bookingcounterpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("room_amount__gte", 0),
                    ("service_amount__gte", 0),
                ),
                name="booking_counter_payment_parts_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="bookingcounterpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("amount", models.F("room_amount") + models.F("service_amount"))
                ),
                name="booking_counter_payment_parts_match_amount",
            ),
        ),
    ]
