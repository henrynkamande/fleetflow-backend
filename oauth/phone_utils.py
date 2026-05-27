"""Normalize phone numbers for storage and duplicate checks."""
from __future__ import annotations


def normalize_phone_number(value: str) -> str:
    """Strip formatting; keep a leading + and digits only."""
    if value is None:
        return ''
    raw = str(value).strip()
    if not raw:
        return ''
    compact = ''.join(raw.split())
    if compact.startswith('+'):
        digits = ''.join(c for c in compact[1:] if c.isdigit())
        return f'+{digits}' if digits else compact
    digits = ''.join(c for c in compact if c.isdigit())
    if not digits:
        return compact
    if digits.startswith('0') and len(digits) >= 10:
        return f'+254{digits[1:]}'
    if digits.startswith('254') and len(digits) >= 12:
        return f'+{digits}'
    return f'+{digits}' if len(digits) >= 10 else digits


def phone_number_lookup_variants(value: str) -> list[str]:
    """Variants that should match the same logical phone in the DB."""
    normalized = normalize_phone_number(value)
    variants: set[str] = {normalized, value.strip()}
    digits = ''.join(c for c in normalized if c.isdigit())
    if digits:
        variants.add(digits)
        if digits.startswith('254') and len(digits) > 3:
            variants.add('0' + digits[3:])
            variants.add('+' + digits)
        elif digits.startswith('0') and len(digits) >= 10:
            variants.add('+254' + digits[1:])
            variants.add('254' + digits[1:])
    return [v for v in variants if v]
