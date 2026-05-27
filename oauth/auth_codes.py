"""Email OTP / reset code helpers (6-digit, 30 min expiry, 60s resend cooldown)."""
from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import EmailAuthCode

CODE_LENGTH = 6
CODE_EXPIRY_SECONDS = 1800
RESEND_COOLDOWN_SECONDS = 60
MAX_VERIFY_ATTEMPTS = 5


def generate_numeric_code(length: int = CODE_LENGTH) -> str:
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def issue_code(user, purpose: str) -> str:
    plain = generate_numeric_code()
    EmailAuthCode.objects.update_or_create(
        user=user,
        purpose=purpose,
        defaults={
            'code_hash': make_password(plain),
            'expires_at': timezone.now() + timedelta(seconds=CODE_EXPIRY_SECONDS),
            'sent_at': timezone.now(),
            'attempts': 0,
        },
    )
    return plain


def resend_cooldown_remaining(user, purpose: str) -> int:
    try:
        record = EmailAuthCode.objects.get(user=user, purpose=purpose)
    except EmailAuthCode.DoesNotExist:
        return 0
    elapsed = (timezone.now() - record.sent_at).total_seconds()
    if elapsed >= RESEND_COOLDOWN_SECONDS:
        return 0
    return int(RESEND_COOLDOWN_SECONDS - elapsed)


def can_resend(user, purpose: str) -> bool:
    return resend_cooldown_remaining(user, purpose) == 0


def verify_code(user, purpose: str, plain_code: str) -> tuple[bool, str | None]:
    try:
        record = EmailAuthCode.objects.get(user=user, purpose=purpose)
    except EmailAuthCode.DoesNotExist:
        return False, 'No verification code found. Please request a new one.'

    if record.is_expired:
        return False, 'This code has expired. Please request a new one.'

    if record.attempts >= MAX_VERIFY_ATTEMPTS:
        return False, 'Too many failed attempts. Please request a new code.'

    if not check_password(plain_code.strip(), record.code_hash):
        record.attempts += 1
        record.save(update_fields=['attempts'])
        remaining = max(0, MAX_VERIFY_ATTEMPTS - record.attempts)
        return False, f'Invalid code. {remaining} attempts remaining.'

    return True, None


def clear_code(user, purpose: str) -> None:
    EmailAuthCode.objects.filter(user=user, purpose=purpose).delete()
