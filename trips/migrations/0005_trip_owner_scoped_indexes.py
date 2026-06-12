from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0004_trip_company_planned_departure_index'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['company', '-created_at'], name='trips_company_9db587_idx'),
        ),
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['company', 'vehicle'], name='trips_company_ee1c86_idx'),
        ),
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['company', 'driver'], name='trips_company_ef6a4f_idx'),
        ),
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['status'], name='trips_status_f46839_idx'),
        ),
    ]
