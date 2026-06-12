import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0007_user_owned_fleet_schema'),
        ('trips', '0005_trip_owner_scoped_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='fleet_owner',
            field=models.ForeignKey(help_text='Fleet owner that owns this trip', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='trips', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RemoveField(model_name='trip', name='company'),
        migrations.DeleteModel(name='TripStop'),
        migrations.DeleteModel(name='TripExpense'),
        migrations.AlterField(
            model_name='trip',
            name='fleet_owner',
            field=models.ForeignKey(help_text='Fleet owner that owns this trip', on_delete=django.db.models.deletion.CASCADE, related_name='trips', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(model_name='trip', index=models.Index(fields=['fleet_owner', 'status'], name='trips_fleet_o_668ecd_idx')),
        migrations.AddIndex(model_name='trip', index=models.Index(fields=['fleet_owner', '-created_at'], name='trips_fleet_o_cc6801_idx')),
        migrations.AddIndex(model_name='trip', index=models.Index(fields=['fleet_owner', 'planned_departure_time'], name='trips_fleet_o_c7ba18_idx')),
        migrations.AddIndex(model_name='trip', index=models.Index(fields=['fleet_owner', 'vehicle'], name='trips_fleet_o_35f0dd_idx')),
        migrations.AddIndex(model_name='trip', index=models.Index(fields=['fleet_owner', 'driver'], name='trips_fleet_o_ba4dd4_idx')),
    ]
