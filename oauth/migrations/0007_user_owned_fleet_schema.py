import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0006_pending_fleet_owner_signup'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='fleet_owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='managed_users', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='user',
            name='subscription_plan',
            field=models.CharField(default='free', max_length=50),
        ),
        migrations.AddField(
            model_name='user',
            name='billing_status',
            field=models.CharField(choices=[('NOT_STARTED', 'Not started'), ('TRIALING', 'Trialing'), ('ACTIVE', 'Active'), ('PAST_DUE', 'Past due'), ('CANCELED', 'Canceled'), ('INCOMPLETE', 'Incomplete')], db_index=True, default='NOT_STARTED', max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='stripe_customer_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='stripe_subscription_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='trial_ends_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='billing_quantity',
            field=models.PositiveIntegerField(default=0, help_text='Last synced billable vehicle count'),
        ),
        migrations.AddField(
            model_name='driverprofile',
            name='fleet_owner',
            field=models.ForeignKey(blank=True, limit_choices_to={'role': 'FLEET_OWNER'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='driver_profiles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.DeleteModel(name='KYCDocument'),
        migrations.AddIndex(model_name='user', index=models.Index(fields=['fleet_owner', 'role'], name='users_fleet_o_4ce925_idx')),
        migrations.AddIndex(model_name='user', index=models.Index(fields=['billing_status'], name='users_billing_83f64d_idx')),
        migrations.AddIndex(model_name='driverprofile', index=models.Index(fields=['fleet_owner', 'is_active'], name='driver_prof_fleet_o_d6ee9d_idx')),
    ]
