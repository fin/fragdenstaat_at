# Forward-port of DE fds_donation 0081 (P7.3, D8).
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fds_donation", "0049_checkdonortagcmsplugin"),
    ]

    operations = [
        migrations.AddField(
            model_name="donor",
            name="new_attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
