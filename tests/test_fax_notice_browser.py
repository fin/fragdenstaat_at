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

from froide.account.factories import UserFactory
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


@pytest.fixture
def batch_user(db):
    """A user allowed to select several public bodies at once.

    can_create_batch() gates the multi chooser on superuser or the
    foirequest.create_batch permission, which is why this flow is invisible to
    an anonymous visitor.
    """
    return UserFactory(username="batch", is_superuser=True)


async def _login(page, live_server, user):
    await page.goto(live_server.url + reverse("account-login"))
    await page.fill("[name=username]", user.email)
    await page.fill("[name=password]", "froide")
    await page.locator('button.btn.btn-primary[type="submit"]').click()
    # AT overrides header.html, so froide's #navbaraccount-link does not exist;
    # the logout form is the marker that a session is established.
    await expect(
        page.locator('form[action="%s"]' % reverse("account-logout")).first
    ).to_have_count(1)


@pytest.mark.django_db
@pytest.mark.elasticsearch
@pytest.mark.xdist_group(name="sequential")
@pytest.mark.asyncio(loop_scope="session")
async def test_notice_in_the_multi_request_flow(
    page, live_server, fax_publicbodies, batch_user
):
    """Several bodies at once, only one of them served by fax.

    The multi chooser is a different component from the single one and keeps
    its own selection, so it needs covering separately -- reported as the
    notice not showing at all in this flow.
    """
    await _login(page, live_server, batch_user)
    await page.goto(live_server.url + reverse("foirequest-make_request"))
    await page.locator("request-page .btn-primary >> nth=0").click()
    await expect(page.locator(SEARCH)).to_be_visible()

    # Both fixtures share this word, so one search finds the pair.
    await page.locator(SEARCH).fill("Teststadt")
    await page.locator(".search-public_bodies-submit").click()
    await page.get_by_role("button", name="Alle").first.click()

    notice = page.locator(NOTICE)
    await expect(notice).to_be_visible()
    await expect(notice).to_contain_text("1 of the 2")


@pytest.mark.django_db
@pytest.mark.elasticsearch
@pytest.mark.xdist_group(name="sequential")
@pytest.mark.asyncio(loop_scope="session")
async def test_notice_when_bodies_are_ticked_one_by_one(
    page, live_server, fax_publicbodies, batch_user
):
    """Same flow, but adding each body individually rather than "select all".

    The multi list renders one checkbox per result; ticking them is the path a
    user actually takes when the search returns more than they want.
    """
    fax_pb, email_pb = fax_publicbodies
    await _login(page, live_server, batch_user)
    await page.goto(live_server.url + reverse("foirequest-make_request"))
    await page.locator("request-page .btn-primary >> nth=0").click()
    await expect(page.locator(SEARCH)).to_be_visible()

    await page.locator(SEARCH).fill("Teststadt")
    await page.locator(".search-public_bodies-submit").click()

    notice = page.locator(NOTICE)

    # Located by value, not by name: the multi list renders its checkboxes with
    # an empty name attribute, so input[name="publicbody"] matches nothing in
    # this flow. That is precisely why reading the DOM was the wrong source of
    # truth -- the whole multi-request flow was invisible to it -- and why the
    # store is not.
    def box(pk):
        return page.locator('input[type="checkbox"][value="%s"]' % pk)

    await expect(box(fax_pb.pk)).to_have_count(1)

    # The ordinary body alone: nothing to warn about.
    await box(email_pb.pk).check()
    await expect(notice).to_be_hidden()

    # Adding the fax-only body brings the notice, counting both.
    await box(fax_pb.pk).check()
    await expect(notice).to_be_visible()
    await expect(notice).to_contain_text("1 of the 2")

    # Removing it again takes the notice away.
    await box(fax_pb.pk).uncheck()
    await expect(notice).to_be_hidden()
