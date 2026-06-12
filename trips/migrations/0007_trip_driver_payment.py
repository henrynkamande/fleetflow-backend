from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0006_simplify_trip_schema'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='driver_payment',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Driver payment for this trip',
                max_digits=10,
            ),
        ),
    ]
