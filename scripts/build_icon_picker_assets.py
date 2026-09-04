#!/usr/bin/env python3
"""Generate the djangocms_frontend icon picker's Font Awesome 4 icon list.

``djangocms_frontend.contrib.icon`` ships icon libraries whose stylesheets are
loaded from cdnjs / jsdelivr / Google Fonts at render time (``ICON_CDN`` in
``djangocms_frontend/contrib/icon/conf.py``): the ``icon_tags``
``add_css_for_icon`` tag injects such a ``<link>`` into every page that renders
an icon, and the admin icon picker loads the same URL to preview icons. We do
not want third-party CDNs, and the site ships Font Awesome 4.7.0 itself
(``frontend/styles/base.scss`` -> ``main.css``), so
``DJANGOCMS_FRONTEND_ICON_LIBRARIES`` in ``settings/base.py`` offers a single
local library instead -- the same move ``templates/admin/djangocms_icon/
includes/assets.html`` makes for the djangocms_icon plugin.

A library is a list of icon names plus a stylesheet. The stylesheet is the FA4
copy already vendored at ``static/font-awesome/font-awesome.min.css`` for the
djangocms_icon admin. Only the name list is generated here, from the ``font-awesome`` npm package -- the very copy
``base.scss`` compiles into ``main.css``, so the picker offers exactly the
icons the site can render. It is committed; re-run after upgrading the
``font-awesome`` npm package::

    python scripts/build_icon_picker_assets.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FA = ROOT / "node_modules" / "font-awesome"
# Names without a "/" are resolved with static() under djangocms_frontend's
# own vendor path, so the file has to live there -- in the theme's static dir,
# which STATICFILES_DIRS puts first.
TARGET = (
    ROOT
    / "fragdenstaat_at/static/djangocms_frontend/icon/vendor/assets/icons-libraries/font-awesome4.min.json"
)


def main() -> None:
    if not FA.is_dir():
        sys.exit(f"{FA} missing -- run `pnpm install` first")
    icons = sorted(
        set(
            re.findall(
                r"\.#\{\$fa-css-prefix\}-([\w-]+):before",
                (FA / "scss/_icons.scss").read_text(),
            )
        )
    )
    library = {
        "prefix": "fa fa-",
        "icon-style": "fa",
        "list-icon": "fa fa-flag",
        "version": json.loads((FA / "package.json").read_text())["version"],
        "icons": icons,
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(library, separators=(",", ":")) + "\n")
    print(f"{TARGET.relative_to(ROOT)}: {len(icons)} icons")


if __name__ == "__main__":
    main()
