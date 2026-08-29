"""The "sent by fax" notice on /anfrage-stellen/.

Some Austrian authorities refuse electronic requests, so froide_fax's
FaxOverride diverts the request to fax *instead of* email. That is a material
difference for the requester, and nothing on the request form said so.

Template-only, overriding froide's foirequest/request.html. Which bounds what
can be tested: it covers a public body chosen server-side (arriving from a
public body page, or /anfrage-stellen/to/<slug>/). Choosing one in the chooser
on the page itself is client-side and re-renders no template.
"""

from django.urls import reverse

import pytest
from froide_fax.models import FaxOverride

from froide.publicbody.factories import PublicBodyFactory

HEADING = "This request will be sent by fax"
FAX_NUMBER = "+4315811234"

pytestmark = pytest.mark.django_db


def _url(publicbody):
    return reverse(
        "foirequest-make_request", kwargs={"publicbody_slug": publicbody.slug}
    )


def test_notice_shown_for_a_fax_only_public_body(client):
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=pb, enabled=True)
    response = client.get(_url(pb))
    assert response.status_code == 200
    body = response.content.decode("utf-8", "replace")
    assert HEADING in body
    # Deliberately no public body name in the message: the script reuses this
    # same element when the chooser changes the selection, and a name baked in
    # server-side would then be describing the wrong body.
    assert pb.name not in _notice(body)


def test_no_notice_without_an_override(client):
    """The ordinary case: email delivery, nothing to say."""
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    response = client.get(_url(pb))
    assert response.status_code == 200
    assert HEADING not in response.content.decode("utf-8", "replace")


def test_no_notice_when_the_override_is_disabled(client):
    """`enabled` is the off switch that keeps the row; honour it."""
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=pb, enabled=False)
    response = client.get(_url(pb))
    assert HEADING not in response.content.decode("utf-8", "replace")


def test_no_notice_when_the_number_is_not_dialable(client):
    """An override we cannot dial diverts nothing, so it must not warn.

    FaxOverride.is_usable is `enabled and bool(number)`; with no number on the
    public body and none on the override there is nothing to dial.
    """
    pb = PublicBodyFactory(fax="")
    FaxOverride.objects.create(publicbody=pb, enabled=True)
    response = client.get(_url(pb))
    assert HEADING not in response.content.decode("utf-8", "replace")


def test_page_still_renders_when_no_body_is_preselected(client):
    """The bare form: `publicbodies` is empty and the lookup must stay quiet."""
    response = client.get(reverse("foirequest-make_request"))
    assert response.status_code == 200
    assert HEADING not in response.content.decode("utf-8", "replace")


def test_no_notice_when_the_fax_handler_is_not_registered(client, monkeypatch):
    """Without the fax MessageHandler in FROIDE_CONFIG, froide routes the
    request to email regardless of the override, so promising a fax would lie.
    """
    monkeypatch.setattr(
        "fragdenstaat_at.theme.templatetags.fds_tags._fax_handler_registered",
        lambda: False,
    )
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=pb, enabled=True)
    html = client.get(_url(pb)).content.decode("utf-8", "replace")
    assert HEADING not in html
    assert 'id="fds-fax-delivery-notice"' not in html


def _notice(html):
    """The notice element's opening tag, or None."""
    import re

    match = re.search(r"<div id=\"fds-fax-delivery-notice\"[^>]*>", html)
    return match.group(0) if match else None


def test_notice_is_rendered_hidden_for_a_normal_body(client):
    """When some *other* body is fax-only, the notice is present but hidden.

    It has to be in the DOM for the script to unhide when the chooser lands on
    a fax-only body -- but it must not be visible until then.
    """
    fax_pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=fax_pb, enabled=True)
    normal_pb = PublicBodyFactory(fax=FAX_NUMBER)

    html = client.get(_url(normal_pb)).content.decode("utf-8", "replace")
    tag = _notice(html)
    assert tag is not None, "notice missing, so the script has nothing to show"
    assert "hidden" in tag, "notice visible for a body that is not fax-only"


def test_visible_notice_carries_no_hidden_attribute(client):
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=pb, enabled=True)
    tag = _notice(client.get(_url(pb)).content.decode("utf-8", "replace"))
    assert tag is not None
    assert "hidden" not in tag


def test_data_attribute_lists_only_divertable_bodies(client):
    """What the script tests membership against."""
    divertable = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=divertable, enabled=True)
    disabled = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=disabled, enabled=False)
    undialable = PublicBodyFactory(fax="")
    FaxOverride.objects.create(publicbody=undialable, enabled=True)

    tag = _notice(client.get(_url(divertable)).content.decode("utf-8", "replace"))
    ids = tag.split('data-fax-publicbody-ids="')[1].split('"')[0].split(",")
    assert ids == [str(divertable.pk)]


def test_nothing_rendered_when_no_body_is_fax_only(client):
    """No overrides at all: no element, no data attribute, no script work."""
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    html = client.get(_url(pb)).content.decode("utf-8", "replace")
    assert _notice(html) is None


def test_both_wording_variants_are_available_to_the_script(client):
    """The script picks the wording, so both variants must reach the page.

    Composed client-side because it depends on how many bodies are selected and
    how many are diverted, which is not known when the template renders. They
    are translated here so gettext can still see them.

    Not covered end to end: reaching a multi-body selection needs the project
    flow -- /anfrage-stellen/an/<id>+<id>/ returns 404 -- so the multi-body
    wording itself is unverified in a browser.
    """
    pb = PublicBodyFactory(fax=FAX_NUMBER)
    FaxOverride.objects.create(publicbody=pb, enabled=True)
    tag = _notice(client.get(_url(pb)).content.decode("utf-8", "replace"))

    for attribute in (
        "data-fax-heading-single",
        "data-fax-heading-multiple",
        "data-fax-message-single",
        "data-fax-message-multiple",
    ):
        assert attribute in tag, attribute
    # The placeholders the script substitutes.
    assert "{count}" in tag and "{total}" in tag
