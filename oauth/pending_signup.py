"""OTP helpers for fleet-owner signup before a User row exists."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils import timezone

from . import auth_codes
from .models import PendingFleetOwnerSignup

CODE_EXPIRY_SECONDS = auth_codes.CODE_EXPIRY_SECONDS
RESEND_COOLDOWN_SECONDS = auth_codes.RESEND_COOLDOWN_SECONDS
MAX_VERIFY_ATTEMPTS = auth_codes.MAX_VERIFY_ATTEMPTS
_HMAC_PREFIX = 'hmac$'


def _hash_code(plain_code: str) -> str:
    digest = salted_hmac(
        'pending-fleet-owner-signup-code',
        plain_code.strip(),
    ).hexdigest()
    return f'{_HMAC_PREFIX}{digest}'


def _check_code(plain_code: str, encoded: str) -> bool:
    if encoded.startswith(_HMAC_PREFIX):
        return constant_time_compare(_hash_code(plain_code), encoded)
    # Backward compatibility for pending signups issued before the fast hash.
    return check_password(plain_code.strip(), encoded)


def issue_code(pending: PendingFleetOwnerSignup) -> str:
    plain = auth_codes.generate_numeric_code()
    pending.code_hash = _hash_code(plain)
    pending.code_expires_at = timezone.now() + timedelta(seconds=CODE_EXPIRY_SECONDS)
    pending.code_sent_at = timezone.now()
    pending.code_attempts = 0
    pending.save(
        update_fields=[
            'code_hash',
            'code_expires_at',
            'code_sent_at',
            'code_attempts',
            'updated_at',
        ],
    )
    return plain


def resend_cooldown_remaining(pending: PendingFleetOwnerSignup) -> int:
    if not pending.code_sent_at:
        return 0
    elapsed = (timezone.now() - pending.code_sent_at).total_seconds()
    if elapsed >= RESEND_COOLDOWN_SECONDS:
        return 0
    return int(RESEND_COOLDOWN_SECONDS - elapsed)


def can_resend(pending: PendingFleetOwnerSignup) -> bool:
    return resend_cooldown_remaining(pending) == 0


def verify_code(pending: PendingFleetOwnerSignup, plain_code: str) -> tuple[bool, str | None]:
    if not pending.code_hash:
        return False, 'No verification code found. Please request a new one.'
    if pending.is_code_expired:
        return False, 'This code has expired. Please request a new one.'
    if pending.code_attempts >= MAX_VERIFY_ATTEMPTS:
        return False, 'Too many failed attempts. Please request a new code.'
    if not _check_code(plain_code, pending.code_hash):
        pending.code_attempts += 1
        pending.save(update_fields=['code_attempts', 'updated_at'])
        remaining = max(0, MAX_VERIFY_ATTEMPTS - pending.code_attempts)
        return False, f'Invalid code. {remaining} attempts remaining.'
    return True, None
