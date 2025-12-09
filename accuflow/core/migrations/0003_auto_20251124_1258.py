
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_godowns_qty'),
    ]

    operations = [
        migrations.AddField(
            model_name='customers',
            name='open_balance',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='customers',
            name='otc_balance',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='suppliers',
            name='open_balance',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='suppliers',
            name='otc_balance',
            field=models.FloatField(default=0),
        ),
    ]
