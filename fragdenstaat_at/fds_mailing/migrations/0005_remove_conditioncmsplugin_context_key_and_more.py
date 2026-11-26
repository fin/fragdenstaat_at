# Forward-port of DE fds_mailing 0032 (P7.3, D8).
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("fds_mailing", "0004_migrate_condition"),
    ]

    operations = [
        migrations.RemoveField(model_name="conditioncmsplugin", name="context_key"),
        migrations.RemoveField(model_name="conditioncmsplugin", name="context_value"),
        migrations.RemoveField(model_name="conditioncmsplugin", name="negate"),
    ]
