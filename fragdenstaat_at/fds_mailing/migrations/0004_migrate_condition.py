# Forward-port of DE fds_mailing 0031 (P7.3, D8). The old plugin resolved
# context_value with template Variable(), so an unquoted value meant a variable
# and a quoted one a literal; the condition syntax reads them the same way.
from django.db import migrations


def migrate_condition(apps, schema_editor):
    ConditionCMSPlugin = apps.get_model("fds_mailing", "ConditionCMSPlugin")
    for instance in ConditionCMSPlugin.objects.all():
        instance.condition = "%s%s%s%s" % (
            "not " if instance.negate else "",
            instance.context_key,
            " == " if instance.context_value else "",
            instance.context_value,
        )
        instance.save(update_fields=["condition"])


class Migration(migrations.Migration):
    dependencies = [
        ("fds_mailing", "0003_conditioncmsplugin_condition"),
    ]

    operations = [
        migrations.RunPython(migrate_condition),
    ]
