from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0003_trip_planned_distance_km'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(
                fields=['company', 'planned_departure_time'],
                name='trips_company_planned_dep_idx',
            ),
        ),
    ]
