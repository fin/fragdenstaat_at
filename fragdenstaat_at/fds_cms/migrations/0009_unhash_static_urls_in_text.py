"""Strip content hashes from static URLs pasted into CMS text plugins.

The footer alias hard-codes three sponsor logos as absolute, hash-stamped URLs
(``.../img/foi_logo.e81e7e609d90.png``). Those hashes are leftovers from a
deployment that used ManifestStaticFilesStorage; production now serves unhashed
assets, so nothing regenerates them. They resolve today only because the old
files happen to still exist, and the next ``collectstatic --clear`` — or any edit
to those images — breaks the logos.

Rewriting to the unhashed name makes them track whatever the current asset is.
The host is left alone: the content is served from the site domain but the assets
from the static domain, so a relative path would not resolve.

Conservative by construction: only ``<12 hex>`` segments immediately before a
known asset extension are removed, and only inside URLs containing ``/static/``.
"""

import re

from django.db import migrations

# .../name.<12 hex>.ext  ->  .../name.ext
HASHED = re.compile(
    r"(/static/[^\"'\s]*?)\.[0-9a-f]{12}(\.(?:png|jpe?g|svg|gif|webp|css|js))"
)


def unhash(apps, schema_editor):
    Text = apps.get_model("djangocms_text", "Text")
    for text in Text.objects.filter(body__contains="/static/").iterator():
        new_body = HASHED.sub(r"\1\2", text.body)
        if new_body != text.body:
            text.body = new_body
            text.save(update_fields=["body"])


def noop(apps, schema_editor):
    """Not reversible: the original hashes are not recoverable, and the unhashed
    URLs are the correct long-term form anyway."""


class Migration(migrations.Migration):
    dependencies = [
        ("fds_cms", "0008_datawrappercmsplugin_opensearchcmsplugin_and_more"),
        ("djangocms_text", "0001_initial"),
    ]

    operations = [migrations.RunPython(unhash, noop)]
