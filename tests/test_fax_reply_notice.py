"""The "this message will be sent by fax" notice on the reply form.

A usable FaxOverride diverts a reply to fax only when the address picked in "To"
is the public body's own default (froide-fax keys the routing on
recipient_email). The notice element is rendered whenever the request *could*
fax a reply and starts hidden; a small script unhides it while the fax-only
address is the selected radio.

These tests cover the server-rendered half: whether the element, its
data-fax-address, and the toggle script are in the page, and that it starts
hidden. The runtime show/hide (a ~15-line inline script keyed on the selected
"To" radio) is left uncovered -- it needs no frontend build and is small enough
to read.
"""

from django.urls import reverse

import pytest
from froide_fax.models import FaxOverride

from froide.foirequest.tests import factories
from froide.publicbody.factories import PublicBodyFactory

HEADING = "This message will be sent by fax"
MARKER = "data-fax-reply-notice"
FAX_NUMBER = "+4315811234"

pytestmark = pytest.mark.django_db


def _make_request(with_override=True, fax=FAX_NUMBER, email=None):
    pb = PublicBodyFactory(fax=fax)
    if email is not None:
        pb.email = email
        pb.save()
    if with_override:
        FaxOverride.objects.create(publicbody=pb, enabled=True)
    fr = factories.FoiRequestFactory(public_body=pb)
    # get_send_message_form() reads foirequest.messages[-1]; give it one.
    factories.FoiMessageFactory(
        request=fr,
        sender_user=fr.user,
        recipient_public_body=pb,
        is_response=False,
        status=None,
    )
    return fr


def _get_page(client, foirequest):
    client.force_login(foirequest.user)
    return client.get(
        reverse("foirequest-show", kwargs={"slug": foirequest.slug})
    ).content.decode("utf-8", "replace")


def test_notice_rendered_for_a_fax_only_request(client):
    fr = _make_request()
    html = _get_page(client, fr)
    assert HEADING in html
    assert MARKER in html
    assert 'data-fax-address="%s"' % fr.public_body.email in html
    # rendered hidden; the toggle script decides visibility
    notice_tag = html.split(MARKER, 1)[1].split(">", 1)[0]
    assert "hidden" in notice_tag


def test_no_notice_without_an_override(client):
    fr = _make_request(with_override=False)
    assert MARKER not in _get_page(client, fr)


def test_no_notice_when_the_override_is_undialable(client):
    fr = _make_request(fax="")
    assert MARKER not in _get_page(client, fr)


def test_no_notice_when_the_public_body_has_no_default_address(client):
    """Nothing to compare the selected "To" against, so a reply can only email."""
    fr = _make_request(email="")
    assert MARKER not in _get_page(client, fr)


def test_no_notice_when_the_fax_handler_is_not_registered(client, monkeypatch):
    monkeypatch.setattr(
        "fragdenstaat_at.theme.templatetags.fds_tags._fax_handler_registered",
        lambda: False,
    )
    fr = _make_request()
    assert MARKER not in _get_page(client, fr)
