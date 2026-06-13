from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0007_trip_driver_payment'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='driver_payment_mode',
            field=models.CharField(
                choices=[
                    ('MONTHLY_FIXED', 'Paid Monthly'),
                    ('WEEKLY_TRIPS', 'Weekly Payment'),
                    ('FIXED_DAILY', 'Fixed Pay Daily'),
                    ('PER_TRIP', 'Per Trip'),
                ],
                default='PER_TRIP',
                help_text='Driver payment mode snapshot used for this trip',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='trip',
            name='driver_payment_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Driver pay rate snapshot used to calculate this trip payout',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='trip',
            name='driver_payment_auto_calculated',
            field=models.BooleanField(
                default=True,
                help_text='When true, calculate driver payment from mode and rate',
            ),
        ),
    ]
