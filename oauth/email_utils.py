"""Outbound auth email helpers."""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection

logger = logging.getLogger(__name__)


def schedule_auth_email(subject: str, message: str, recipient: str) -> None:
    """Send mail in a background thread so HTTP workers are not blocked on SMTP."""

    def _send() -> None:
        try:
            deliver_auth_email(subject, message, recipient)
        finally:
            connection.close()

    threading.Thread(
        target=_send,
        name=f'auth-email-{recipient[:40]}',
        daemon=True,
    ).start()


def deliver_auth_email(subject: str, message: str, recipient: str) -> bool:
    """Send transactional mail. Returns False if delivery did not succeed."""
    try:
        sent_count = send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        if sent_count < 1:
            logger.error(
                'Auth email not delivered to %s (%s). Check SENDGRID_API_KEY and DEFAULT_FROM_EMAIL.',
                recipient,
                subject,
            )
            return False
        logger.info('Auth email sent to %s (%s)', recipient, subject)
        return True
    except Exception as exc:
        logger.exception('Auth email failed to %s: %s', recipient, exc)
        return False
