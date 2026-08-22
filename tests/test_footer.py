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

There are two footers, and they are tested separately:

``LiveFooterTest``
    The one visitors actually see.  It lives in a djangocms-alias static alias
    (``{% static_alias "footer" %}``), migrated out of a cms StaticPlaceholder by
    ``fds_cms/migrations/0006``.  This is the one that matters.

``FooterTemplateTest``
    ``templates/footer.html`` -- a near-duplicate that the site does **not**
    render.  Kept under test because it is what a DE-sourced override would
    collide with, and because it is configuration-driven (``{% content_url %}``)
    where the alias copy hardcodes absolute URLs.

See MERGE_PLAN.md §2.7 for how the duplication arose.
"""

import json
import re
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase

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


class FooterTemplateTest(SimpleTestCase):
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

    def test_template_copy_uses_content_url_not_hardcoded_domains(self):
        """The template resolves legal links through ``{% content_url %}``.

        The live placeholder copy hardcodes ``https://fragdenstaat.at/...``
        instead, which is why it survived the ``.de``->``.at`` rename unscathed
        but will not survive a domain change.  Keep the template copy
        configuration-driven so it remains the better of the two.
        """
        self.assertNotIn(
            "fragdenstaat.at/info/",
            self.html,
            "the template copy has grown hardcoded absolute URLs; it should use "
            "{% content_url %} so it tracks FROIDE_CONFIG['content_urls']",
        )


class LiveFooterTest(TestCase):
    """Guard the footer visitors actually get: the djangocms-alias static alias.

    Renders through the same ``{% static_alias %}`` path as ``base.html``, against
    the real page/alias content captured from production in
    ``tests/fixtures/cms.json``.
    """

    fixtures = ["cms.json"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def _render(self):
        from django.template import Template

        from sekizai.context import SekizaiContext

        from fragdenstaat_at.fds_cms.utils import get_request

        request = get_request(language="de-at", path="/")
        context = SekizaiContext(request)
        context["request"] = request
        html = Template(
            '{% load djangocms_alias_tags %}{% static_alias "footer" %}'
        ).render(context)
        return html, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

    def test_alias_renders_non_empty(self):
        html, _ = self._render()
        self.assertGreater(
            len(html),
            500,
            "the footer alias rendered (almost) nothing -- migration 0006 may not "
            "have moved the plugins, or the AliasContent has no published Version",
        )

    def test_credit_and_sponsor_copy_present(self):
        _, text = self._render()
        for fragment in self.expected["text_fragments"]:
            self.assertIn(fragment, text, f"live footer lost copy: {fragment!r}")

    def test_legal_links_present(self):
        html, _ = self._render()
        for link in self.expected["links"]:
            if not link["text"]:
                continue
            path = norm_url(link["href"])
            self.assertIn(
                path.split("/", 1)[-1] if "/" in path else path,
                html,
                f"live footer lost link {link['text']!r}",
            )

    def test_no_german_site_identity(self):
        html, _ = self._render()
        lowered = html.lower()
        for forbidden in self.expected["must_not_contain"]:
            self.assertNotIn(forbidden.lower(), lowered)
