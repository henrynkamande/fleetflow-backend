import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """Requires upper, lower, digit, and special character."""

    SPECIAL = re.compile(r'[!@#$%^&*(),.?":{}|<>_\-\[\]\\;/+=`~]')

    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append(_('Password must include at least one uppercase letter.'))
        if not re.search(r'[a-z]', password):
            errors.append(_('Password must include at least one lowercase letter.'))
        if not re.search(r'\d', password):
            errors.append(_('Password must include at least one digit.'))
        if not self.SPECIAL.search(password):
            errors.append(_('Password must include at least one special character.'))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            'Your password must be at least 8 characters and include uppercase, '
            'lowercase, a digit, and a special character.'
        )
