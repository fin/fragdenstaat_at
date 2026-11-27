# Runbook: P7 deployment test (DE@b70ab730 + okfde/froide@65bdbb35)

Run by a human, on a **staging copy** of production, after the P7 merge. No
live donation data goes through AI tooling (decision 2026-11-26, MERGE_PLAN P7.3).
Every check below reports **counts, types or headers only — never values**, so
the output can be shared for review without exposing donor data.

Budget: about an hour. Stop and report if any step says **STOP**.

**Local option:** `.devcontainer/staging/` runs this against a dump on your own
machine, isolated from the dev container. `scripts/staging/p7-deploy-test.sh`
automates sections 0–3 and writes the counts-only report; section 4 stays
manual. Its README lists what is isolated and what isn't. In that setup the
rollback in section 0 is recreating the database (`docker compose -p
fds-at-staging down -v`), not a second dump.

**Baseline: production runs `dev` @ `55ac7c4` (2026-10-19).** Everything below
is relative to that, not to `main`. What this deploy changes:

- **Code:** the P7 merge (DE@`b70ab730`), the classification-reminder cutoff
  (`e40bcdb`, on `dev` but never deployed), and Feedback-ID.
- **Dependencies (`uv.lock`):** froide moves from fin's
  `2026-feat-messagekind-initial-message` branch to `okfde/froide@main`
  (`65bdbb35`); froide-payment from `fin/froide-payment@main` to `okfde@main`;
  froide-fax to `fin/froide-fax@main` (`7dfd964`, okfde's two commits merged); djangocms-text 0.9.1 →
  1.0.2 (held at DE's version, see MERGE_PLAN P7.2 group 1), django-flowcontrol 0.0.19 → 0.0.21.
- **Lock refresh (`6da1a0a`):** on top of that, the registry packages were
  moved to DE@`b70ab730`'s locked versions. Against production that is **109
  changed packages**, 7 added, 10 removed (xlrd among them). `django` 5.2.17,
  `urllib3` 2.7.0 and `pandas` 3.0.3 are **unchanged**: production already has
  them. Every version below is what DE runs in production. The ones on a live
  AT path, each with a check in section 4:

  | package | production → this deploy | where it runs in AT | check |
  |---|---|---|---|
  | `weasyprint` | 66 → 69 | every letter/fax PDF (`froide.foirequest.pdf_generator`, froide-fax) | 4. PDFs, Fax |
  | `pikepdf`, `reportlab`, `svglib` | 9 → 10, 4.4 → 4.5, 1.5 → 2.3 | redaction, filingcabinet PDF handling | 4. PDFs |
  | `django-localflavor`, `python-stdnum` | 3.1 → 5.0, 1.18 → 2.2 | `IBANFormField` in froide-payment's SEPA form | 4. Donation form |
  | `django-cms`, `djangocms-link`, `django-filer`, `djangocms-alias`, `djangocms-versioning` | 5.1.1 → 5.1.3, 5.0 → 5.2, 3.3 → 3.6, 3.1 → 3.2, 2.7 → 2.8 | every CMS page; three new migrations (section 1) | 3. `verify_render`, 4. CMS editing |
  | `djangocms-simple-admin-style`, `django-tinymce` | 2.1 → 5.2, 3.5 → 5.0 | admin only | 4. CMS editing |
  | `celery`, `kombu`, `billiard`, `django-celery-beat`, `cron-descriptor` | 5.5 → 5.6, 5.5 → 5.6, 4.2.1 → 4.2.4, 2.8 → 2.9, 2.1 → 1.4.5 | workers, beat, the periodic-task admin | 4. Celery |
  | `channels`, `daphne`, `twisted`, `autobahn` | 4.2 → 4.3, 4.2.2 → 4.2.3, 26.4 → 26.10, 25 → 26 | the ASGI server | 4. Celery (service start) |
  | `sentry-sdk`; npm `@sentry/browser` | 2.29 → 2.62; 9 → 10 | error reporting, backend and browser | 4. Sentry |
  | `phonenumberslite`, `django-phonenumber-field` | 8 → 9, 7 → 8 | froide's phone fields (fax numbers) | 4. Fax |

  The rest are dev/test tools (ipython, faker, debug-toolbar, honcho,
  pytest-*) or transitive with no direct AT use. The suite passes on the new
  lock (433 passed). Install with `uv sync --locked`: a plain `uv sync` may
  re-resolve to something other than what was tested.
- **Frontend:** Vite 7, `@vitejs/plugin-vue` 6, Sentry 10/4, vega minors; the
  npm `django-cookie-consent` and `@types/dompurify` are gone (`pnpm-lock.yaml`).
  Rebuild with `pnpm install --frozen-lockfile && pnpm run build`.
- **Celery:** no renames (production already has `e07f8e5`); two new tasks
  queued from signal handlers, none scheduled. Restart the workers together
  with the web processes.
- **Unchanged:** the production settings resolve the same redirect hosts
  (`fragdenstaat.at` comes from `ALLOWED_HOSTS`); no new environment variables.

---

## 0. Before migrating

```bash
# Rollback point. fds_donation 0052 drops the hstore column: there is no undo
# other than restoring this dump.
pg_dump -h <staging-host> -U <user> <db> > staging-pre-p7-$(date +%F).sql
```

Record these numbers. Section 2 compares against them. Production's import code
(`55ac7c4`) writes `ibans` as one `;`-joined string, `iban` and
`banktransfer_reference` as strings; older rows may hold list reprs or
`old_data`. Migration 0051 converts all of these.

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

**Celery tasks.** This deploy renames no tasks: production (`dev` @ `55ac7c4`)
already runs the `fragdenstaat_at.*` names. It adds two,
`fragdenstaat_at.fds_donation.process_new_donation_task` and the dormant
`gift_order_inventory_warning_notification`, so restart the workers with the
web processes. Neither is in the beat schedule.

## 1. Migrate

```bash
python manage.py migrate
python manage.py showmigrations | grep '\[ \]'        # expect: nothing
python manage.py makemigrations --check --dry-run      # see note
```

New migrations: `bounce 0003`, `froide_payment 0021`, `fds_cms 0010–0011`,
`fds_donation 0049–0052`, `fds_mailing 0003–0005`, plus three from the lock
refresh:

- `filer 0018_alter_file_options`: model options only, no SQL.
- `djangocms_alias 0008`: a unique constraint on category translations
  (`language_code`, `master`). **STOP** if it fails with a duplicate-key error;
  report the number of duplicate pairs, not their names.
- `djangocms_link 0020`: renames the `Link` plugin column `target` →
  `link_target`. AT overrides no djangocms_link templates, so nothing reads
  the old name; still check a link plugin set to open in a new tab
  (section 4, CMS editing).

That list is complete against production's lock (old and new wheels compared
for every changed package that ships migrations). The four edited froide
`document` migrations only make their `foirequest` dependency conditional
(already applied, no effect).

`makemigrations --check` also reports `contractor` and `sortabletable`. That
is pre-existing and comes from those third-party packages, so it is not a STOP
(djangocms-alias 3.2 fixed the third one it used to list). Anything else
listed is.

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

`condition_plugins` should equal section 0. fds_mailing is installed but unused
in production, so expect 0 for both; if `condition_plugins` is not 0, check that
`empty_conditions` is 0 and that one email template using a condition block
previews as before for a donor and a non-donor.

```bash
python scripts/verify_render.py   # needs a built frontend; every CMS page 200, no logged errors
```

## 4. Functional checks

- **Bank-transfer import.** Import a small synthetic CSV (two rows: one
  matching a test donation, one unknown). Expect matched 1, unmatched 1. The
  matched donor's `attributes->'ibans'` must be an array (re-run the shape
  query).
- **Donation form.** Make one test donation per enabled method. Recurring
  PayPal must not 400: production has the `de-at` locale fix from fin's
  froide-payment fork, and this deploy swaps it for upstream's copy. For the
  SEPA/bank-transfer form (localflavor 5, stdnum 2): an AT test IBAN
  (`AT61 1904 3002 3457 3201`) and a DE one must be accepted, with and without
  spaces; `AT61 1904 3002 3457 3202` (bad check digit) must be rejected.
- **PDFs** (WeasyPrint 69, pikepdf 10). Download the PDF of one request and
  of one letter-style message. Expect: it opens, the page count is plausible,
  umlauts and the logo render, and the layout matches the same download on
  production (compare side by side; report pass/fail only). Redact one test
  attachment and check the redacted PDF opens.
- **CMS editing** (django-cms 5.1.3, djangocms-link 5.2, filer 3.6, admin
  style 5). Log in, open a page in edit mode, edit and publish a text plugin,
  edit a link plugin (its "new tab" target must survive the `link_target`
  rename), and upload an image through filer. Open one admin form with a
  TinyMCE field.
- **Celery** (celery 5.6, beat 2.9). After the restart, the worker logs
  `ready`, beat logs its schedule, and
  `celery -A froide.celery inspect registered` (use the app your service
  units pass to `-A`) lists
  `fragdenstaat_at.fds_donation.process_new_donation_task`. The periodic-task
  admin list must load: cron-descriptor goes *down* to 1.4.5, and it renders
  the human-readable schedules there. The ASGI server (daphne/channels) must
  start without errors.
- **Sentry** (SDK 2.62, browser SDK 10). Trigger one backend test event
  (`python manage.py shell -c "import sentry_sdk; sentry_sdk.capture_message('p7 staging')"`)
  and check that the browser SDK still reports: a frontend error from staging
  must show up in Sentry. If the build uploads source maps (`sentryVitePlugin`
  in production mode, needs `SENTRY_AUTH_TOKEN`), its frames must be readable.
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
- **Feedback-ID.** Send one transactional mail (any froide notification) to a
  Gmail address. Mailings are not in use, so skip the mailing variant. The raw
  message must carry
  `Feedback-ID: ::<mail intent, "/" replaced by ".">:fragdenstaat.at`, and the
  `h=` list of the
  `DKIM-Signature` must include `feedback-id`. If it does not, Gmail ignores the
  header: fix the MTA's DKIM header list (ops, not code).
- **Classification reminders.** New behaviour against production, which still
  mails every unclassified request weekly. In a shell, check the Saturday task
  would only mail recent requests:
  `FoiRequest.objects.get_unclassified().filter(last_message__lt=now()-timedelta(days=67)).count()`
  is how many stale requests now get **no** mail.
- **Fax.** With `FAX_BACKEND` pointing at the dummy backend, send a fax-routed
  reply and check a `DeliveryStatus` is created and `email_message_id` is set.
  Production's froide-fax (`7b74f80`) works; this checks the okfde merge on the
  sync branch, whose auto-merge broke the send path before P7.1 fixed it. Open
  the generated fax PDF (WeasyPrint 69): cover letter, QR code and body must
  render. Also edit and save a public body's fax number in the admin
  (phonenumbers 9).

## 5. Report

The two count tables (sections 0 and 2), the shape table, the
`empty_conditions` count, whether the three lock-refresh migrations applied,
and pass/fail for each section-4 item, including what
the iframe submit did.
