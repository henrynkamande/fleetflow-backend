from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0003_emailauthcode'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='billing_status',
            field=models.CharField(
                choices=[
                    ('NOT_STARTED', 'Not started'),
                    ('TRIALING', 'Trialing'),
                    ('ACTIVE', 'Active'),
                    ('PAST_DUE', 'Past due'),
                    ('CANCELED', 'Canceled'),
                    ('INCOMPLETE', 'Incomplete'),
                ],
                db_index=True,
                default='NOT_STARTED',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='stripe_customer_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='stripe_subscription_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='trial_ends_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='billing_quantity',
            field=models.PositiveIntegerField(default=0, help_text='Last synced billable vehicle count'),
        ),
    ]
