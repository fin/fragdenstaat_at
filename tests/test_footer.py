"""Guard the site footer against regressions during the fragdenstaat_de sync.

The footer is the smallest piece of markup that exercises the whole AT identity
at once: the sponsor and credit copy, the ``FROIDE_CONFIG["content_urls"]``
legal links, and the static pipeline.  Most ways the sync can go wrong -- a DE
template winning over the AT override, ``content_urls`` reverting to the German
paths, a sponsor asset dropped from the build -- surface here first, and on
every page of the site.

The reference in ``tests/snapshots/footer_live.json`` was captured from
https://fragdenstaat.at/ on 2026-08-18, i.e. *before* any sync work.  Compare
against it; do not regenerate it casually.  A diff means either a real
regression or a deliberate footer change, and the latter should update the
snapshot in the same commit.

This renders ``footer.html`` directly rather than fetching a page, so it needs
no database, no CMS fixtures and no running services.  That is deliberate: the
test stays usable while the rest of the stack is mid-port.

Note: the live footer is produced by this template, **not** by the ``footer``
CMS static placeholder, which holds an unrendered near-duplicate (its URLs are
absolute, the template's are relative).  See MERGE_PLAN.md.
"""

import json
import re
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

SNAPSHOT = Path(__file__).parent / "snapshots" / "footer_live.json"
STATIC_HASH = re.compile(r"\.[0-9a-f]{12}(\.[a-z0-9]+)$")


def norm_url(url: str) -> str:
    """Host-relative where possible, without a trailing slash."""
    return re.sub(r"^https?://", "", url).rstrip("/")


def norm_static(src: str) -> str:
    """Strip host, /static/ prefix and any ManifestStaticFilesStorage hash."""
    src = re.sub(r"^https?://[^/]+", "", src)
    src = re.sub(r"^/?static/", "", src.lstrip("/"))
    return STATIC_HASH.sub(r"\1", src)


class FooterRegressionTest(SimpleTestCase):
    """Compare the rendered footer against the pre-sync live site."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.html = render_to_string("footer.html", {})
        cls.text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cls.html))
        cls.hrefs = {norm_url(h) for h in re.findall(r'href="([^"]+)"', cls.html)}
        cls.srcs = {
            norm_static(s) for s in re.findall(r'<img[^>]+src="([^"]+)"', cls.html)
        }

    def test_renders_at_all(self):
        self.assertGreater(len(self.html), 200, "footer rendered suspiciously short")

    def test_credit_and_sponsor_copy_present(self):
        """The FOI / OKF credit and the Easyname sponsorship must survive."""
        for fragment in self.expected["text_fragments"]:
            self.assertIn(fragment, self.text, f"footer lost copy: {fragment!r}")

    def test_no_german_site_identity_leaked_in(self):
        """A DE template winning over the AT override would show up here."""
        lowered = self.html.lower()
        for forbidden in self.expected["must_not_contain"]:
            self.assertNotIn(
                forbidden.lower(),
                lowered,
                f"German identity leaked into the AT footer: {forbidden!r}",
            )

    def test_legal_links_still_point_at_the_austrian_pages(self):
        """Covers FROIDE_CONFIG['content_urls'] reverting to the DE paths."""
        for link in self.expected["links"]:
            if not link["text"]:
                continue
            want = norm_url(link["href"])
            self.assertIn(
                want,
                self.hrefs,
                f"footer lost link {link['text']!r} -> {link['href']} "
                f"(have: {sorted(self.hrefs)})",
            )

    def test_sponsor_logos_resolve_through_the_static_pipeline(self):
        """Catches assets dropped from the build during the frontend merge."""
        for image in self.expected["images"]:
            self.assertIn(
                image["src"],
                self.srcs,
                f"footer lost image {image['src']} (have: {sorted(self.srcs)})",
            )

    def test_legal_links_are_relative_not_absolute(self):
        """The template uses {% content_url %}; the unused CMS static placeholder
        stores absolute https://fragdenstaat.at/... URLs.  Absolute legal links
        here would mean the placeholder copy has started winning."""
        self.assertNotIn(
            "fragdenstaat.at/info/",
            self.html,
            "absolute legal URLs in the footer: the duplicated CMS 'footer' "
            "static placeholder may have started rendering -- reconcile the two",
        )
