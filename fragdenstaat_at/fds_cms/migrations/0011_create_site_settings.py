# Forward-port of DE fds_cms 0089 (P7.3, D8): one SiteSettings row per Site.
from django.db import migrations


def create_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model("fds_cms", "SiteSettings")
    Site = apps.get_model("sites", "Site")
    for site in Site.objects.filter(site_settings__isnull=True):
        SiteSettings.objects.create(site=site)


class Migration(migrations.Migration):
    dependencies = [
        ("fds_cms", "0010_sitesettings"),
    ]

    operations = [
        migrations.RunPython(create_site_settings, migrations.RunPython.noop),
    ]
