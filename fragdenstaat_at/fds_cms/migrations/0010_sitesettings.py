# Forward-port of DE fds_cms 0088_sitesettings (P7.3, D8).
import django.db.models.deletion
from django.db import migrations, models

import fragdenstaat_at.fds_cms.sites


class Migration(migrations.Migration):
    dependencies = [
        ("fds_cms", "0009_unhash_static_urls_in_text"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "settings",
                    models.JSONField(
                        default=fragdenstaat_at.fds_cms.sites.get_default_site_settings,
                        validators=[
                            fragdenstaat_at.fds_cms.sites.validate_site_settings
                        ],
                    ),
                ),
                (
                    "site",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_settings",
                        to="sites.site",
                    ),
                ),
            ],
        ),
    ]
