import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformSystemExpense',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                (
                    'category',
                    models.CharField(
                        choices=[
                            ('HOSTING', 'Hosting'),
                            ('INFRASTRUCTURE', 'Infrastructure'),
                            ('MARKETING', 'Marketing'),
                            ('STAFF', 'Staff'),
                            ('SOFTWARE_LICENSES', 'Software Licenses'),
                            ('OPERATIONS', 'Operations'),
                            ('OTHER', 'Other'),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('recorded_at', models.DateField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='platform_expenses_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'platform_system_expenses',
                'ordering': ['-recorded_at', '-created_at'],
            },
        ),
    ]
