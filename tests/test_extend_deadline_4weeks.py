"""The AT-only "extend deadline by four weeks" button.

froide's own extend_deadline takes a count of the law's response-time unit
capped at 15 (days, for AT). This adds a flat four-week extension beside it --
theme.views.extend_deadline_four_weeks, rendered from the
foirequest_explain_deadline template block (no froide change).
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from froide.foirequest.models import FoiEvent
from froide.foirequest.tests import factories

pytestmark = pytest.mark.django_db

FOUR_WEEKS = timedelta(weeks=4)


def _request(status="awaiting_response", due_in_days=14):
    return factories.FoiRequestFactory(
        status=status,
        due_date=timezone.now() + timedelta(days=due_in_days),
    )


def _url(fr):
    return reverse("fds-extend-deadline-4weeks", kwargs={"slug": fr.slug})


def test_owner_extends_by_four_weeks(client):
    fr = _request()
    before = fr.due_date
    client.force_login(fr.user)

    response = client.post(_url(fr))

    assert response.status_code == 302
    fr.refresh_from_db()
    assert fr.due_date == before + FOUR_WEEKS


def test_creates_a_deadline_extended_event(client):
    fr = _request()
    client.force_login(fr.user)

    client.post(_url(fr))

    events = FoiEvent.objects.filter(request=fr, event_name="deadline_extended")
    assert events.exists()


def test_overdue_becomes_awaiting_response_when_the_new_date_is_future(client):
    # due date already passed -> status overdue; +4 weeks lands in the future.
    fr = _request(status="overdue", due_in_days=-2)
    client.force_login(fr.user)

    client.post(_url(fr))

    fr.refresh_from_db()
    assert fr.status == "awaiting_response"
    assert fr.due_date > timezone.now()


def test_still_overdue_when_four_weeks_is_not_enough(client):
    fr = _request(status="overdue", due_in_days=-40)
    client.force_login(fr.user)

    client.post(_url(fr))

    fr.refresh_from_db()
    assert fr.status == "overdue"


def test_anonymous_cannot_extend(client):
    fr = _request()
    before = fr.due_date

    response = client.post(_url(fr))

    # froide sends anonymous writers to the login page rather than a bare 403.
    assert response.status_code == 302
    assert "/account/login/" in response["Location"]
    fr.refresh_from_db()
    assert fr.due_date == before


def test_other_user_is_forbidden(client):
    fr = _request()
    before = fr.due_date
    client.force_login(factories.UserFactory())

    response = client.post(_url(fr))

    assert response.status_code == 403
    fr.refresh_from_db()
    assert fr.due_date == before


def test_get_is_not_allowed(client):
    fr = _request()
    client.force_login(fr.user)

    response = client.get(_url(fr))

    assert response.status_code == 405


def test_button_renders_and_keeps_froides_own_control(client):
    """Our button rides in the foirequest_explain_deadline block; froide's
    own day-based extend form must still be on the page."""
    fr = _request()
    factories.FoiMessageFactory(request=fr, sender_user=fr.user, is_response=False)
    client.force_login(fr.user)

    body = client.get(fr.get_absolute_url()).content.decode()

    froide_action = reverse("foirequest-extend_deadline", kwargs={"slug": fr.slug})
    ours = reverse("fds-extend-deadline-4weeks", kwargs={"slug": fr.slug})
    assert froide_action in body, "froide's own extend form went missing"
    assert ours in body, "our four-week button did not render"


def test_button_hidden_for_non_writers(client):
    fr = _request()
    factories.FoiMessageFactory(request=fr, sender_user=fr.user, is_response=False)

    body = client.get(fr.get_absolute_url()).content.decode()

    assert reverse("fds-extend-deadline-4weeks", kwargs={"slug": fr.slug}) not in body
