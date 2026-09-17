import csv
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import partial
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import reset_queries, transaction
from django.db.models import Q

import pandas as pd
from froide_payment.models import Payment, PaymentStatus
from froide_payment.provider.banktransfer import find_transfer_code

from .models import Donation, Donor, defer_donor_updates, update_donation_numbers
from .services import create_donation_from_payment, detect_recurring_on_donor
from .tasks import process_recurrence_task

BANKTRANSFER_CSV_REQUIRED = ("reference", "amount", "date_received")
BANKTRANSFER_CSV_OPTIONAL = ("identifier", "iban", "date", "purpose", "name")
BANKTRANSFER_CSV_COLUMNS = BANKTRANSFER_CSV_REQUIRED + BANKTRANSFER_CSV_OPTIONAL

logger = logging.getLogger(__name__)


class BanktransferFileError(ValueError):
    """The CSV was rejected during validation; nothing has been written."""


@dataclass
class BanktransferImportResult:
    matched: int = 0  # pending donations that received their transfer
    created: int = 0  # follow-up donations for known (recurring) donors
    unmatched: list[str] = field(default_factory=list)  # rows nobody claimed

    @property
    def count(self):
        return self.matched + self.created


def find_donation(transfer_ident, row):
    donation = Donation.objects.filter(identifier=transfer_ident).first()
    if donation is not None:
        return donation

    transfer_code = find_transfer_code(row["reference"])
    if transfer_code is None:
        return None

    donation = (
        Donation.objects.filter(payment__transaction_id=transfer_code, identifier="")
        .order_by("id")
        .first()
    )
    if donation is None:
        return None

    donor = donation.donor
    if donor:
        update_iban_on_donor(donor, row.get("iban"), row["reference"])
    return donation


def update_iban_on_donor(donor, iban, reference):
    # donor.attributes is a Postgres HStoreField: flat str -> str only, no
    # nested values. A Python list stored as a value gets stringified via
    # repr() on save; read back next time it's a *string*, which the old
    # code then wrapped in a new single-element list and stringified again
    # -- doubling in size on every save. Keep it as one flat, deduplicated,
    # ';'-joined string instead (IBANs can't contain ';').
    if not donor.attributes:
        donor.attributes = donor.attributes or {}
    raw_ibans = donor.attributes.get("ibans") or ""
    known_ibans = [v for v in raw_ibans.split(";") if v]
    previous_iban = donor.attributes.get("iban")
    if previous_iban and previous_iban not in known_ibans:
        known_ibans.append(previous_iban)
    if pd.notnull(iban) and iban:
        if iban not in known_ibans:
            known_ibans.append(iban)
        donor.attributes["iban"] = iban
    donor.attributes["ibans"] = ";".join(known_ibans)
    donor.attributes["banktransfer_reference"] = reference
    donor.save()


def find_known_donor(row):
    """
    Find the donor a transfer belongs to when no pending donation claims it,
    i.e. a follow-up transfer of a recurring donor. Only donors we already know
    are considered: first by the transfer code in the reference, then by IBAN.
    Never creates donors -- unknown transfers are handled outside the system.
    """
    transfer_code = find_transfer_code(row["reference"])
    if transfer_code is not None:
        donation = (
            Donation.objects.filter(payment__transaction_id=transfer_code)
            .order_by("id")
            .first()
        )
        if donation and donation.donor:
            update_iban_on_donor(donation.donor, row.get("iban"), row["reference"])
            return donation.donor

    iban = row.get("iban")
    if iban:
        return (
            Donor.objects.filter(Q(identifier=iban) | Q(attributes__iban=iban))
            .order_by("id")
            .first()
        )
    return None


def import_banktransfer(transfer_ident, row, project):
    """
    Returns "matched" if a pending donation received this transfer, "created"
    if a follow-up donation was created for a known donor, or None if the row
    could not be attributed to anyone (nothing is written in that case).
    """
    is_new = False
    donation = find_donation(transfer_ident, row)
    if donation is None:
        donor = find_known_donor(row)
        if donor is None:
            return None
        donation = Donation(
            donor=donor,
            completed=True,
            timestamp=row.get("date") or row["date_received"],
        )
        is_new = True
    else:
        donor = donation.donor

    donation.project = project
    donation.identifier = transfer_ident
    donation.amount = Decimal(str(row["amount"]))
    donation.amount_received = Decimal(str(row["amount"]))
    donation.received_timestamp = row["date_received"]
    if row.get("purpose"):
        donation.purpose = row["purpose"]
    donation.method = "banktransfer"
    donation.completed = True
    donation.save()

    detect_recurring_on_donor(donor)

    if donation.payment:
        payment = donation.payment
        if payment.status != PaymentStatus.CONFIRMED:
            payment.captured_amount = donation.amount
            payment.received_amount = donation.amount
            payment.received_timestamp = donation.received_timestamp
            payment.change_status_and_save(PaymentStatus.CONFIRMED)
    return "created" if is_new else "matched"


def parse_banktransfer_amount(value):
    value = value.strip().replace(" ", "")
    if "," in value and "." in value:
        # Both separators present: whichever comes last is the decimal one.
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")  # 1.234,50
        else:
            value = value.replace(",", "")  # 1,234.50
    elif "," in value:
        value = value.replace(",", ".")  # 10,50
    amount = Decimal(value)
    if amount <= 0:
        # Outgoing transfers / refunds are not donations
        raise ValueError(f"amount must be positive, got {amount}")
    return amount


def parse_banktransfer_date(value):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            naive = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
    raise ValueError(f"unrecognised date {value!r} (use YYYY-MM-DD)")


def read_banktransfer_csv(csv_file):
    """
    Parse the AT bank transfer CSV (see BANKTRANSFER_CSV_COLUMNS) into row
    dicts. Everything is validated up front so a bad row fails the whole file
    before anything is written.
    """
    if isinstance(csv_file, (str, os.PathLike)):
        with open(csv_file, encoding="utf-8-sig", newline="") as f:
            return read_banktransfer_csv(f)

    sample = csv_file.readline()
    csv_file.seek(0)
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(csv_file, delimiter=delimiter)
    columns = [c.strip().lower() for c in reader.fieldnames or []]
    missing = [c for c in BANKTRANSFER_CSV_REQUIRED if c not in columns]
    if missing:
        raise BanktransferFileError("missing columns: {}".format(", ".join(missing)))

    rows = []
    for raw in reader:
        raw = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if not any(raw.values()):
            continue
        row = {c: raw.get(c, "") for c in BANKTRANSFER_CSV_COLUMNS}
        try:
            row["amount"] = parse_banktransfer_amount(row["amount"])
            row["date_received"] = parse_banktransfer_date(row["date_received"])
            row["date"] = parse_banktransfer_date(row["date"]) if row["date"] else None
        except (ValueError, InvalidOperation) as e:
            raise BanktransferFileError(f"line {reader.line_num}: {e}") from e
        rows.append(row)
    return rows


def make_transfer_ident(row, seen):
    """
    Stable identifier for a transfer so re-importing a file is idempotent.
    Prefers the bank's own transaction id; otherwise derives one from the
    transfer, numbering identical transfers on the same day.
    """
    ident = row["identifier"] or "{date}-{ref}-{amount}-{iban}".format(
        date=row["date_received"].date().isoformat(),
        ref=row["reference"],
        amount=row["amount"],
        iban=row["iban"],
    )
    seen[ident] += 1
    if seen[ident] > 1:
        ident = f"{ident}-{seen[ident]}"
    return ident


def describe_banktransfer_row(row):
    return " | ".join(
        str(v)
        for v in (
            row["date_received"].date().isoformat(),
            row["amount"],
            row["name"],
            row["iban"],
            row["reference"],
        )
        if v
    )


def import_banktransfers(csv_file, project):
    """
    Import bank transfers that were already checked against the expected
    banktransfer donations. Rows that match neither a pending donation nor a
    known donor are reported back, not imported.
    """
    rows = read_banktransfer_csv(csv_file)
    total = len(rows)
    result = BanktransferImportResult()
    logger.info("Importing %d bank transfer row(s) for %s", total, project)
    # A recurring donor's transfers show up many times in one file. Without
    # this, every row re-renumbers and re-analyzes that donor's whole
    # donation history (see models.defer_donor_updates) -- once per row, and
    # twice per row with a payment (once directly, once via the
    # payment_status_changed signal). That's the compounding cost that made
    # imports of otherwise modest files stall and OOM. Collapse it to once
    # per touched donor, after the whole file is done.
    touched_donors: set[int] = set()
    try:
        with defer_donor_updates() as touched_donors:
            _import_banktransfer_rows(rows, project, result)
    finally:
        # Also on failure: every row before the failing one has already
        # committed, so its donor still needs renumbering / recurrence
        # detection, or those donations stay inconsistent until the next save.
        logger.info("Updating donation numbers for %d donor(s)", len(touched_donors))
        for donor_id in touched_donors:
            update_donation_numbers(donor_id)
            transaction.on_commit(partial(process_recurrence_task.delay, donor_id))
    logger.info(
        "Bank transfer import done: %d/%d rows (matched=%d created=%d unmatched=%d)",
        total,
        total,
        result.matched,
        result.created,
        len(result.unmatched),
    )
    return result


def _import_banktransfer_rows(rows, project, result):
    total = len(rows)
    seen = Counter()
    for lineno, row in enumerate(rows, start=1):
        # Django's DEBUG=True query log grows for the whole request/task; for a
        # large file that outgrows available memory faster than the import itself.
        if lineno % 20 == 0:
            reset_queries()
            logger.info(
                "Bank transfer import: %d/%d rows (matched=%d created=%d unmatched=%d)",
                lineno,
                total,
                result.matched,
                result.created,
                len(result.unmatched),
            )
        with transaction.atomic():
            transfer_ident = make_transfer_ident(row, seen)
            status = import_banktransfer(transfer_ident, row, project)
        if status == "matched":
            result.matched += 1
        elif status == "created":
            result.created += 1
        else:
            result.unmatched.append(describe_banktransfer_row(row))


def import_paypal(csv_file):
    df = pd.read_csv(csv_file)
    df["date"] = pd.to_datetime(
        df["Datum"] + " " + df["Uhrzeit"], format="%d.%m.%Y %H:%M:%S"
    ).dt.tz_localize(settings.TIME_ZONE)
    df["amount"] = pd.to_numeric(
        df["Brutto"].str.replace(".", "").str.replace(",", ".")
    )
    df["amount_received"] = pd.to_numeric(
        df["Netto"].str.replace(".", "").str.replace(",", ".")
    )

    df = df.rename(
        columns={
            "Transaktionscode": "sale_id",
            "Zugehöriger Transaktionscode": "subscription_id",
            "Name": "name",
            "Ländervorwahl": "country",
            "Adresszeile 1": "address",
            "Adresszusatz": "address2",
            "Ort": "city",
            "PLZ": "postcode",
            "Hinweis": "note",
            "Absender E-Mail-Adresse": "paypal_email",
        }
    )
    make_empty = (
        "country",
        "address",
        "address2",
        "city",
        "note",
        "postcode",
        "subscription_id",
    )

    df = df.query('`Auswirkung auf Guthaben` == "Haben"')
    for c in make_empty:
        df[c] = df[c].fillna("")

    df["address"] = df.apply(
        lambda r: "{} {}".format(r["address"], r["address2"]).strip(), 1
    )
    count = 0
    new_count = 0
    for _, row in df.iterrows():
        is_new = import_paypal_row(row)
        count += 1
        if is_new:
            new_count += 1
    return count, new_count


def get_or_create_paypal_donor(row):
    donor = (
        Donor.objects.filter(
            Q(attributes__paypal_email=row["paypal_email"])
            | Q(email=row["paypal_email"], email_confirmed__isnull=False)
        )
        .order_by("id")
        .first()
    )
    if donor is not None:
        return donor

    name = row["name"]
    names = name.strip().rsplit(" ", 1)
    first_name = " ".join(names[:-1])
    last_name = " ".join(names[-1:])
    return Donor.objects.create(
        active=True,
        salutation="",
        first_name=first_name,
        last_name=last_name,
        company_name="",
        address=row["address"],
        postcode=str(row["postcode"]),
        city=row["city"],
        country=row["country"],
        email=row["paypal_email"],
        attributes={"paypal_email": row["paypal_email"]},
        contact_allowed=False,
        become_user=False,
        receipt=False,
    )


def import_paypal_row(row):
    """
    - Find payment
    - If found return False
    - If not:
    - Create donation / donor
    """

    payment = find_paypal_payment(row)
    if payment:
        if not payment.received_amount:
            payment.received_amount = Decimal(str(row["amount_received"]))
        if not payment.received_timestamp:
            payment.received_timestamp = row["date"]
        payment.save()
        # Make sure has donation
        create_donation_from_payment(payment)
        return False

    try:
        return Donation.objects.get(method="paypal", identifier=row["sale_id"])
    except Donation.DoesNotExist:
        pass

    donor = get_or_create_paypal_donor(row)

    donation = Donation.objects.create(
        donor=donor,
        identifier=row["sale_id"],
        completed=True,
        received_timestamp=row["date"],
        timestamp=row["date"],
        method="paypal",
        amount=Decimal(str(row["amount"])),
        amount_received=Decimal(str(row["amount_received"])),
        note=row["note"],
        recurring=bool(row["subscription_id"]),
    )
    detect_recurring_on_donor(donor)

    return donation


def find_paypal_payment(row):
    buffer = timedelta(minutes=5)

    cond = Q(extra_data__contains=row["sale_id"])
    if row["subscription_id"]:
        cond |= Q(extra_data__contains=row["subscription_id"])

    payments = (
        Payment.objects.filter(
            variant="paypal",
            status=PaymentStatus.CONFIRMED,
        )
        .filter(
            received_timestamp__gte=row["date"] - buffer,
            received_timestamp__lte=row["date"] + buffer,
        )
        .filter(cond)
    )

    if len(payments) == 0:
        return None
    elif len(payments) == 1:
        return payments[0]
    raise ValueError("Multiple matching payments found")
