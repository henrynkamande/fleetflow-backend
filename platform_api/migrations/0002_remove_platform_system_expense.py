from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
        ('platform_api', '0001_platform_system_expense'),
    ]

    operations = [
        migrations.DeleteModel(name='PlatformSystemExpense'),
    ]
