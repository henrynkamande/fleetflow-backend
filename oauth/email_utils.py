"""Outbound auth email helpers."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from fleetflow.background import run_after_commit

logger = logging.getLogger(__name__)


def schedule_auth_email(subject: str, message: str, recipient: str) -> None:
    """Send mail in a background thread so HTTP workers are not blocked on SMTP."""
    if not getattr(settings, 'EMAIL_DELIVERY_ENABLED', True):
        logger.info('Auth email delivery disabled; skipped scheduled email to %s (%s)', recipient, subject)
        return

    logger.info('Scheduling auth email to %s (%s)', recipient, subject)

    run_after_commit(
        f'auth-email-{recipient[:40]}',
        deliver_auth_email,
        subject,
        message,
        recipient,
    )


def deliver_auth_email(subject: str, message: str, recipient: str) -> bool:
    """Send transactional mail. Returns False if delivery did not succeed."""
    if not getattr(settings, 'EMAIL_DELIVERY_ENABLED', True):
        logger.info('Auth email delivery disabled; skipped email to %s (%s)', recipient, subject)
        return True

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
