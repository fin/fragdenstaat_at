"""Guard the Austrian identity on the pages and mails that carry bank details.

Money going to the wrong account is the worst failure mode in this codebase, and
it is invisible in a render check: the page returns 200 either way. AT's bank
details were Open Knowledge Foundation Deutschland's for the whole of the DE
sync, hardcoded in five places including a SEPA QR code, because the templates
were ported verbatim.

These are string assertions rather than a scanner because they run against
*rendered output*: they cover what a donor actually sees, including anything
pulled in from CMS content or an included template, which
`sync_froide_translations.py --dry-run` (source scan, MERGE_PLAN 9.12) cannot
see.

Note "Open Knowledge Foundation Deutschland" is deliberately not forbidden: the
site footer credits OKF Deutschland as a supporter, which is correct. Only the
German *bank* details are.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import AnonymousUser
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

import pytest

from fragdenstaat_at.fds_donation.tests.factories import DonorFactory

ORG = "Forum Informationsfreiheit"
AT_IBAN_SPACED = "AT69 2011 1824 3494 2000"
AT_IBAN_PLAIN = "AT692011182434942000"
AT_BIC = "GIBAATWWXXX"

# Every German bank identifier that appeared in the ported templates, in each
# form it appeared in -- spaced and unspaced, since the BLZ leaked as a bare
# copy-button value with its label removed.
DE_BANK_MARKERS = [
    "DE36430609671173893200",
    "DE36 4306 0967 1173 8932 00",
    "GENODEM1GLS",
    "GLS Bank",
    "43060967",
    "430 609 67",
]


# Allowed in the footer and nowhere else: the site credits OKF Deutschland as a
# supporter, which is correct. Anywhere else it means DE content leaked in.
DE_ORG = "Open Knowledge Foundation Deutschland"

FOOTER_RE = re.compile(r"<footer[^>]*id=\"footer\".*?</footer>", re.S | re.I)


def strip_footer(html):
    """Remove the footer element so page checks can ban DE_ORG everywhere else.

    Every page extends base.html, which renders the footer alias, so a
    whole-body check would trip on the legitimate supporter credit.
    """
    return FOOTER_RE.sub("", html)


def assert_no_german_bank(text, where):
    found = [m for m in DE_BANK_MARKERS if m in text]
    assert not found, f"German bank details in {where}: {found}"


def assert_no_german_org(text, where):
    assert DE_ORG not in text, (
        f"{DE_ORG!r} appears in {where}. It belongs only in the footer's "
        "supporter credit -- anywhere else is leaked DE content."
    )


class FakeOrder:
    """Minimal stand-in: the templates only read these attributes."""

    is_recurring = False
    total_gross = Decimal("5.00")
    remote_reference = "FDS TESTREF"
    subscription = None


class FakePayment:
    is_confirmed = False
    variant = "banktransfer"


@pytest.mark.parametrize(
    "template",
    [
        "fds_donation/includes/banktransfer_instructions.html",  # web
        "fds_donation/includes/banktransfer.txt",  # mail
    ],
)
def test_banktransfer_details_are_austrian(template):
    out = render_to_string(template, {"order": FakeOrder(), "payment": FakePayment()})
    assert ORG in out, f"{template} does not name {ORG}"
    assert AT_IBAN_SPACED in out or AT_IBAN_PLAIN in out, f"{template}: no AT IBAN"
    assert AT_BIC in out, f"{template}: no AT BIC"
    assert_no_german_bank(out, template)
    assert_no_german_org(out, template)


class FooterTest(TestCase):
    """The footer alias, rendered the way base.html renders it.

    A Django TestCase, not a pytest class: `fixtures` is a TestCase attribute
    and is silently ignored elsewhere, which renders the empty CMS welcome page
    instead of the site.
    """

    fixtures = ["cms.json"]

    def _footer(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = {}
        context = Context({"request": request})
        return Template(
            '{% load djangocms_alias_tags %}{% static_alias "footer" %}'
        ).render(context)

    def test_footer_has_no_german_bank_details(self):
        html = self._footer()
        self.assertGreater(len(html), 200, "footer rendered suspiciously short")
        assert_no_german_bank(html, "footer alias")

    def test_footer_credits_the_austrian_organisation(self):
        self.assertIn(ORG, self._footer())

    def test_footer_may_credit_okf_as_supporter(self):
        """The one place DE_ORG is legitimate, asserted so nobody "cleans" it up.

        If this fails the credit was removed -- a content decision rather than a
        leak. Delete this test along with it.
        """
        self.assertIn(DE_ORG, self._footer())


class PageTest(TestCase):
    fixtures = ["cms.json"]

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", "replace")
        assert_no_german_bank(body, "homepage")
        assert_no_german_org(strip_footer(body), "homepage (outside the footer)")

    def test_donation_form_page(self):
        response = self.client.get(reverse("fds_donation:donate"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", "replace")
        assert_no_german_bank(body, "donation form")
        assert_no_german_org(strip_footer(body), "donation form (outside the footer)")

    def test_donor_page(self):
        """/spenden/spende/ihre-spenden/ lists pending bank transfers."""
        donor = DonorFactory(email="donor@example.com", email_confirmed=timezone.now())
        response = self.client.post(donor.get_login_url())
        self.assertEqual(response.status_code, 302)
        # follow=True: the donor landing page redirects on to a sub-path
        # (/ihre-spenden/spenden/), so a single GET returns another 302.
        response = self.client.get(response.url, follow=True)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8", "replace")
        assert_no_german_bank(body, "donor page")
        assert_no_german_org(strip_footer(body), "donor page (outside the footer)")


# ---------------------------------------------------------------------------
# {% page_url %} links, MERGE_PLAN 9.3
#
# django-cms's page_url tag resolves a *string* argument as a page's reverse_id
# (Page -> Advanced settings -> ID). When no page matches it returns "" rather
# than raising -- a deliberate upstream decision, so that the "as" form never
# raises regardless of DEBUG (cms/templatetags/cms_tags.py, PageUrl). The cost
# is that a missing reverse_id is invisible: the page still returns 200, with a
# clickable link that goes nowhere.
#
# AT's imported CMS content has 10 pages and 0 reverse_ids, so every one of
# these is unresolved in production today.
# ---------------------------------------------------------------------------

# Referenced with a fallback, so a missing page degrades rather than breaking.
SAFE_PAGE_URL_IDS = {
    "home": "wrapped in |default:'/' at header.html and cms/breadcrumbs.html",
    "beginnersguide": "wrapped in {% if %} at header.html, link hidden if unset",
}

# Referenced bare: these render href="" and produce a dead visible link.
REQUIRED_PAGE_URL_IDS = {
    "help": "cms/help_base.html -- 'Topics' link",
    "help:donations": "fds_donation/donor_detail.html -- 'Frequent questions & contact'",
    "donate": "fds_donation/donation_failed.html -- 'Try again' button",
}

# {% page_url "x" %} / {% page_url 'x' %}, string literals only. Variable
# lookups (cms/pub_base.html passes a Page object) can't be checked statically.
PAGE_URL_LITERAL_RE = re.compile(r"{%\s*page_url\s+(['\"])(?P<id>[^'\"]+)\1")


def _scan_template_page_url_ids():
    """Every reverse_id referenced by a string literal in AT's own templates."""
    root = Path(__file__).resolve().parent.parent / "fragdenstaat_at"
    found = {}
    for path in root.rglob("*.html"):
        for match in PAGE_URL_LITERAL_RE.finditer(
            path.read_text(encoding="utf-8", errors="replace")
        ):
            found.setdefault(match.group("id"), []).append(str(path.relative_to(root)))
    return found


def test_page_url_ids_are_all_accounted_for():
    """Fails when a {% page_url %} appears that this file doesn't classify.

    This is the part that runs green today. It doesn't check the CMS content --
    it checks that nobody adds a new page_url link without deciding whether it
    needs a fallback, which is how the three unguarded ones got in.
    """
    found = _scan_template_page_url_ids()
    known = set(SAFE_PAGE_URL_IDS) | set(REQUIRED_PAGE_URL_IDS)
    unclassified = {k: v for k, v in found.items() if k not in known}
    assert not unclassified, (
        "New {% page_url %} reverse_id(s) not classified in this file: "
        + ", ".join(f"{k!r} ({', '.join(v)})" for k, v in sorted(unclassified.items()))
        + ". Give the link a fallback and add it to SAFE_PAGE_URL_IDS, or add it "
        "to REQUIRED_PAGE_URL_IDS and set the reverse_id on the CMS page."
    )
    # And the reverse: a classified id that no template uses any more is stale.
    stale = known - set(found)
    assert not stale, (
        f"No template references {sorted(stale)} any more -- drop from this file."
    )


# ---------------------------------------------------------------------------
# Regenerating tests/fixtures/cms.json
#
# The fixture is shared by this module, test_footer.py and test_web.py.
#
#     python manage.py export_fdscms --output tests/fixtures/cms.json
#
# Run that against a database loaded from a `scripts/export_dev_db.py` extract,
# NOT a real one. The extract is what keeps the fixture small: it carries
# published versions only and fabricates a single synthetic user, so the
# fixture's lone account.user is pk=1 / "dev" / dev@localhost. The same dump
# against a real dev database produced 4180 objects and 2745 users when checked.
#
# Do NOT use plain `dumpdata`. It cannot emit a loadable CMS fixture here:
# under --natural-foreign it orders via serializers.sort_dependencies, which
# sorts by *natural key* dependencies rather than the FK graph. cms.Page has no
# natural key, so it is emitted last -- after cms.PageContent, which references
# it -- and cms/signals/pagecontent.py dereferences instance.page in a post_save
# handler. loaddata then dies with Page.DoesNotExist before any test runs.
# export_fdscms re-sorts the dump by the real FK graph to fix exactly this.
#
# Verified flags, from the stored FKs: --natural-foreign IS used (site is
# ["fragdenstaat.at"], content_type is ["cms", "pagecontent"], Version's
# created_by is ["dev@localhost"]); --natural-primary is NOT (every object keeps
# its integer pk, which is what lets page pks line up with a dev database, so
# single fields can be patched across instead of regenerating).
#
# Provenance: the fixture arrived in the 2021 DE merge and has been regenerated
# several times since; the original command was never recorded and was
# reconstructed from the file's contents.
# ---------------------------------------------------------------------------


class PageUrlResolutionTest(TestCase):
    """Every unguarded {% page_url %} resolves to a real page. MERGE_PLAN 9.3.

    This was xfail(strict) while the CMS content had no reverse_ids at all; the
    marker came off when a regenerated fixture made it XPASS. It now guards
    against the ids being removed or renamed again -- the failure it catches is
    silent, since an empty href still returns 200.
    """

    fixtures = ["cms.json"]

    def _render(self, reverse_id):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.current_page = None
        template = Template("{% load cms_tags %}{% page_url page_id as url %}{{ url }}")
        return template.render(
            Context({"request": request, "page_id": reverse_id})
        ).strip()

    def test_required_page_urls_resolve(self):
        unresolved = {
            page_id: where
            for page_id, where in sorted(REQUIRED_PAGE_URL_IDS.items())
            if not self._render(page_id)
        }
        assert not unresolved, (
            "These {% page_url %} lookups render an empty href, so the link is "
            "visible but dead:\n"
            + "\n".join(f"  {k!r}: {v}" for k, v in unresolved.items())
            + "\nFix in the CMS: Page -> Advanced settings -> ID."
        )
