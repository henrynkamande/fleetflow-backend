from django.db import migrations, models


def normalize_driver_payment_modes(apps, schema_editor):
    DriverProfile = apps.get_model('oauth', 'DriverProfile')
    DriverProfile.objects.filter(payment_type='FIXED').update(payment_type='MONTHLY_FIXED')
    DriverProfile.objects.filter(payment_type__in=['PER_KM', 'PER_HOUR']).update(payment_type='PER_TRIP')


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0009_pendingfleetownersignup_preferred_currency'),
    ]

    operations = [
        migrations.RunPython(normalize_driver_payment_modes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='driverprofile',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('MONTHLY_FIXED', 'Paid Monthly'),
                    ('WEEKLY_TRIPS', 'Weekly Payment'),
                    ('FIXED_DAILY', 'Fixed Pay Daily'),
                    ('PER_TRIP', 'Per Trip'),
                ],
                default='PER_TRIP',
                max_length=20,
            ),
        ),
    ]
