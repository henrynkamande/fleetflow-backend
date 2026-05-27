from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0004_company_stripe_billing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('FLEET_OWNER', 'Fleet Owner'),
                    ('DRIVER', 'Driver'),
                    ('PLATFORM_ADMIN', 'Platform Admin'),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
