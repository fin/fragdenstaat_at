"""The fax notice tracking the public body chooser, in a real browser.

tests/test_fax_delivery_notice.py covers the server-rendered half. This covers
the half that only exists at runtime: the chooser is a Vue app that re-renders
no template, so frontend/javascript/makerequest.ts has to drive the notice.

Written to chase a bug and it found two. The selection surfaces as
input[name="publicbody"] as a *hidden* input once committed -- the chooser emits
no radios -- so an implementation matching `:checked` never updated. And
committing swaps the DOM during a Vue re-render without firing an event, so a
change listener alone is not enough either.

Setup and selectors follow froide's own live tests
(froide/tests/live/test_request.py), which is what made this work: the bodies
must be on Site 1 with a FoiLaw for their jurisdiction, the index has to be
rebuilt, and results are buttons reached through an explicit search submit.

Needs a built frontend (`pnpm run build`) and Elasticsearch.
"""

from django.contrib.sites.models import Site
from django.urls import reverse

import pytest
from playwright.async_api import expect

from froide.foirequest.tests.factories import rebuild_index
from froide.publicbody.factories import (
    FoiLawFactory,
    JurisdictionFactory,
    PublicBodyFactory,
)

NOTICE = "#fds-fax-delivery-notice"
SEARCH = ".search-public_bodies"
FAX_NAME = "Faxamt Teststadt"
EMAIL_NAME = "Mailamt Teststadt"


@pytest.fixture
def fax_publicbodies(db):
    """One body diverted to fax, one ordinary, both searchable."""
    from froide_fax.models import FaxOverride

    site = Site.objects.get(id=1)
    jurisdiction = JurisdictionFactory.create(name="Wien")
    FoiLawFactory.create(site=site, jurisdiction=jurisdiction, name="AuskunftsG")

    fax_pb = PublicBodyFactory(
        name=FAX_NAME, jurisdiction=jurisdiction, site=site, fax="+4315811234"
    )
    FaxOverride.objects.create(publicbody=fax_pb, enabled=True)
    email_pb = PublicBodyFactory(
        name=EMAIL_NAME, jurisdiction=jurisdiction, site=site, fax="+4315811235"
    )
    rebuild_index()
    return fax_pb, email_pb


async def _open_chooser(page, live_server):
    """Land on the make-request page with the public body chooser showing.

    The first .btn-primary advances past the "search existing requests" step.
    Wait for the chooser's own search field rather than clicking straight away:
    the button only exists once the Vue app has mounted, and clicking too early
    lands on a different control.
    """
    await page.goto(live_server.url + reverse("foirequest-make_request"))
    await page.locator("request-page .btn-primary >> nth=0").click()
    await expect(page.locator(SEARCH)).to_be_visible()


async def _choose(page, name):
    """Search for a body and pick it, the way froide's own live tests do.

    The search reacts to keyup (see publicbody-beta-chooser.vue), so the submit
    click is what actually fires it -- fill() alone emits only `input`.
    """
    await page.locator(SEARCH).fill(name)
    await page.locator(".search-public_bodies-submit").click()
    await page.locator(".search-results .search-result .btn >> nth=0").click()


@pytest.mark.django_db
@pytest.mark.elasticsearch
@pytest.mark.xdist_group(name="sequential")
@pytest.mark.asyncio(loop_scope="session")
async def test_notice_appears_for_a_fax_body(page, live_server, fax_publicbodies):
    notice = page.locator(NOTICE)
    await _open_chooser(page, live_server)
    await expect(notice).to_be_hidden()

    await _choose(page, FAX_NAME)
    await expect(notice).to_be_visible()


@pytest.mark.django_db
@pytest.mark.elasticsearch
@pytest.mark.xdist_group(name="sequential")
@pytest.mark.asyncio(loop_scope="session")
async def test_notice_stays_hidden_for_an_ordinary_body(
    page, live_server, fax_publicbodies
):
    """A fax-only body exists, but the one chosen is not it."""
    notice = page.locator(NOTICE)
    await _open_chooser(page, live_server)
    await _choose(page, EMAIL_NAME)
    await expect(notice).to_be_hidden()


@pytest.mark.django_db
@pytest.mark.elasticsearch
@pytest.mark.xdist_group(name="sequential")
@pytest.mark.asyncio(loop_scope="session")
async def test_preselected_body_needs_no_script(page, live_server, fax_publicbodies):
    """Server-rendered visibility, so the notice survives a script failure."""
    fax_pb, _ = fax_publicbodies
    await page.goto(
        live_server.url
        + reverse("foirequest-make_request", kwargs={"publicbody_slug": fax_pb.slug})
    )
    await expect(page.locator(NOTICE)).to_be_visible()
