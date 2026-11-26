# Runbook: P7 deployment test (DE@b70ab730 + okfde/froide@65bdbb35)

Run by a human, on a **staging copy** of production, after the P7 merge. No
live donation data goes through AI tooling (decision 2026-11-26, MERGE_PLAN P7.3).
Every check below reports **counts, types or headers only — never values**, so
the output can be shared for review without exposing donor data.

Budget: about an hour. Stop and report if any step says **STOP**.

---

## 0. Before migrating

```bash
# Rollback point. fds_donation 0052 drops the hstore column: there is no undo
# other than restoring this dump.
pg_dump -h <staging-host> -U <user> <db> > staging-pre-p7-$(date +%F).sql
```

Record these numbers. Section 2 compares against them:

```sql
SELECT
  (SELECT count(*) FROM fds_donation_donor)                       AS donors,
  (SELECT count(*) FROM fds_donation_donor
     WHERE attributes IS NOT NULL AND attributes <> ''::hstore)   AS donors_with_attributes,
  (SELECT count(*) FROM fds_donation_donor
     WHERE attributes ? 'ibans')                                  AS donors_with_ibans,
  (SELECT count(*) FROM fds_donation_donor
     WHERE attributes ? 'old_data')                               AS donors_with_old_data,
  (SELECT count(*) FROM fds_donation_donation)                    AS donations,
  (SELECT count(*) FROM froide_payment_payment)                   AS payments,
  (SELECT count(*) FROM froide_payment_subscription)              AS subscriptions,
  (SELECT count(*) FROM fds_mailing_conditioncmsplugin)           AS condition_plugins,
  (SELECT count(*) FROM django_site)                              AS sites;
```

**Celery task rename.** This deploy renames the `fds_donation` tasks from
`fragdenstaat_de.*` to `fragdenstaat_at.*` (see MERGE_PLAN "Celery"). On
production, follow `docs/runbooks/celery-task-rename.md`. On staging, check now
that the queue has nothing under the old names, so section 4 is meaningful.

## 1. Migrate

```bash
python manage.py migrate
python manage.py showmigrations | grep '\[ \]'        # expect: nothing
python manage.py makemigrations --check --dry-run      # see note
```

New migrations, in order: `bounce 0003`, `froide_payment 0021`,
`fds_cms 0010–0011`, `fds_donation 0049–0052`, `fds_mailing 0003–0005`.

`makemigrations --check` also reports `djangocms_alias`, `contractor` and
`sortabletable`. That is pre-existing and comes from those third-party
packages, so it is not a STOP. Anything else listed is.

## 2. Donor attributes (hstore → JSON)

```sql
SELECT
  (SELECT count(*) FROM fds_donation_donor)                               AS donors,
  (SELECT count(*) FROM fds_donation_donor WHERE attributes <> '{}'::jsonb) AS donors_with_attributes,
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'ibans')    AS donors_with_ibans,
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'old_data') AS donors_with_old_data;
```

**STOP** if any of the four differs from section 0.

```sql
-- Shapes, by key. Expected:
--   ibans                   -> array only
--   iban, banktransfer_ref. -> string only
--   old_data                -> array (a few 'string' rows are acceptable: an
--                              old_data repr that is not a plain literal, e.g.
--                              containing datetime(...), is kept verbatim)
SELECT key, jsonb_typeof(value) AS type, count(*)
FROM fds_donation_donor, jsonb_each(attributes)
GROUP BY 1, 2 ORDER BY 1, 2;

-- Every IBAN list entry is a string, none empty, none still ';'-joined or repr-ed
SELECT count(*) AS bad_iban_entries
FROM fds_donation_donor, jsonb_array_elements(attributes->'ibans') AS e
WHERE jsonb_typeof(e) <> 'string'
   OR e #>> '{}' = '' OR e #>> '{}' LIKE '%;%' OR e #>> '{}' LIKE '[%';
```

**STOP** if `ibans` has any type other than `array`, if `iban` or
`banktransfer_reference` is anything other than `string`, or if
`bad_iban_entries` is not 0. Report the shape table either way.

## 3. CMS and mailing data

```sql
SELECT (SELECT count(*) FROM django_site) AS sites,
       (SELECT count(*) FROM fds_cms_sitesettings) AS site_settings;   -- equal

SELECT count(*) AS condition_plugins,
       count(*) FILTER (WHERE condition IN ('', 'False')) AS empty_conditions
FROM fds_mailing_conditioncmsplugin;
```

`condition_plugins` should equal section 0. `empty_conditions` should be 0
unless a plugin had no key before. Open one mailing that uses a condition
block in the admin preview, and check it renders as before for a donor and a
non-donor.

```bash
python scripts/verify_render.py   # needs a built frontend; every CMS page 200, no logged errors
```

## 4. Functional checks

- **Bank-transfer import.** Import a small synthetic CSV (two rows: one
  matching a test donation, one unknown). Expect matched 1, unmatched 1. The
  matched donor's `attributes->'ibans'` must be an array (re-run the shape
  query).
- **Donation form.** Make one test donation per enabled method. Recurring
  PayPal must not 400 (the `de-at` locale fix now comes from upstream
  froide-payment).
- **Donation embed.** `python manage.py shell -c "from django.urls import reverse; print(reverse('fds_donation:donate-embed'))"`,
  then:
  - `curl -sI <url>` must show `Content-Security-Policy: frame-ancestors 'self'`
    and no `X-Frame-Options`.
  - Set a test partner origin in *Frame ancestors* on the donation page's page
    settings. The header must then list it.
  - From a page on that origin, frame the form and **submit a donation from
    inside the iframe**. Unverified so far: the CSRF and session cookies are
    `SameSite=Lax`, so a cross-site POST may be rejected (DE has the same
    settings). Report what happens either way.
- **Feedback-ID.** Send a test mailing and one transactional mail (any
  froide notification) to a Gmail address. The raw message must carry `Feedback-ID:`
  (`mailing-<id>::<newsletter slug or "mailing">:fragdenstaat.at`, and
  `::<mail intent, "/" replaced by ".">:fragdenstaat.at` for transactional
  mail), and the `h=` list of the
  `DKIM-Signature` must include `feedback-id`. If it does not, Gmail ignores the
  header: fix the MTA's DKIM header list (ops, not code).
- **Classification reminders.** In a shell, check the Saturday task would only
  mail recent requests:
  `FoiRequest.objects.get_unclassified().filter(last_message__lt=now()-timedelta(days=67)).count()`
  is how many stale requests now get **no** mail.
- **Fax.** With `FAX_BACKEND` pointing at the dummy backend, send a fax-routed
  reply and check a `DeliveryStatus` is created and `email_message_id` is set.
  This exercises the froide-fax send path that the okfde merge broke and
  P7.1 fixed.

## 5. Report

The two count tables (sections 0 and 2), the shape table, the
`empty_conditions` count, and pass/fail for each section-4 item, including what
the iframe submit did.
