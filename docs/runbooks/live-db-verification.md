# Verifying the sync against a live database import

What to run after loading a **real production dump** into the dev environment, and
what each step is actually checking. Everything below has been run against the
scrubbed extract; the point of doing it again on live data is the things the
extract **cannot** show — real donation rows, and real draft/public divergence in
CMS content.

Budget: ~30 minutes, most of it waiting on migrations.

> **Stop-and-report criteria.** Do not deploy if step 3 needs anything not listed
> here, if step 5 reports drift, if step 6 shows a page failing or an error in the
> log, or if step 8 shows fewer donors/donations after migrating than before.

---

## 0. Before you import

```bash
# Keep the pre-migration state: everything below is comparative.
pg_dump -h <prod-host> -U <user> <db> > prod-$(date +%F).sql
```

Record these numbers — several later steps compare against them:

```sql
SELECT
  (SELECT count(*) FROM fds_donation_donor)            AS donors,
  (SELECT count(*) FROM fds_donation_donation)         AS donations,
  (SELECT count(*) FROM froide_payment_payment)        AS payments,
  (SELECT count(*) FROM froide_payment_subscription)   AS subscriptions,
  (SELECT count(*) FROM foirequest_foirequest)         AS foirequests,
  (SELECT count(*) FROM account_user)                  AS users,
  (SELECT count(*) FROM cms_cmsplugin)                 AS plugins;
```

```
 donors | donations | payments | subscriptions | foirequests | users | plugins 
--------+-----------+----------+---------------+-------------+-------+---------
    381 |       730 |      663 |           138 |        4857 |  2745 |     757
```

`foirequests` and `users` also tell you the **migration window** — the CMS content
is trivial by comparison, so those are what determine downtime.

---

## 1. Load it

```bash
createdb -h db -U fragdenstaat_at fds_live
psql -h db -U fragdenstaat_at -d fds_live -c "CREATE EXTENSION postgis; CREATE EXTENSION hstore;"
psql -h db -U fragdenstaat_at -d fds_live -f prod-YYYY-MM-DD.sql
```

Use this for every command below:

```bash
export PGPASSWORD=fragdenstaat_at
export DATABASE_HOST=db DATABASE_NAME=fds_live \
       DATABASE_USER=fragdenstaat_at DATABASE_PASSWORD=fragdenstaat_at \
       DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.development \
       DJANGO_CONFIGURATION=Dev \
       DJANGO_ELASTICSEARCH_HOSTS=http://elasticsearch:9200
```

---

## 2. Check the `fds_cms/0005` precondition — **before** faking anything

`0005` adds columns that production already has, so it must be faked. But faking
it on a database that *lacks* them silently leaves a broken schema, so check
first:

```sql
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema='public' AND (
  (table_name='fds_cms_borderedsectioncmsplugin' AND column_name='attributes') OR
  (table_name='fds_cms_cardcmsplugin'            AND column_name='attributes') OR
  (table_name='fds_cms_modalcmsplugin'  AND column_name IN ('attributes','dialog_attributes','tag_type')) OR
  (table_name='fds_cms_revealmorecmsplugin'      AND column_name='attributes'))
ORDER BY 1,2;
```

- **6 rows** → expected. Fake it (step 3).
- **0 rows** → do **not** fake; run `migrate fds_cms` normally and re-check.
- **Anything between** → stop and report. The schema is in a state nobody has seen.

Also confirm where the app actually is:

```sql
SELECT app, max(name) FROM django_migrations
WHERE app IN ('fds_cms','fds_donation','cms','djangocms_alias','djangocms_versioning')
GROUP BY app ORDER BY app;
```

---

## 3. Migrate

```bash
python manage.py migrate --fake fds_cms 0005      # only if step 2 showed 6 rows
python manage.py migrate 2>&1 | tee migrate.log
```

Expect **54 migrations**, in this order. Captured from an actual run against the
extract, not from memory — `fds_cms.0006` is at position 12 and `cms.0042` at 13,
and **that ordering is load-bearing**: `0006` reads `StaticPlaceholder`, which
`cms.0042` deletes.

```
account.0039_lowercase_username
account.0040_alter_user_username
account.0041_alter_application_authorization_grant_type
account.0042_alter_user_language
account.0043_alter_application_client_secret
campaign.0008_campaign_logo_campaign_short_description
campaign.0009_alter_campaign_logo
djangocms_versioning.0018_fix_typo
djangocms_alias.0005_dynamic_slot_names
djangocms_alias.0006_alter_alias_id_alter_aliascontent_id_and_more
djangocms_alias.0007_alter_category_options_alter_aliasplugin_alias
fds_cms.0006_static_placeholders_to_aliases
cms.0042_remove_placeholderreference_placeholder_ref_and_more
cms.0043_alter_globalpagepermission_can_view_and_more
cms.0044_pagecontent_slug_overwrite_url
cms.0045_pageurl_site_unique_path
cookie_consent.0001_initial
cookie_consent.0002_auto__add_logitem
cookie_consent.0003_alter_cookiegroup_varname
cookie_consent.0004_cookie_natural_key
datashow.0001_initial
datashow.0002_column_facet_count
datashow.0003_table_row_description_template_and_more
djangocms_frontend.0003_slotmodel
document.0031_alter_document_updated_at_alter_document_user_and_more
document.0032_alter_document_language
fds_cms.0007_remove_fdspageextension_public_extension
fds_cms.0008_datawrappercmsplugin_opensearchcmsplugin_and_more
fds_cms.0009_unhash_static_urls_in_text
flowcontrol.0001_initial
flowcontrol.0002_trigger_condition_alter_flowrun_outcome
flowcontrol.0003_flow_condition_flow_content_type
flowcontrol.0004_waitfortrigger_remove_trigger_unique_flow_trigger_and_more
flowcontrol.0005_emailalert
flowcontrol.0006_trigger_reset_to_action
flowcontrol.0007_alter_flowrun_status
fds_mailing.0001_initial
fds_newsletter.0001_initial
fds_donation.0045_donor_subscriber
fds_donation.0046_emaildonationbuttoncmsplugin_and_more
fds_mailing.0002_initial
filingcabinet.0032_alter_document_language
foirequest.0073_lowercase_foirequest_secret_address
foirequest.0074_requestdraft_proof
foirequest.0075_alter_foiproject_language_alter_foirequest_language
georegion.0014_georegion_related
guide.0008_action_params_alter_guidance_matches
proof.0002_alter_proof_options
publicbody.0051_remove_taggedpublicbody_content_object_and_more
publicbody.0052_publicbodycontact
publicbody.0053_auto_20260402_1210
publicbody.0054_proposedpublicbodycontact_and_more
publicbody.0055_alter_foilawtranslation_unique_together_and_more
searchalert.0001_initial
```

Grouped, that is:

| Group | What it does |
|---|---|
| `fds_cms.0005` | **FAKED** — columns already present (step 2) |
| `fds_cms.0006` | static placeholders → djangocms-alias |
| `cms.0042` | deletes `StaticPlaceholder` — must come *after* `0006` |
| `cms.0043–0045`, `djangocms_alias.0005–0007`, `djangocms_versioning.0018`, `djangocms_frontend.0003` | upstream CMS catch-up |
| `fds_cms.0007–0009` | `public_extension` removal, new plugins, unhashing static URLs |
| `fds_donation.0045–0046` | `Donor.subscriber`, then DE's schema incl. `Recurrence` |
| `cookie_consent.*`, `datashow.*` | newly registered apps |
| froide apps | `account`, `publicbody`, `foirequest`, `document`, `filingcabinet`, `georegion`, `guide`, `proof`, `searchalert` |

### If something wants faking that is not listed

Only `fds_cms.0005` should ever need `--fake`, and only when step 2 found its six
columns. If `migrate` fails with *"column … already exists"* or *"relation …
already exists"* for anything else, **stop and report** — it means production has
schema this branch does not know about, and faking past it hides the difference
rather than resolving it. Capture the failing migration and the relevant
`information_schema` rows before doing anything else.

To inspect without applying:

```bash
python manage.py migrate --plan            # what would run, in order
python manage.py showmigrations fds_cms fds_donation cms
python manage.py sqlmigrate fds_cms 0006   # the SQL for one migration
```

If `fds_cms.0006` runs **after** `cms.0042`, stop — the alias conversion will have
found no data, and the static placeholders are gone.

---

## 4. Verify the two data migrations did their work

Exit code 0 is not evidence. Check the rows.

```sql
-- 0006: one Alias + one published Version per static placeholder, plugins moved
SELECT a.static_code,
       count(DISTINCT ac.id)                                  AS contents,
       count(DISTINCT v.id) FILTER (WHERE v.state='published') AS published,
       (SELECT count(*) FROM cms_cmsplugin p
          JOIN cms_placeholder ph ON p.placeholder_id = ph.id
         WHERE ph.object_id IN (SELECT id FROM djangocms_alias_aliascontent
                                 WHERE alias_id = a.id)) AS plugins
FROM djangocms_alias_alias a
JOIN djangocms_alias_aliascontent ac ON ac.alias_id = a.id
LEFT JOIN djangocms_versioning_version v
       ON v.object_id = ac.id
      AND v.content_type_id = (SELECT id FROM django_content_type
                                WHERE app_label='djangocms_alias' AND model='aliascontent')
GROUP BY a.id, a.static_code ORDER BY 1;
```

⚠️ **This is the step the extract could not exercise.** `export_dev_db.py` writes
`public_id` into both the draft and public FKs, so draft/public divergence is
structurally absent from it. On live data the migration takes the **published**
placeholder and discards draft-only edits. Confirm each `static_code` you expect
(`footer`, `top_banner`, `dropdown_banner`, `help_footer`, …) has `contents = 1`,
`published = 1`, and a plausible plugin count.

More than one `contents` row per code means the language grouping went wrong — the
symptom of a `values_list(...).distinct()` that did not deduplicate. Stop.

```sql
-- no placeholders left pointing at the deleted model
SELECT count(*) FROM cms_placeholder ph
  LEFT JOIN django_content_type ct ON ph.content_type_id = ct.id
 WHERE ct.model = 'staticplaceholder';        -- expect 0

-- 0009: no hash-stamped static URLs left in CMS text
SELECT count(*) FROM djangocms_text_text
 WHERE body ~ '/static/[^"'']*\.[0-9a-f]{12}\.';   -- expect 0
```

---

## 5. No model drift

Check AT's own apps. **This must exit 0:**

```bash
python manage.py makemigrations --check --dry-run \
  fds_cms fds_donation fds_mailing fds_newsletter theme
# -> No changes detected in apps 'fds_mailing', 'fds_donation', 'theme', 'fds_cms', 'fds_newsletter'
```

Run it **unscoped** and it will always fail, on any database — five upstream apps
report drift:

| app | cause |
|---|---|
| `account` | django-oauth-toolkit 3.1.0; froide's migrations were generated against a newer one |
| `publicbody` | django-parler 2.3 changed translation constraints |
| `contractor`, `sortabletable` | built against django-cms 5.0; AT runs 5.1.1 (`cmsplugin_ptr` changed) |
| `djangocms_frontend` | 2.5.1 ships a proxy `Image` model with no migration |

Note `makemigrations --check` compares **models in code against migration files on
disk** — it never touches the database, so this result is identical whichever dump
is loaded. It is not a symptom of a bad import.

Do not "fix" it by running `makemigrations`: every file it wants to write lands in
`site-packages/` or the froide checkout, not in this repo, so it would be lost on
the next install.

Chasing the versions does not help either — measured, not assumed. Upgrading
django-parler 2.3 → 2.4 clears `publicbody` and immediately introduces the same
drift in `djangocms_alias`; upgrading django-oauth-toolkit past DE's 3.3.0 makes
`account` worse, adding two new fields froide has no migration for. The drift
moves, it does not go away. Leave it and scope the check.

---

## 6. Render every CMS page

**The highest-value check on this list.** The CMS swallows plugin render errors, so
a broken plugin returns HTTP 200 with the content silently missing. This found four
such bugs during the sync that the test suite did not.

```bash
python scripts/verify_render.py
```

Every page must be `200` (or a deliberate `302`), with no logged errors and no
suspiciously short body. Investigate anything under ~2 kB.

---

## 7. Search

```bash
python manage.py search_index --rebuild -f
```

Then sanity-check relevance — a term from a page title should rank that page first:

```bash
curl -s -H 'Content-Type: application/json' \
  "http://elasticsearch:9200/fragdenstaat_at_cmspage/_search" \
  -d '{"query":{"match":{"content":"Datenschutz"}},"_source":["title"],"size":3}'
```

---

## 8. Donations — the part the extract could not test

```sql
SELECT
  (SELECT count(*) FROM fds_donation_donor)          AS donors,
  (SELECT count(*) FROM fds_donation_donation)       AS donations,
  (SELECT count(*) FROM froide_payment_subscription) AS subscriptions,
  (SELECT count(*) FROM fds_donation_recurrence)     AS recurrences,
  (SELECT count(*) FROM fds_donation_donor WHERE subscriber_id IS NOT NULL) AS with_subscriber;
```

- `donors`/`donations` must match the step 0 numbers exactly. Any loss is a
  stop-and-restore.
- `recurrences` is new in `0046`. DE's model moves recurring donations off
  froide-payment `Subscription`s, so compare it against `subscriptions` and check
  a few by hand in the admin.
- `with_subscriber` will be **0** — `Donor.subscriber` is a fresh nullable column
  with no backfill, which is expected.

Then exercise the admin and the form, since both were rewritten wholesale:

```bash
python manage.py shell -c "
from django.contrib import admin
from fragdenstaat_at.fds_donation.models import Donor, Donation, Recurrence
for m in (Donor, Donation, Recurrence):
    a = admin.site._registry[m]
    print(m.__name__, a.get_queryset(None).count() if False else 'registered')
"
```

Load `/admin/fds_donation/donor/` and a donor detail page in a browser, and load a
donation form page. The browser test covers the happy path; the admin is where the
`Recurrence` join surfaces.

---

## 9. Test suite

```bash
env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION \
  DATABASE_URL="postgis://fragdenstaat_at:fragdenstaat_at@db:5432/fragdenstaat_at" \
  python -m pytest -q --create-db
```

Expect **256 passed, 1 skipped, 11 deselected**.

Two traps:

- **Unset `DJANGO_SETTINGS_MODULE` and `DJANGO_CONFIGURATION`.** Environment
  variables override `pytest.ini`, so a shell left over from the steps above runs
  the suite under `Dev` instead of `Test`. `tests/conftest.py` now refuses rather
  than doing this silently.
- **Use `--create-db` after any schema change.** `--reuse-db` is the default and
  will otherwise reuse a stale test database — this produced ~77 spurious errors
  once during the sync.

---

## 10. Timing

Note how long step 3 takes on live data. It sets the production maintenance
window, and `foirequest`/`account` are the tables that dominate it — not the CMS.

---

## 11. Donation system — Stripe and PayPal

Section 8 checks the donation *data* that survived the import. It cannot check
that money actually moves: the extract carries **zero donations**, and the
banktransfer tests in the default suite never touch a payment provider. These
are the only tests that exercise a real provider end to end, and they are
deselected by default (`-m "not stripe and not paypal"` in `pytest.ini`) because
they need credentials.

Like section 9, these run against `test_fragdenstaat_at`, not the imported
extract — but run them *after* an import, because a provider misconfiguration
and a bad import look identical from the donation admin.

### Stripe (8 tests)

```bash
export STRIPE_TEST_PUBLIC_KEY=pk_test_...
export STRIPE_TEST_SECRET_KEY=sk_test_...

env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION \
  DATABASE_URL="postgis://fragdenstaat_at:fragdenstaat_at@db:5432/fragdenstaat_at" \
  python -m pytest -m stripe -q
```

`settings/test.py` already wires both keys into the `creditcard` and `sepa`
variants — nothing to configure by hand. The secret key **must** start with
`sk_test_`; the fixture asserts it, so a live key fails loudly rather than
charging anyone.

**You do not need to run `stripe listen` yourself.** `stripe_sepa_setup` starts
the CLI forwarder itself, pointed at the `live_server` URL (a random port), and
reads the signing secret back out of it. The Stripe CLI must be on `PATH` — it
is baked into `.devcontainer/Dockerfile`, so this only bites outside the
devcontainer.

Covers: card once/recurring, quick donation, SEPA once, SEPA recurring, and the
failure paths (declined, disputed, additional fields, shortened interval). The
recurring ones are the reason §9.8 matters — they build a `Plan`, which is where
the `slug` overflow used to 500.

### PayPal (3 tests)

```bash
export PAYPAL_TEST_CLIENT_ID=...      # sandbox REST app
export PAYPAL_TEST_SECRET=...
export PAYPAL_TEST_ACCOUNT=...        # sandbox *buyer* login, not the app
export PAYPAL_TEST_PASSWORD=...

env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION \
  DATABASE_URL="postgis://fragdenstaat_at:fragdenstaat_at@db:5432/fragdenstaat_at" \
  python -m pytest -m paypal -q
```

**Also needs `lt` (localtunnel) on `PATH`**, which is not installed by the
devcontainer:

```bash
npm install -g localtunnel
```

PayPal has to reach `live_server` to deliver `CHECKOUT.ORDER.APPROVED` and
`PAYMENT.CAPTURE.COMPLETED`, and it cannot route to `localhost`. The test opens a
public `*.loca.lt` tunnel and registers that as the webhook URL. This is the
structural difference from Stripe, whose CLI polls outward and needs no inbound
path. Note it does expose the test server publicly for the duration, and
`loca.lt` is third-party infrastructure that rate-limits — a tunnel that comes up
but delivers no webhook is the next thing to suspect, ahead of the test code.

Four variables, not two: the first pair authenticates AT against PayPal, the
second is a sandbox buyer account the browser logs in *as*. `settings/test.py`
hardcodes `https://api.sandbox.paypal.com` and the tests assert `"sandbox"` is
in the endpoint, so these cannot hit production.

Covers `test_paypal_once`, `test_paypal_recurring`, `test_paypal_cancel`.

### Both at once

```bash
python -m pytest -m "stripe or paypal" -q     # 11 tests
```

### Gotchas

- **Missing credentials raise, they do not skip.** The autouse fixtures are named
  `skip_stripe_if_no_key` / `skip_stripe_if_no_cli` but call `raise
  RuntimeError`. An unset key is a loud failure, not a quiet pass — read the
  message before assuming the payment code is broken.
- **These are real browser tests** (`async` + Playwright chromium), pinned to one
  xdist worker via `@pytest.mark.xdist_group("sequential")`. They are slow and
  they talk to third-party sandboxes, so treat a single flake as a flake and a
  reproducible failure as real.
- **PayPal's sandbox is the flakier of the two.** It drives a real login form on
  PayPal's side, which changes without notice.
