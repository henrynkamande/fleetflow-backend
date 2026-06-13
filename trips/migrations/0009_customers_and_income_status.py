from django.db import migrations, models
import django.db.models.deletion
import uuid


def create_default_customers(apps, schema_editor):
    Customer = apps.get_model('trips', 'Customer')
    Trip = apps.get_model('trips', 'Trip')
    for fleet_owner_id in Trip.objects.exclude(fleet_owner_id=None).values_list('fleet_owner_id', flat=True).distinct():
        customer, _ = Customer.objects.get_or_create(
            fleet_owner_id=fleet_owner_id,
            is_default=True,
            defaults={
                'name': 'Cash Payment',
                'created_by_id': fleet_owner_id,
            },
        )
        Trip.objects.filter(fleet_owner_id=fleet_owner_id, customer__isnull=True).update(
            customer=customer,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0010_driver_payment_modes'),
        ('trips', '0008_trip_driver_payment_modes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('phone', models.CharField(blank=True, default='', max_length=100)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('address', models.TextField(blank=True, default='')),
                ('notes', models.TextField(blank=True, default='')),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_customers', to='oauth.user')),
                ('fleet_owner', models.ForeignKey(help_text='Fleet owner that owns this customer', on_delete=django.db.models.deletion.CASCADE, related_name='customers', to='oauth.user')),
            ],
            options={
                'db_table': 'customers',
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AddField(
            model_name='trip',
            name='customer',
            field=models.ForeignKey(blank=True, help_text='Customer/client assigned to this trip', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='trips', to='trips.customer'),
        ),
        migrations.AddField(
            model_name='trip',
            name='income_status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('PARTIAL', 'Partial'), ('PAID', 'Paid'), ('OVERDUE', 'Overdue')], default='PENDING', help_text='Payment status controlled manually by fleet admin', max_length=20),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['fleet_owner', 'name'], name='customers_fleet_o_96c603_idx'),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['fleet_owner', 'is_default'], name='customers_fleet_o_42781b_idx'),
        ),
        migrations.AddConstraint(
            model_name='customer',
            constraint=models.UniqueConstraint(condition=models.Q(('is_default', True)), fields=('fleet_owner',), name='one_default_customer_per_fleet'),
        ),
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['fleet_owner', 'customer'], name='trips_fleet_o_6f1122_idx'),
        ),
        migrations.AddIndex(
            model_name='trip',
            index=models.Index(fields=['fleet_owner', 'income_status'], name='trips_fleet_o_23f8bf_idx'),
        ),
        migrations.RunPython(create_default_customers, migrations.RunPython.noop),
    ]
