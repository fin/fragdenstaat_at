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

from decimal import Decimal

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


def assert_no_german_bank(text, where):
    found = [m for m in DE_BANK_MARKERS if m in text]
    assert not found, f"German bank details in {where}: {found}"


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


class PageTest(TestCase):
    fixtures = ["cms.json"]

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        assert_no_german_bank(response.content.decode("utf-8", "replace"), "homepage")

    def test_donation_form_page(self):
        response = self.client.get(reverse("fds_donation:donate"))
        self.assertEqual(response.status_code, 200)
        assert_no_german_bank(
            response.content.decode("utf-8", "replace"), "donation form"
        )

    def test_donor_page(self):
        """/spenden/spende/ihre-spenden/ lists pending bank transfers."""
        donor = DonorFactory(email="donor@example.com", email_confirmed=timezone.now())
        response = self.client.post(donor.get_login_url())
        self.assertEqual(response.status_code, 302)
        # follow=True: the donor landing page redirects on to a sub-path
        # (/ihre-spenden/spenden/), so a single GET returns another 302.
        response = self.client.get(response.url, follow=True)
        self.assertEqual(response.status_code, 200)
        assert_no_german_bank(response.content.decode("utf-8", "replace"), "donor page")
