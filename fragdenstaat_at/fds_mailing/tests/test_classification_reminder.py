from datetime import timedelta

from django.core import mail
from django.utils import timezone

import pytest

from froide.foirequest.models import FoiRequest
from froide.foirequest.tasks import classification_reminder
from froide.foirequest.tests.factories import FoiRequestFactory

from ..middleware import (
    StaleClassificationReminderMiddleware,
    should_send_classification_reminder,
)


def make_unclassified(last_message):
    return FoiRequestFactory.create(
        status=FoiRequest.STATUS.AWAITING_CLASSIFICATION,
        last_message=last_message,
    )


@pytest.mark.django_db
def test_recent_unclassified_request_gets_reminder():
    fr = make_unclassified(timezone.now() - timedelta(days=10))
    mail.outbox = []
    classification_reminder()
    assert [m.to for m in mail.outbox] == [[fr.user.email]]


@pytest.mark.django_db
@pytest.mark.parametrize("age_days", [31, 59, 68, 365 * 4])
def test_stale_unclassified_request_gets_no_reminder(age_days):
    make_unclassified(timezone.now() - timedelta(days=age_days))
    mail.outbox = []
    classification_reminder()
    assert mail.outbox == []


@pytest.mark.django_db
def test_final_reminder_around_day_60():
    fr = make_unclassified(timezone.now() - timedelta(days=62))
    mail.outbox = []
    classification_reminder()
    assert [m.to for m in mail.outbox] == [[fr.user.email]]


@pytest.mark.parametrize("weekday_offset", range(7))
def test_reminder_schedule_over_time(weekday_offset):
    """Simulate the weekly task: 3-4 reminders in the first month, one at ~60."""
    last_message = timezone.now()
    first_run = last_message + timedelta(days=weekday_offset, hours=1)
    sent_ages = []
    for week in range(52):
        run = first_run + timedelta(weeks=week)
        age = run - last_message
        # froide's own lower bound in get_unclassified()
        if age > timedelta(days=4) and should_send_classification_reminder(
            last_message, now=run
        ):
            sent_ages.append(age.days)
    early = [a for a in sent_ages if a < 30]
    late = [a for a in sent_ages if a >= 30]
    assert 3 <= len(early) <= 4
    assert len(late) == 1 and 60 <= late[0] < 67


@pytest.mark.django_db
def test_stale_request_stays_in_moderation_queue():
    fr = make_unclassified(timezone.now() - timedelta(days=365 * 4))
    assert fr in FoiRequest.objects.get_unclassified_for_moderation()


@pytest.mark.django_db
def test_other_intents_are_not_filtered():
    fr = make_unclassified(timezone.now() - timedelta(days=365 * 4))
    middleware = StaleClassificationReminderMiddleware()
    assert (
        middleware.should_mail(
            "foirequest/emails/became_overdue", {"foirequest": fr}, {}
        )
        is None
    )
