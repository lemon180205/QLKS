import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import BadHeaderError, send_mail

logger = logging.getLogger(__name__)


def send_booking_email(booking, subject, message):
    if not booking.email:
        return False

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.email],
            fail_silently=False,
        )
    except (BadHeaderError, OSError, SMTPException):
        logger.exception(
            "Could not send booking email for reference %s",
            booking.reference_code,
        )
        return False
    return True
