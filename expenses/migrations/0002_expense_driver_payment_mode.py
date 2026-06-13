from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='driver_payment_mode',
            field=models.CharField(
                blank=True,
                choices=[
                    ('MONTHLY_FIXED', 'Paid Monthly'),
                    ('WEEKLY_TRIPS', 'Weekly Payment'),
                    ('FIXED_DAILY', 'Fixed Pay Daily'),
                    ('PER_TRIP', 'Per Trip'),
                ],
                help_text='Optional payment mode for driver wage expenses.',
                max_length=20,
                null=True,
            ),
        ),
    ]
