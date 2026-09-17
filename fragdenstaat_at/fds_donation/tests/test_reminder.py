from datetime import datetime, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

import pytest
from froide_payment.models import Order, Payment

from ..services import (
    DONATION_SPAM_COUNT,
    INCOMPLETE_DONATION_NOTE,
    REMIND_INCOMPLETE_AFTER_DAYS,
    REMINDER_TEXT,
    get_incomplete_donations_to_remind,
    get_unreceived_banktransfers_to_remind,
    send_incomplete_donation_reminder,
)
from .factories import DonationFactory, DonorFactory


@pytest.mark.django_db
def test_incomplete_donations_remind_not_yet():
    timestamp = timezone.now()
    donor = DonorFactory(email="test@example.com")
    DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    assert len(list(get_incomplete_donations_to_remind())) == 0


@pytest.mark.django_db
def test_incomplete_donations_remind():
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    assert len(list(get_incomplete_donations_to_remind())) == 1


@pytest.mark.django_db
def test_incomplete_donations_remind_not_if_donor_donated_after():
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    DonationFactory(
        donor=donor, completed=True, timestamp=timestamp + timedelta(minutes=1)
    )
    assert len(list(get_incomplete_donations_to_remind())) == 0


@pytest.mark.django_db
def test_incomplete_donations_remind_not_if_email_donated_after():
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    donor_2 = DonorFactory(email="test@example.com")
    DonationFactory(
        donor=donor_2, completed=True, timestamp=timestamp + timedelta(minutes=1)
    )
    assert len(list(get_incomplete_donations_to_remind())) == 0


@pytest.mark.django_db
def test_incomplete_donations_remind_not_if_email_donated_shortly_before():
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    DonationFactory(
        donor=donor, completed=True, timestamp=timestamp - timedelta(days=2)
    )
    assert len(list(get_incomplete_donations_to_remind())) == 0


@pytest.mark.django_db
def test_incomplete_donations_ignore_if_spam():
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    for _ in range(0, DONATION_SPAM_COUNT):
        DonationFactory(donor=donor, completed=False, timestamp=timestamp)
    assert len(list(get_incomplete_donations_to_remind())) == 0


@pytest.mark.django_db
def test_send_incomplete_reminder(mailoutbox):
    timestamp = timezone.now() - timedelta(days=REMIND_INCOMPLETE_AFTER_DAYS)
    donor = DonorFactory(email="test@example.com")
    amount = Decimal("10.00")
    order = Order.objects.create(
        user_email=donor.email,
        total_net=amount,
        total_gross=amount,
        is_donation=True,
    )
    payment = Payment.objects.create(order=order, variant="sepa")
    donation = DonationFactory(
        method="sepa",
        donor=donor,
        completed=False,
        timestamp=timestamp,
        payment=payment,
        order=order,
    )
    send_incomplete_donation_reminder(donation)
    donation.refresh_from_db()
    assert donation.email_sent is not None
    assert INCOMPLETE_DONATION_NOTE in donation.note
    assert donor.email_confirmation_sent is not None

    assert len(mailoutbox) == 1
    m = mailoutbox[0]
    donate_url = reverse("fds_donation:donor-donate")
    assert f"{donate_url}?initial_amount={donation.amount}" in m.body
    assert reverse("fds_donation:donor") in m.body
    assert list(m.to) == [donor.email]


# --- remind_unreceived_banktransfers -----------------------------------------
#
# base_date is fixed to the 15th so "last month" is unambiguous:
# window = [Aug 28 00:00, Sep 27 00:00) with the 4-day bank delay.

BASE = timezone.make_aware(datetime(2026, 10, 15, 12, 0))
IN_WINDOW = timezone.make_aware(datetime(2026, 9, 10, 12, 0))


def _unreceived(donor, **kwargs):
    kwargs.setdefault("timestamp", IN_WINDOW)
    kwargs.setdefault("completed", True)
    kwargs.setdefault("received_timestamp", None)
    return DonationFactory(donor=donor, **kwargs)


@pytest.mark.django_db
def test_unreceived_banktransfer_due():
    donor = DonorFactory()
    donation = _unreceived(donor)
    assert list(get_unreceived_banktransfers_to_remind(BASE)) == [donation]


@pytest.mark.django_db
def test_unreceived_banktransfer_window_edges():
    donor = DonorFactory()
    # Just inside both edges (bank delay shifts the month back by 4 days)
    first = _unreceived(donor, timestamp=timezone.make_aware(datetime(2026, 8, 28)))
    last = _unreceived(
        donor, timestamp=timezone.make_aware(datetime(2026, 9, 26, 23, 59))
    )
    # Just outside
    _unreceived(donor, timestamp=timezone.make_aware(datetime(2026, 8, 27, 23, 59)))
    _unreceived(donor, timestamp=timezone.make_aware(datetime(2026, 9, 27)))
    assert set(get_unreceived_banktransfers_to_remind(BASE)) == {first, last}


@pytest.mark.django_db
def test_unreceived_banktransfer_skips_wrong_state():
    donor = DonorFactory()
    _unreceived(donor, received_timestamp=IN_WINDOW)
    _unreceived(donor, completed=False)
    _unreceived(donor, method="paypal")
    _unreceived(donor, note="foo\n%s 2026-10-01" % REMINDER_TEXT)
    assert list(get_unreceived_banktransfers_to_remind(BASE)) == []


@pytest.mark.django_db
def test_unreceived_banktransfer_respects_minimum_age():
    donor = DonorFactory()
    # Triggered by hand early in the month: the window is still last month,
    # but the tail of it is under 14 days old and must wait.
    early = timezone.make_aware(datetime(2026, 10, 3, 12, 0))
    _unreceived(donor, timestamp=timezone.make_aware(datetime(2026, 9, 26)))
    old = _unreceived(donor, timestamp=timezone.make_aware(datetime(2026, 9, 5)))
    assert list(get_unreceived_banktransfers_to_remind(early)) == [old]


@pytest.mark.django_db
def test_unreceived_banktransfer_skips_donor_who_paid_since():
    donor = DonorFactory()
    _unreceived(donor)
    DonationFactory(
        donor=donor,
        completed=True,
        timestamp=IN_WINDOW + timedelta(days=3),
        received_timestamp=IN_WINDOW + timedelta(days=5),
    )
    assert list(get_unreceived_banktransfers_to_remind(BASE)) == []

    # ...but an earlier received donation does not count
    other = DonorFactory()
    due = _unreceived(other)
    DonationFactory(
        donor=other,
        completed=True,
        timestamp=timezone.make_aware(datetime(2026, 8, 1)),
        received_timestamp=timezone.make_aware(datetime(2026, 8, 3)),
    )
    assert list(get_unreceived_banktransfers_to_remind(BASE)) == [due]
