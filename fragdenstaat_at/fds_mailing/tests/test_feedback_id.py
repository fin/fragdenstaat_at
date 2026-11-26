"""Google FBL Feedback-ID: AT's variant of DE 40179bb7 (P7.2 group 3)."""

from types import SimpleNamespace

from django.core import mail

import pytest

from froide.foirequest.models import FoiRequest
from froide.foirequest.notifications import send_classification_reminder
from froide.foirequest.tests.factories import FoiRequestFactory

from ..middleware import FeedbackIdMailMiddleware
from ..utils import (
    make_feedback_id,
    make_intent_feedback_id,
    make_mailing_feedback_id,
)


def test_format_has_four_fields_and_no_customer_id():
    value = make_feedback_id(campaign_id="mailing-7", mail_type="newsletter")
    assert value == "mailing-7::newsletter:fragdenstaat.at"


def test_fields_cannot_smuggle_in_separators():
    value = make_feedback_id(campaign_id="a:b c", mail_type="x/y")
    assert value.count(":") == 3
    assert value == "a-b-c::x-y:fragdenstaat.at"


def test_mailing_uses_newsletter_slug_as_mail_type():
    with_newsletter = SimpleNamespace(
        mailing=SimpleNamespace(
            id=7, newsletter_id=1, newsletter=SimpleNamespace(slug="weekly")
        ),
        subscriber=SimpleNamespace(id=12345),
    )
    without = SimpleNamespace(
        mailing=SimpleNamespace(id=8, newsletter_id=None, newsletter=None),
        subscriber=None,
    )
    assert (
        make_mailing_feedback_id(with_newsletter) == "mailing-7::weekly:fragdenstaat.at"
    )
    assert make_mailing_feedback_id(without) == "mailing-8::mailing:fragdenstaat.at"
    # never the subscriber id
    assert "12345" not in make_mailing_feedback_id(with_newsletter)


def test_intent_feedback_id():
    assert (
        make_intent_feedback_id("foirequest/emails/classification_reminder")
        == "::foirequest.emails.classification_reminder:fragdenstaat.at"
    )


def test_middleware_keeps_existing_headers():
    result = FeedbackIdMailMiddleware().enhance_email_kwargs(
        "foirequest/emails/classification_reminder",
        {},
        {"headers": {"References": "<x@y>", "In-Reply-To": "<x@y>"}},
    )
    assert result["headers"]["References"] == "<x@y>"
    assert result["headers"]["In-Reply-To"] == "<x@y>"
    assert result["headers"]["Feedback-ID"].endswith(":fragdenstaat.at")


def test_middleware_does_not_override_an_explicit_feedback_id():
    result = FeedbackIdMailMiddleware().enhance_email_kwargs(
        "some/intent", {}, {"headers": {"Feedback-ID": "explicit"}}
    )
    assert result["headers"]["Feedback-ID"] == "explicit"


@pytest.mark.django_db
def test_transactional_mail_carries_header_end_to_end():
    fr = FoiRequestFactory.create(status=FoiRequest.STATUS.AWAITING_CLASSIFICATION)
    mail.outbox = []
    send_classification_reminder(fr)
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.extra_headers["Feedback-ID"] == (
        "::foirequest.emails.classification_reminder:fragdenstaat.at"
    )
    # froide's own threading headers survive the merge
    assert "References" in message.extra_headers
