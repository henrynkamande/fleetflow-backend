import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0007_user_owned_fleet_schema'),
        ('vehicles', '0004_vehicle_company_plate_unique_optional_vin'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='fleet_owner',
            field=models.ForeignKey(help_text='Fleet owner that owns this vehicle', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RemoveConstraint(
            model_name='vehicle',
            name='unique_vehicle_registration_per_company',
        ),
        migrations.RemoveField(model_name='vehicle', name='company'),
        migrations.DeleteModel(name='VehicleDocument'),
        migrations.DeleteModel(name='VehicleServiceRecord'),
        migrations.DeleteModel(name='VehicleExpense'),
        migrations.DeleteModel(name='FuelLog'),
        migrations.AlterField(
            model_name='vehicle',
            name='fleet_owner',
            field=models.ForeignKey(help_text='Fleet owner that owns this vehicle', on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='vehicle',
            constraint=models.UniqueConstraint(fields=('fleet_owner', 'registration_number'), name='unique_vehicle_registration_per_fleet_owner'),
        ),
        migrations.AddIndex(model_name='vehicle', index=models.Index(fields=['fleet_owner', 'status'], name='vehicles_fleet__5e389f_idx')),
        migrations.AddIndex(model_name='vehicle', index=models.Index(fields=['fleet_owner', '-created_at'], name='vehicles_fleet__94b1a5_idx')),
        migrations.AddIndex(model_name='vehicle', index=models.Index(fields=['fleet_owner', 'vehicle_type'], name='vehicles_fleet__3dfec4_idx')),
        migrations.AddIndex(model_name='vehicle', index=models.Index(fields=['fleet_owner', 'assigned_driver'], name='vehicles_fleet__3eb9c9_idx')),
        migrations.AddIndex(model_name='vehicle', index=models.Index(fields=['fleet_owner', 'is_active'], name='vehicles_fleet__f53998_idx')),
    ]
