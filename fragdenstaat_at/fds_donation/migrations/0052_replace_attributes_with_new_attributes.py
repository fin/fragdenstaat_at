# Forward-port of DE fds_donation 0083 (P7.3, D8). Irreversible in practice:
# the hstore column is dropped, so keep a pre-migration dump to roll back to.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("fds_donation", "0051_move_donor_attributes"),
    ]

    operations = [
        migrations.RemoveField(model_name="donor", name="attributes"),
        migrations.RenameField(
            model_name="donor", old_name="new_attributes", new_name="attributes"
        ),
    ]
