import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone

import expenses.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('trips', '0006_simplify_trip_schema'),
        ('vehicles', '0005_simplify_vehicle_schema'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Expense',
                    fields=[
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('scope', models.CharField(choices=[('FLEET', 'Fleet'), ('VEHICLE', 'Vehicle'), ('TRIP', 'Trip'), ('PLATFORM', 'Platform')], db_index=True, max_length=20)),
                        ('category', models.CharField(choices=[('FUEL', 'Fuel'), ('MAINTENANCE', 'Maintenance'), ('INSURANCE', 'Insurance'), ('REGISTRATION', 'Registration'), ('TOLL', 'Toll'), ('PARKING', 'Parking'), ('DRIVER_WAGES', 'Driver wages'), ('HOSTING', 'Hosting'), ('MARKETING', 'Marketing'), ('OPERATIONS', 'Operations'), ('SOFTWARE', 'Software'), ('OTHER', 'Other')], db_index=True, max_length=32)),
                        ('status', models.CharField(choices=[('PAID', 'Paid'), ('PENDING', 'Pending'), ('OVERDUE', 'Overdue')], db_index=True, default='PAID', max_length=20)),
                        ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                        ('description', models.CharField(max_length=500)),
                        ('vendor', models.CharField(blank=True, max_length=200)),
                        ('expense_date', models.DateField(db_index=True, default=timezone.localdate)),
                        ('odometer_reading', models.PositiveIntegerField(blank=True, null=True)),
                        ('receipt', models.FileField(blank=True, null=True, upload_to=expenses.models.expense_receipt_upload_path, validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])])),
                        ('notes', models.TextField(blank=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expenses_created', to=settings.AUTH_USER_MODEL)),
                        ('fleet_owner', models.ForeignKey(blank=True, help_text='Fleet owner for fleet/vehicle/trip expenses. Empty for platform-only costs.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='expenses', to=settings.AUTH_USER_MODEL)),
                        ('trip', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expenses', to='trips.trip')),
                        ('vehicle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='expenses', to='vehicles.vehicle')),
                    ],
                    options={
                        'db_table': 'expenses',
                        'ordering': ['-expense_date', '-created_at'],
                    },
                ),
                migrations.AddIndex(model_name='expense', index=models.Index(fields=['fleet_owner', 'expense_date'], name='expenses_fleet__5a2df4_idx')),
                migrations.AddIndex(model_name='expense', index=models.Index(fields=['fleet_owner', 'vehicle'], name='expenses_fleet__75bc3b_idx')),
                migrations.AddIndex(model_name='expense', index=models.Index(fields=['fleet_owner', 'trip'], name='expenses_fleet__0550e8_idx')),
                migrations.AddIndex(model_name='expense', index=models.Index(fields=['scope', 'category'], name='expenses_scope_7d2f6f_idx')),
                migrations.AddIndex(model_name='expense', index=models.Index(fields=['status'], name='expenses_status_f3f3dc_idx')),
            ],
        ),
    ]
