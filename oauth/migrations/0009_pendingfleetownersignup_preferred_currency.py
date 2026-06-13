from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0008_remove_company_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingfleetownersignup',
            name='preferred_currency',
            field=models.CharField(default='USD', max_length=3),
        ),
    ]
