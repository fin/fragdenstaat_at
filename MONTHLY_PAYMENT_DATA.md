# Monthly payment data: import, reminders, follow-up

How the monthly bank statement and PayPal export get into the donation
database, and how donors who promised a bank transfer but never sent it get
reminded. Everything happens on the **Donations changelist** in the Django
admin (`/admin/fds_donation/donation/`); nothing here is scheduled — a person
does it, in this order, once the statement for the previous month is in hand.

```
1. Import bank transfers (CSV)           → forms below the donation list
2. Import PayPal (CSV)                   → forms below the donation list
3. Check the import mail, fix unmatched  → admin actions
4. Preview who would be reminded         → sidebar filter "Banktransfer reminder due"
5. Send reminders                        → button "Erinnerungen senden"
```

Steps 1–3 must come before 4–5: a reminder goes to everyone whose promised
transfer is still unreceived *in the database*, so importing afterwards means
reminding people who already paid.

---

## 1. Bank transfers (foi-buchhaltung CSV)

**Where:** bottom of the donation list, "Überweisungen aus foi-buchhaltung".
Pick the project (currently only *Forum Informationsfreiheit*), choose the
file, "Überweisungen importieren".

The upload returns immediately ("Import will start in background"); the actual
work runs in a Celery task and **the result is mailed to you**, the uploader:

- `Bank transfers imported for FOI` — with `Matched / New / Unmatched` counts and,
  if any, the list of unmatched rows.
- `Bank transfer import for FOI failed` — either the file was rejected up front
  (nothing written) or a row failed mid-way (rows before it are committed;
  re-uploading is safe, see *Idempotency*).

If no mail arrives within a few minutes, the worker is not picking up tasks —
check Celery before re-uploading.

### File format

CSV, UTF-8 (a BOM is fine), `,` or `;` delimited — whichever the header line
uses more of. Column names are case-insensitive. Only incoming transfers belong
in the file; a row with a zero or negative amount rejects the whole file.

| column          | required | meaning                                                                                |
|-----------------|----------|----------------------------------------------------------------------------------------|
| `reference`     | yes      | Verwendungszweck as the bank shows it. Matching looks for the `FDS XXXXXXXX` code in it. |
| `amount`        | yes      | `10.50`, `10,50`, `1.234,50` and `1,234.50` all work.                                  |
| `date_received` | yes      | `YYYY-MM-DD` or `DD.MM.YYYY`. Becomes the donation's received date.                    |
| `identifier`    | no       | The bank's own transaction id. Strongly recommended — see *Idempotency*.               |
| `iban`          | no       | Sender IBAN. Used to recognise recurring donors whose reference lacks a code.          |
| `date`          | no       | Booking date, if different from `date_received`.                                       |
| `purpose`       | no       | Overrides the donation's purpose field.                                                |
| `name`          | no       | Sender name. Only echoed back in the unmatched list.                                   |

The whole file is validated before anything is written, so a bad amount or
date on line 40 rejects the file with `line 40: …` and nothing is imported.

### What happens to each row

1. **Matched** — a pending banktransfer donation exists whose payment carries
   the `FDS …` code found in `reference`. It gets `received_timestamp`,
   `amount_received`, and its payment is confirmed. This is the normal case for
   one-off donations made through the website.
2. **New** — no pending donation, but the donor is known: either an earlier
   donation used the same `FDS …` code, or the sender IBAN is on file. A new
   completed donation is created. This is the normal case for the follow-up
   transfers of a Dauerauftrag, whose reference keeps the original code.
3. **Unmatched** — neither. **Nothing is written** for that row; it is listed
   in the result mail as `date | amount | name | iban | reference`. The import
   never creates donors — an unknown sender has to be handled by hand (step 3).

Whenever a row is attributed to a donor, the sender IBAN is recorded on the
donor so future transfers from that account match even without a code.

### Idempotency

Each row gets a stable identifier — the `identifier` column if present,
otherwise `date_received-reference-amount-iban`. Re-importing the same file, or
a file that overlaps with a previous one, updates the same donations rather
than duplicating them. Without a bank transaction id, two genuinely separate
transfers on the same day with the same amount, reference and IBAN would
collapse into one, which is why `identifier` is worth having.

## 2. PayPal (CSV)

**Where:** the "Paypal (CSV)" form, directly under the bank transfer form.
Upload PayPal's German activity export as-is (columns `Datum`, `Uhrzeit`,
`Brutto`, `Netto`, `Transaktionscode`, `Auswirkung auf Guthaben`, …). Only
`Haben` rows are considered. Same background/mail pattern as above.

Rows whose transaction code matches a PayPal payment made through the site
just fill in the received amount/date. Anything else creates a donation —
and, unlike the bank import, a donor if the PayPal e-mail address is unknown
(marked `contact_allowed=False`, no receipt).

## 3. Fix what the import could not

Work through the *Unmatched* list from the result mail. Typical cases:

- **Transfer without a usable code, donor identifiable by name.** Find the
  pending donation in the admin (filter `Received: No`, `method: banktransfer`,
  search the donor name), open it, and enter `received_timestamp`,
  `amount_received` and the bank's transaction id as `identifier` by hand.
- **Donor already has both a pending and a manually created received donation.**
  Select exactly those two and run the action *Match planned to received
  banktransfer*: the pending one takes over amount, date and identifier, the
  duplicate is deleted. Both must be banktransfer, same donor, same project,
  and the received one must not have a payment, order or receipt attached.
- **Money was sent back.** Action *Mark banktransfer donation as refunded* on
  the single donation.
- **Unknown sender, no donation intended.** Nothing to do in the system.

## 4. Preview: who would be reminded

Sidebar filter **Banktransfer reminder due → yes** (URL parameter
`?reminder_due=1`). This shows *exactly* the set the button in step 5 will
mail — filter and task read the same queryset,
`fds_donation.services.get_unreceived_banktransfers_to_remind()`. Combine it
freely with other filters or the donor search to inspect individual cases.

A donation is listed when all of these hold:

- completed, method `banktransfer`, no `received_timestamp`
- promised **last month**, shifted back by a 4-day bank delay: created in the
  window `[1st of last month − 4 d, 1st of this month − 4 d)` — e.g. for a run
  in October, from 28 Aug up to and including 26 Sep
- at least 14 days old at the time of the check
- the donor has **no other received donation** since the window started
  (someone who promised 10 € and then sent 20 € under a different reference is
  not nagged)
- not reminded before — the note field does not contain `REMINDER:`

If a donor shows up here who you know has paid, the import missed their
transfer: fix that first (step 3), then re-check the filter.

## 5. Send the reminders

Bottom of the donation list, **"Erinnerungen für ausstehende Überweisungen" →
"Erinnerungen senden"**. Requires change permission on donations. This enqueues
the Celery task `remind_unreceived_banktransfers`; the admin only confirms
"will be sent in background" and does not report a count — use the filter in
step 4 beforehand for that.

Each donor gets the `fds_donation/email/donation_reminder` mail (subject *Ihre
Spende an das Forum Informationsfreiheit*) restating IBAN, amount and the
`FDS …` Verwendungszweck. The donation's note gets a `REMINDER: <timestamp>`
line appended, which is what keeps it out of the filter afterwards.

To remind a single donor outside this window — say a pending transfer from two
months ago that slipped through — select the donation(s) and use the list
action *Send donation reminder*. It applies the same once-only, ≥ 14 days,
banktransfer-only guards and reports how many mails actually went out.

**Pressing the button twice is harmless.** Every donation is reminded at most
once, so a second press only reaches donations that were held back the first
time — for instance the ones under 14 days old when you triggered early in the
month. Which is also why there is no cron for this: it should run right after
the statement is in, and only you know when that is. Make sure the
deployment's beat config does *not* schedule the task.

## 6. What to expect afterwards

- Donors who now pay will match on the next import via their `FDS …` code, as
  usual. Their donation loses `received_timestamp = NULL` and drops out of the
  filter on its own.
- Promised transfers that never arrive stay in the database as unreceived and
  are deleted by `remove_old_donations` after 12 months (incomplete checkouts
  after 3 months). That task is not scheduled in this repo either.

---

### Where things live

| what                                 | where                                                                              |
|--------------------------------------|------------------------------------------------------------------------------------|
| upload views, admin actions          | `fragdenstaat_at/fds_donation/admin.py` — `DonationAdmin`                          |
| the two upload forms and the button  | `fragdenstaat_at/fds_donation/templates/admin/fds_donation/donation/change_list.html` |
| CSV parsing and matching             | `fragdenstaat_at/fds_donation/external.py`                                         |
| result mails                         | `fragdenstaat_at/fds_donation/tasks.py` — `import_banktransfers_task`, `import_paypal_task` |
| reminder selection                   | `fragdenstaat_at/fds_donation/services.py` — `get_unreceived_banktransfers_to_remind` |
| reminder sending / note stamp        | `fragdenstaat_at/fds_donation/services.py` — `send_donation_reminder_email`        |
| preview filter                       | `fragdenstaat_at/fds_donation/admin_utils.py` — `BanktransferReminderDueListFilter` |
| reminder mail template               | `fragdenstaat_at/fds_donation/templates/fds_donation/email/donation_reminder.txt`  |
| tests                                | `fds_donation/tests/test_external.py`, `test_reminder.py`, `test_admin.py`         |
