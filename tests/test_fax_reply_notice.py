"""The reply-form notice about fax vs email for a fax-only public body.

froide-fax diverts a reply to fax only when it is addressed to the public
body's own default address; other addresses in "To" are emailed. The notice
(injected via the send_message_form_pre block) states that split. It renders
whenever the request could fax a reply and the public body has a default
address to name.
"""

from django.urls import reverse

import pytest
from froide_fax.models import FaxOverride

from froide.foirequest.tests import factories
from froide.publicbody.factories import PublicBodyFactory

HEADING = "Replies to the default address are sent by fax"
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


def test_notice_shown_and_names_the_default_address(client):
    fr = _make_request()
    html = _get_page(client, fr)
    assert HEADING in html
    assert fr.public_body.email in html


def test_no_notice_without_an_override(client):
    fr = _make_request(with_override=False)
    assert HEADING not in _get_page(client, fr)


def test_no_notice_when_the_override_is_undialable(client):
    fr = _make_request(fax="")
    assert HEADING not in _get_page(client, fr)


def test_no_notice_when_the_public_body_has_no_default_address(client):
    """Nothing to name, and a reply can only email."""
    fr = _make_request(email="")
    assert HEADING not in _get_page(client, fr)


def test_no_notice_when_the_fax_handler_is_not_registered(client, monkeypatch):
    monkeypatch.setattr(
        "fragdenstaat_at.theme.templatetags.fds_tags._fax_handler_registered",
        lambda: False,
    )
    fr = _make_request()
    assert HEADING not in _get_page(client, fr)
