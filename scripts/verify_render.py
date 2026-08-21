#!/usr/bin/env python
"""Render every CMS page and report failures.

The CMS swallows plugin render errors: a broken plugin yields HTTP 200 with the
content silently missing. This walks every published page, checks the status,
watches the log for render errors, and flags suspiciously short bodies.

Found four real bugs during the fragdenstaat_de sync that the test suite did not:
unregistered Column plugins, a missing PublicBody import, an unregistered
thumbnail_dims filter, and get_soft_root on a lazy None.

Usage (with DATABASE_* / DJANGO_SETTINGS_MODULE / DJANGO_CONFIGURATION set):
    python scripts/verify_render.py [--min-bytes 2000]

Needs a built frontend (`npx vite build`); it forces FRONTEND_DEBUG off so the
built manifest is used rather than a dev server.
"""

import argparse
import io
import logging
import sys

import configurations

configurations.setup()

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--min-bytes",
        type=int,
        default=2000,
        help="flag 200s smaller than this as suspiciously short",
    )
    args = ap.parse_args()

    settings.FRONTEND_DEBUG = False

    from cms.models import PageUrl

    log = io.StringIO()
    handler = logging.StreamHandler(log)
    logging.getLogger().addHandler(handler)

    client = Client()
    paths = sorted(set(PageUrl.objects.values_list("path", flat=True)))
    if not paths:
        print("no CMS pages found — is this the right database?", file=sys.stderr)
        return 2

    failures = []
    for path in paths:
        url = "/" + path + ("/" if path else "")
        try:
            response = client.get(url, HTTP_HOST="localhost")
        except Exception as exc:  # noqa: BLE001 - report, do not mask
            print(f"  {url:44s} EXC {type(exc).__name__}: {exc}")
            failures.append(url)
            continue

        size = len(response.content)
        print(f"  {url:44s} {response.status_code:>3}  {size:>7} bytes")
        if response.status_code >= 500:
            failures.append(url)
        elif response.status_code == 200 and size < args.min_bytes:
            failures.append(f"{url} (only {size} bytes)")

    errors = [
        line
        for line in log.getvalue().splitlines()
        if "Error" in line or "Invalid" in line or "Traceback" in line
    ]

    print()
    print(f"  pages:          {len(paths)}")
    print(f"  failures:       {failures or 'none'}")
    print(f"  logged errors:  {errors[:5] or 'none'}")
    return 1 if (failures or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
