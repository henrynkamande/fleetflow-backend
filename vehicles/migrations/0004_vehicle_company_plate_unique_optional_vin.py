from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0003_vehicle_owner_list_indexes'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='vehicle',
                    name='registration_number',
                    field=models.CharField(
                        help_text='Vehicle license plate/registration number',
                        max_length=50,
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterField(
            model_name='vehicle',
            name='vin',
            field=models.CharField(
                blank=True,
                help_text='Vehicle Identification Number (VIN/Chassis Number)',
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name='vehicle',
            constraint=models.UniqueConstraint(
                fields=('company', 'registration_number'),
                name='unique_vehicle_registration_per_company',
            ),
        ),
    ]
