"""Outbound auth email helpers."""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def deliver_auth_email(subject: str, message: str, recipient: str) -> bool:
    """Send transactional mail; surfaces errors when DEBUG is on."""
    try:
        send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=not settings.DEBUG,
        )
        logger.info('Auth email sent to %s (%s)', recipient, subject)
        return True
    except Exception as exc:
        logger.exception('Auth email failed to %s: %s', recipient, exc)
        return False
