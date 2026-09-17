import os
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

import pytest
from froide_payment.models import Order, Payment, PaymentStatus
from froide_payment.provider.banktransfer import generate_transfer_code

from froide.account.factories import UserFactory

from ..external import find_donation, import_banktransfer, import_banktransfers
from ..models import Donation, Donor
from ..tasks import import_banktransfers_task
from .factories import DonationFactory, DonorFactory, make_banktransfer_donation


@pytest.mark.django_db
def test_import_banktransfer_new_iban():
    transfer_code = generate_transfer_code()
    donor = DonorFactory.create(attributes={"iban": "DE0"})
    donation = DonationFactory.create(
        donor=donor,
        payment=Payment.objects.create(
            transaction_id=transfer_code, order=Order.objects.create()
        ),
    )

    iban = "DE1"
    row = {
        "reference": transfer_code,
        "iban": iban,
    }
    found_donation = find_donation("no-ident", row)
    assert found_donation == donation
    donor = found_donation.donor
    donor.refresh_from_db()
    assert donor.attributes["iban"] == iban
    assert iban in donor.attributes["ibans"]


@pytest.mark.django_db
def test_import_banktransfer_subscription_active():
    donor = DonorFactory.create()
    now = timezone.now()
    first_date = now
    amount = Decimal("10.00")
    donation = make_banktransfer_donation(donor, amount, first_date)
    transfer_code = donation.payment.transaction_id

    iban = "DE1"
    row = {
        "reference": transfer_code,
        "iban": iban,
        "amount": amount,
        "date": first_date,
        "date_received": first_date,
    }
    import_banktransfer(transfer_code, row, settings.DONATION_PROJECTS[0][0])

    payment = donation.payment
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.CONFIRMED
    assert payment.captured_amount == amount
    assert payment.received_amount == amount
    assert payment.received_timestamp == first_date

    subscription = payment.order.subscription
    subscription.refresh_from_db()
    assert subscription.active is True


@pytest.mark.django_db
def test_import_banktransfer_purpose(donor):
    now = timezone.now()
    first_date = now
    amount = Decimal("10.00")
    donation = make_banktransfer_donation(donor, amount, first_date)
    transfer_code = donation.payment.transaction_id

    assert donation.purpose == ""

    iban = "DE1"
    row = {
        "reference": transfer_code,
        "iban": iban,
        "amount": amount,
        "date": first_date,
        "date_received": first_date,
        "purpose": "TEST-PURP",
    }
    import_banktransfer(transfer_code, row, settings.DONATION_PROJECTS[0][0])

    payment = donation.payment
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.CONFIRMED

    donation.refresh_from_db()
    assert donation.purpose == "TEST-PURP"

    subscription = payment.order.subscription
    subscription.refresh_from_db()
    assert subscription.active is True


CSV_HEADER = "identifier,reference,amount,date_received,iban,date,purpose,name\n"


def write_csv(tmp_path, lines, header=CSV_HEADER):
    path = tmp_path / "transfers.csv"
    path.write_text(header + "".join(line + "\n" for line in lines), encoding="utf-8")
    return str(path)


@pytest.mark.django_db
def test_import_banktransfers_csv(tmp_path):
    donor = DonorFactory.create()
    amount = Decimal("10.00")
    donation = make_banktransfer_donation(donor, amount, timezone.now())
    transfer_code = donation.payment.transaction_id
    donor_count = Donor.objects.count()
    donation_count = Donation.objects.count()

    path = write_csv(
        tmp_path,
        [
            f"TX1,Spende {transfer_code},10.00,2026-09-01,AT611904300234573201,2026-08-31,,Jane Doe",
            "TX2,Spende ohne Code,5.00,2026-09-02,AT021100000123456789,,,Unknown Person",
        ],
    )
    result = import_banktransfers(path, settings.DONATION_PROJECTS[0][0])

    assert result.matched == 1
    assert result.created == 0
    assert len(result.unmatched) == 1
    assert "Unknown Person" in result.unmatched[0]
    assert "AT021100000123456789" in result.unmatched[0]
    # Unknown transfers create neither donors nor donations
    assert Donor.objects.count() == donor_count
    assert Donation.objects.count() == donation_count

    donation.refresh_from_db()
    assert donation.identifier == "TX1"
    assert donation.amount_received == amount
    assert timezone.localtime(donation.received_timestamp).isoformat() == (
        "2026-09-01T00:00:00+02:00"
    )
    donation.payment.refresh_from_db()
    assert donation.payment.status == PaymentStatus.CONFIRMED
    donor.refresh_from_db()
    assert donor.attributes["iban"] == "AT611904300234573201"


@pytest.mark.django_db
def test_import_banktransfers_csv_recurring_follow_up_and_idempotent(tmp_path):
    donor = DonorFactory.create()
    donation = make_banktransfer_donation(donor, Decimal("10.00"), timezone.now())
    transfer_code = donation.payment.transaction_id
    project = settings.DONATION_PROJECTS[0][0]

    import_banktransfers(
        write_csv(tmp_path, [f"TX1,{transfer_code},10.00,2026-08-01,AT1,,,"]), project
    )
    # Second transfer with the same code: donation is already claimed, so a
    # follow-up donation is created for the known donor.
    path = write_csv(tmp_path, [f"TX2,{transfer_code},10.00,2026-09-01,AT1,,,"])
    result = import_banktransfers(path, project)
    assert result.created == 1
    assert result.matched == 0
    follow_up = Donation.objects.get(identifier="TX2")
    assert follow_up.donor == donor
    assert follow_up.payment is None
    assert follow_up.method == "banktransfer"
    assert follow_up.completed is True
    assert follow_up.amount_received == Decimal("10.00")

    # Re-running the same file only updates, it does not duplicate
    donation_count = Donation.objects.count()
    result = import_banktransfers(path, project)
    assert result.matched == 1
    assert result.created == 0
    assert Donation.objects.count() == donation_count


@pytest.mark.django_db
def test_import_banktransfers_csv_without_identifier_and_german_formats(tmp_path):
    donor = DonorFactory.create()
    donation = make_banktransfer_donation(donor, Decimal("1234.50"), timezone.now())
    transfer_code = donation.payment.transaction_id
    project = settings.DONATION_PROJECTS[0][0]

    path = write_csv(
        tmp_path,
        [
            f"{transfer_code};1.234,50;01.09.2026",
            f"{transfer_code};1.234,50;01.09.2026",
        ],
        header="reference;amount;date_received\n",
    )
    result = import_banktransfers(path, project)
    assert result.matched == 1
    assert result.created == 1
    donation.refresh_from_db()
    assert donation.amount_received == Decimal("1234.50")
    assert donation.identifier == f"2026-09-01-{transfer_code}-1234.50-"
    # Identical transfers on the same day get distinct identifiers
    assert Donation.objects.filter(
        identifier=f"2026-09-01-{transfer_code}-1234.50--2"
    ).exists()

    donation_count = Donation.objects.count()
    result = import_banktransfers(path, project)
    assert (result.matched, result.created) == (2, 0)
    assert Donation.objects.count() == donation_count


@pytest.mark.django_db
def test_import_banktransfers_csv_rejects_bad_files(tmp_path):
    project = settings.DONATION_PROJECTS[0][0]
    donation_count = Donation.objects.count()

    with pytest.raises(ValueError, match="missing columns: date_received"):
        import_banktransfers(
            write_csv(tmp_path, ["FDS 1,1"], header="reference,amount\n"), project
        )
    with pytest.raises(ValueError, match="line 3"):
        import_banktransfers(
            write_csv(
                tmp_path,
                ["FDS ACDEFHJK,1.00,2026-09-01", "FDS ACDEFHJK,1.00,not-a-date"],
                header="reference,amount,date_received\n",
            ),
            project,
        )
    assert Donation.objects.count() == donation_count


@pytest.mark.django_db
def test_import_banktransfers_task(tmp_path, mailoutbox):
    user = UserFactory.create()
    donor = DonorFactory.create()
    donation = make_banktransfer_donation(donor, Decimal("10.00"), timezone.now())
    transfer_code = donation.payment.transaction_id
    project = settings.DONATION_PROJECTS[0][0]

    path = write_csv(
        tmp_path,
        [
            f"TX1,{transfer_code},10.00,2026-09-01,AT1,,,",
            "TX2,nothing,5.00,2026-09-02,AT2,,,Unknown Person",
        ],
    )
    import_banktransfers_task(path, project, user_id=user.id)

    assert not os.path.exists(path)
    donation.payment.refresh_from_db()
    assert donation.payment.status == PaymentStatus.CONFIRMED
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert project in mail.subject
    assert "Matched: 1" in mail.body
    assert "New: 0" in mail.body
    assert "Unmatched: 1" in mail.body
    assert "Unknown Person" in mail.body

    # Bad file: the uploader is told, nothing crashes silently in the worker
    path = write_csv(tmp_path, ["x"], header="nope\n")
    import_banktransfers_task(path, project, user_id=user.id)
    assert not os.path.exists(path)
    assert len(mailoutbox) == 2
    assert "failed" in mailoutbox[1].subject
    assert "missing columns" in mailoutbox[1].body
