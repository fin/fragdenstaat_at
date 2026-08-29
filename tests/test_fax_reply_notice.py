"""The "this message will be sent by fax" notice on the reply form.

froide_fax's FaxOverride routes *every* outgoing message on the request to fax,
follow-ups included, so a reply sent from the message form is faxed no matter
which address is picked in "To". froide's send-message form does not say so;
this notice, injected via the send_message_form_pre block, does.
"""

from django.urls import reverse

import pytest
from froide_fax.models import FaxOverride

from froide.foirequest.tests import factories
from froide.publicbody.factories import PublicBodyFactory

HEADING = "This message will be sent by fax"
FAX_NUMBER = "+4315811234"

pytestmark = pytest.mark.django_db


def _make_request(with_override=True, fax=FAX_NUMBER):
    pb = PublicBodyFactory(fax=fax)
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


def test_notice_shown_on_a_fax_only_request(client):
    fr = _make_request()
    assert HEADING in _get_page(client, fr)


def test_no_notice_without_an_override(client):
    fr = _make_request(with_override=False)
    assert HEADING not in _get_page(client, fr)


def test_no_notice_when_the_override_is_undialable(client):
    fr = _make_request(fax="")
    assert HEADING not in _get_page(client, fr)


def test_no_notice_when_the_fax_handler_is_not_registered(client, monkeypatch):
    monkeypatch.setattr(
        "fragdenstaat_at.theme.templatetags.fds_tags._fax_handler_registered",
        lambda: False,
    )
    fr = _make_request()
    assert HEADING not in _get_page(client, fr)
