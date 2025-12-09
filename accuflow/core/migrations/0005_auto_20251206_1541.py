
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_auto_20251124_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='godowns',
            name='open_balance',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='godowns',
            name='otc_balance',
            field=models.FloatField(default=0),
        ),
    ]
