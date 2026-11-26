# Forward-port of DE fds_donation 0080 (P7.3, D8).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0045_pageurl_site_unique_path"),
        ("fds_donation", "0048_donationformcmsplugin_hide_contact_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckDonorTagCMSPlugin",
            fields=[
                (
                    "cmsplugin_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        related_name="%(app_label)s_%(class)s",
                        serialize=False,
                        to="cms.cmsplugin",
                    ),
                ),
                (
                    "negate",
                    models.BooleanField(
                        default=False,
                        help_text="If doesn't have tag",
                        verbose_name="Negate condition",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="fds_donation.donortag",
                        verbose_name="Donor Tag",
                    ),
                ),
            ],
            bases=("cms.cmsplugin",),
        ),
    ]
