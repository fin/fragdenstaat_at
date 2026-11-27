"""Production's `collectstatic` must succeed.

Production uses ManifestStaticFilesStorage (settings/production.py), which
rewrites every `url()`, `@import` and `sourceMappingURL` reference to the
hashed file name, and aborts the whole run if a referenced file is missing.
Dev and the test settings use the plain storage, so nothing else exercises
this. It has broken deploys three times: django-json-widget 1.1.1's
jsoneditor.min.js (49a0f48, 434af7f), and DE's ckeditor4 bundle override
(5a225194), whose sourceMappingURL named a hashed map that only existed in
DE's own collectstatic output. The P7 staging test caught that one.

Takes a few seconds. Without a frontend build (`pnpm run build`) it still runs,
over the third-party and theme files only.
"""

from django.conf import settings
from django.core.management import call_command
from django.test import override_settings


def test_collectstatic_with_manifest_storage(tmp_path):
    storages = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    }
    with override_settings(STATIC_ROOT=tmp_path, STORAGES=storages):
        call_command("collectstatic", interactive=False, verbosity=0)
    assert (tmp_path / "staticfiles.json").exists()
