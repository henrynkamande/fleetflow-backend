from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0002_trip_other_expenses_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='planned_distance_km',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Estimated route distance in km (from fleet planning)',
                null=True,
            ),
        ),
    ]
