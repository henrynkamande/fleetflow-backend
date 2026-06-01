"""Read-only helpers describing outbound email configuration."""
from django.conf import settings


def describe_email_backend() -> str:
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if getattr(settings, 'EMAIL_CONSOLE', False):
        return 'console (EMAIL_CONSOLE=true; mail is printed, not delivered)'
    if backend.endswith('console.EmailBackend'):
        return 'console (DEBUG; mail is printed in the API process logs)'
    sendgrid_key = getattr(settings, 'SENDGRID_API_KEY', '') or ''
    if sendgrid_key and 'sendgrid' in (getattr(settings, 'EMAIL_HOST', '') or '').lower():
        return f'SendGrid SMTP (from {settings.DEFAULT_FROM_EMAIL})'
    host = getattr(settings, 'EMAIL_HOST', '') or 'unknown'
    return f'SMTP {host} (from {settings.DEFAULT_FROM_EMAIL})'


def delivery_is_real_inbox() -> bool:
    """False when mail only goes to the process console."""
    if getattr(settings, 'EMAIL_CONSOLE', False):
        return False
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    return not backend.endswith('console.EmailBackend')
