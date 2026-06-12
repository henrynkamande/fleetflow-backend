from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0007_user_owned_fleet_schema'),
        ('trips', '0006_simplify_trip_schema'),
        ('vehicles', '0005_simplify_vehicle_schema'),
    ]

    operations = [
        migrations.RemoveField(model_name='user', name='company'),
        migrations.DeleteModel(name='Company'),
    ]
