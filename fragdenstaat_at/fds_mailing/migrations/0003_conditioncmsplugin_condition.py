# Forward-port of DE fds_mailing 0030 (P7.3, D8).
from django.db import migrations, models

import flowcontrol.utils


class Migration(migrations.Migration):
    dependencies = [
        ("fds_mailing", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="conditioncmsplugin",
            name="condition",
            field=models.TextField(
                default="False",
                validators=[flowcontrol.utils.validate_template_condition],
            ),
            preserve_default=False,
        ),
    ]
