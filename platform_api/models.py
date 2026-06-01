import uuid

from django.conf import settings
from django.db import models


class PlatformSystemExpense(models.Model):
    class Category(models.TextChoices):
        HOSTING = 'HOSTING', 'Hosting'
        INFRASTRUCTURE = 'INFRASTRUCTURE', 'Infrastructure'
        MARKETING = 'MARKETING', 'Marketing'
        STAFF = 'STAFF', 'Staff'
        SOFTWARE_LICENSES = 'SOFTWARE_LICENSES', 'Software Licenses'
        OPERATIONS = 'OPERATIONS', 'Operations'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=Category.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    recorded_at = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platform_expenses_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_system_expenses'
        ordering = ['-recorded_at', '-created_at']

    def __str__(self):
        return f'{self.name} ({self.amount})'
