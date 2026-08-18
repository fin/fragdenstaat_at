# fragdenstaat_at ↔ fragdenstaat_de — sync plan

| | ref | date |
|---|---|---|
| **AT** | `fragdenstaat_at` @ `sync/de-head-2026-08` | working branch |
| **DE@hash** | `fragdenstaat_de` @ `abe0781d` — the fork baseline | 2023-01-19 |
| **DE@HEAD** | `fragdenstaat_de` @ `938901ef` | 2026-08-17 |

`abe0781d..HEAD` is 2194 commits over 3 years 7 months.

**Measure divergence with `scripts/de_drift.py`** rather than trusting numbers in prose:

| vs | identical | **modified** | at-only | de-only |
|---|---|---|---|---|
| DE @ `abe0781d` | 243 | **57** | 51 | 255 |
| DE @ HEAD | 42 | **240** | 69 | 635 |

240 is the real workload. 57 is only how far AT drifted from its fork point.

---

## 1. Decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Merge direction | Rebase AT onto DE@HEAD; re-apply AT's delta as a branding/config layer |
| D2 | Delta style | Configure-out locally (settings/templates), no upstreaming to DE |
| D3 | Dropped apps | `fds_newsletter` + `fds_mailing` return with **no signup surface**; `fds_blog`, `fds_fximport` stay out ✅ |
| D4 | Language | Keep `de-at`; overrides move into `fragdenstaat_at/locale/de_AT/` |
| D5 | froide | No permanent fork; `fin/froide` is a time-boxed test bed, exit = `de_AT` relocation proven |
| D6 | Dependencies | DE's curated `pyproject.toml` minus apps AT does not enable ✅ |
| D7 | Tests | DE's harness before the code sync |
| D8 | Migration lineage | Keep AT's graphs; forward-port DE's model changes as new AT migrations, both apps |
| D9 | `fds_cms/0005` | Keep it; `--fake` on production ✅ |
| D10 | Static placeholders | Migrate to djangocms-alias ✅ |

**D2's running cost:** three permanent local patches, re-applied every sync —
`DONATION_SITE_NAME_OVERRIDE` in `fds_donation/forms.py`, `MIN_AMOUNT=2` in
`form_settings.py` (DE has 5), and the Erste/George column mapping in
`external.py`.

**D8's consequence:** `fds_cms` and `fds_donation` can never be `git`-pulled
cleanly from DE. Justified for `fds_cms` (21 plugin rows of AT content); forced
for `fds_donation`, where rows are real money.

---

## 2. Current state

### Done

- **Dependencies (D6).** DE's curated list, minus `froide-campaign`/`food`/`fax`/
  `legalaction`/`exam`/`crowdfunding`/`govplan`/`evidencecollection`/
  `pressconference`/`election`, `django-amenities`, `django-legal-advice-builder`,
  `osmium`, and `torch`+`torchvision` (~2 GB, only `fds_fximport` needed them).
  `django-flowcontrol` and `mjml-python` included ahead of D3.
- **Static placeholders → djangocms-alias (D10).** `fds_cms/0006`. `django-cms`
  unpinned to `>=5.0.5,<6`. Templates use `{% static_alias %}`.
- **Porting against upstream froide (D5).** `scripts/froide-source.sh okfde|fin|status`
  switches the sibling checkout; froide is installed editable so it is a checkout,
  not a reinstall. `devsetup.sh` pulls from the branch's upstream so a re-run does
  not undo the switch.
- **Test suite.** Was completely non-executing; now green.
  `tests/test_footer.py` covers both the live alias-rendered footer and the dead
  template copy. `tests/fixtures/cms.json` is regenerated from the production
  extract.
- **Search path.** CMS indexing and search work end to end; the index rebuilds and
  ranks correctly.
- Defects fixed: broken search-index listeners, `cms.models.Title` import,
  `page__node` / `page.placeholders` / `CMSToolbar` breakage, schemeless
  Elasticsearch hosts, iframe `src` stripped by the sanitiser, a bank-import
  filter that silently dropped sub-€1 transfers and refunds, empty `og:image`
  tags, a duplicated blocklist regex, a stray `print` corrupting `dumpdata`, and
  an N+1 query in `RegularDonorsProgressBarPlugin` (one query per donor).
- **Mechanical cleanup.** `package.json` pruned of JS deps for uninstalled Python
  apps, description corrected to Austria, dead `favicon` script removed; dead
  templates deleted (`snippets/temp.html`, `legal_advice_builder/`); dev
  Elasticsearch image bumped 7.15.0 → 8.15.1 (**needs a container rebuild to
  verify**); Celery rename runbook written.
- **Guards.** `tests/conftest.py` now aborts if `DJANGO_SETTINGS_MODULE` /
  `DJANGO_CONFIGURATION` are set to anything other than `pytest.ini`'s values —
  this container's ambient env trips it, which is the point. A non-blocking
  `de-drift` job in `ci.yml` reports divergence from DE (`--check-max-modified 260`;
  currently 240).

### Not done

Settings reconstruction, `fds_cms`/`theme` adoption from DE, `fds_donation`
adoption, frontend, template re-derivation, migration forward-porting, Austrian
donation receipts, translations.

---

## 3. Apps in both repos

### `fds_cms`

**AT has:** a hand-done django-cms 4/5 port (predating DE's), legacy structural
plugins (`Row`, `ColumnN`, `Container*`, `SubMenu`, `PageSubMenu` — 17 live
instances against 43 on the modern grid), `HomepageHero`/`HomepageHow`, an
`export_fdscms` dumpdata command, squashed migrations (7 vs DE's ~60).

**AT lacks:** `PublicBodyFeedbackPlugin` + contact form, CMS pages in site search
(`cms_apps.py` apphook — DE moved registration there), AVIF thumbnails.

**From DE (200 commits):** datashow and Datawrapper embeds, search-alert plugin,
dark-mode toggle, language switcher, video consent banner, FoiRequest map
template, page-annotation titles, 1h caching of plain CMS views.

*Germany-specific:* `load_georegion.py` is built around German shapefile schemas.

### `fds_donation`

**AT has:** `RegularDonorsProgressBarCMSPlugin`, Austrian banking (IBAN/BIC,
creditor ID, Forum Informationsfreiheit as payee), `DONATION_SITE_NAME_OVERRIDE`,
`MIN_AMOUNT` 5→2, an Erste Bank/George statement importer.

**AT lacks:** all newsletter and mailing coupling (`Donor.subscriber` FK,
`SetupMailingMixin`), donation purpose and receipt opt-in (both `HiddenInput`),
SEPA direct-debit reconciliation, `DONATION_LOGIC_PLUGINS`.

**From DE (374 commits — the largest delta):** `Recurrence` model with cancel
reasons and upgrade flows, `DonorEvent` audit trail, donor self-service auth,
django-flowcontrol integration, gift-order shipping with Internetmarke export,
IBAN in donor export, refund handling, a real test suite. Migrations 44 → 79.

*Germany-specific, needs Austrian replacement:*
1. **`zwb.html` — the Zuwendungsbestätigung.** AT wrapped the entire body in
   `{% comment %}`, so it renders a **blank PDF**. The German form is the §50 EStDV
   Muster with an OKF Berlin letterhead. Austria's equivalent is
   **Spendenabsetzbarkeit** with mandatory **FinanzOnline** electronic reporting
   (§18 Abs 1 Z 7 EStG) — a data submission, not a PDF. The whole `export.py` /
   `get_zwb_data` / `send_jzwb_mailing_task` / `backup_jzwb_pdf_task` pipeline
   needs rebuilding. **Largest genuinely new piece of work in this plan.**
2. `remote_filing.py` / `DONATION_BACKUP_URL` — confirm these point at Austrian
   infrastructure.
3. `sepa_notification.txt` carries no registration data since the OKF details were
   removed; Austrian ZVR practice may require some.

### `fds_ogimage`

Byte-identical to DE, but disabled everywhere and `FDS_OGIMAGE_URL = ""`. Either
host an AT ogimage service or remove the app. Until then `SITE_LOGO` is unset, so
social shares have no image.

### `theme`

**AT has:** `colors.py`, vendored webfonts, local template overrides,
`update_georegion.py`.

**AT lacks:** `fds_tags.py` filters, `admin.py`, `cms_plugins.py`, `glyphosat.py`,
the custom homepage view, `inject_status_change` (DE redirects to a donation ask
after a request is marked successful — worth revisiting as an AT fundraising hook).

*Corrected:* `legal_backup.py` is **not** Klageautomat machinery and is not dead —
it is a data-retention backup of a departing user's requests, fired by
`account_future_canceled`, and it applies to AT as much as DE. AT's copy used the
Google Drive API, which was never a dependency of either repo, so it failed on
every account cancellation. Now on DE's WebDAV implementation, skipped when
unconfigured.

*Dead machinery removed:* `amenity_updater.py` and its task (OSM ingestion for
uninstalled apps). Still present and still German: `update_georegion.py` hardcodes
the **ARS** key lengths (2/3/5/9/12) and cannot load Austrian
Gemeindekennziffern.

### `settings/`

AT's changes are subtraction-by-comment plus identity substitution. `de-at` single
language, `.at` domains throughout, `google.at` search, Austrian greetings added on
top of DE's.

*Correctly removed:* `FROIDE_FOOD_CONFIG`, `AMENITY_TOPICS`, Telnyx, Slack channel,
Frontex captcha, campaign providers.

*Kept and needs review:* `recipient_blocklist_regex` is entirely German (de-mail,
BND, bahn.de, jobcenter-ge.de) with nothing Austrian; `default_law` 2→1;
`target_countries` removed; `content_urls["pseudonym"]` commented out, so the
pseudonym help link is dead; `TEXT_ADDITIONAL_PROTOCOLS = ("bank",)` supports
banking deep links AT deleted from its templates.

*From DE:* `django-cookie-consent`, `django-datashow`, `django-flowcontrol`,
`USER_LANGUAGES`/`de-ls`, `CELERY_TASK_ROUTES`, `query_preprocessor`,
`FLOWCONTROL_TEMPLATE_FILTERS`, `XFrameOptionsCSPMiddleware`.

### Celery

Small surface. AT's `production.py` adds `check_mail_log` (every minute) — AT-only
and load-bearing for delivery status. DE routes `run_subscriber_import` to a
`convert` queue; AT has no task routing.

**All five `fds_donation` tasks are still registered as
`fragdenstaat_de.fds_donation.*`** (the `theme` tasks were renamed; these were
missed). Any beat schedule or queue rule must use the DE namespace. Renaming is a
drain-and-deploy operation, not a code edit.

`remind_unreceived_banktransfers` is documented "run on the 15th" but nothing in AT
schedules it — confirm it exists in the deployment's beat config.

The rename procedure is written up in `docs/runbooks/celery-task-rename.md`.

### Templates

AT extends froide/DE templates and empties the blocks that referenced disabled
apps: crowdfunding and Klageautomat tabs, campaign questionnaires, fax sending, the
glyphosat BfR download modal, newsletter settings, Matomo.

Also emptied from `foirequest/header/header.html`, each a DE editorial hook with no
AT equivalent: EU-office banner, Klima-Helpdesk banner, a hardcoded Corona/RKI
banner, the Schriftformerfordernis fax prompt.

**AT-only:** `footer.html`, `foirequest/emails/presserecht/overdue_reply.txt`
(Austrian press-law chase-up — genuinely AT-specific law), homepage snippets,
reworked signup confirmation emails.

⚠️ **The footer exists twice and the template is the dead copy.** The live site
renders the CMS static alias (migrated in `fds_cms/0006`) via
`{% static_alias "footer" %}` in `base.html`. Editing `templates/footer.html` has
no effect. The alias also stores *hash-stamped* static URLs pasted into its HTML,
so sponsor logos break on any `collectstatic` that changes those files — fix
during template work. Verified: those four are the *only* hashed URLs on the live
page (everything template-rendered is unhashed), so they are orphans from an older
deployment that used manifest storage. They resolve today; nothing regenerates
them.

*Germany-specific left in place:* `base.html`'s `metadescription` is still German
IFG boilerplate; Austria's Informationsfreiheitsgesetz (in force 2025) replaced the
Auskunftspflichtgesetz. `snippets/meta.html` still carries DE's
`google-site-verification` token.

### Frontend

AT: 65 files, DE@HEAD: 98. AT added `base.scss`/`globalvars.scss`, StixTwo serif,
dropdown/modal tokens, Vite 6 + pnpm. Search is commented out of `main.ts`.

---

## 4. Apps in DE, absent from AT

**`fds_newsletter`** — self-hosted double-opt-in subscriptions. `Newsletter` +
`Subscriber` (per-newsletter, campaign attribution, taggable), CMS plugins,
onboarding schedule, cleanup tasks. DE has since added segments, archiving and
subscriber import. No German specifics beyond hardcoded slugs.

**`fds_mailing`** — campaign email composition and sending. `EmailTemplate` (CMS
placeholder body with dedicated email plugins, bound to a froide mail intent),
`Mailing` (state machine, scheduled sends), `MailingMessage` (per-recipient,
linked to Subscriber **or Donor** or User). Public web archive of past mailings.
No German specifics.

**`fds_blog`** — editorial CMS: `Article` from mixins, `Author` decoupled from
`User`, translatable categories, Elasticsearch, RSS, Google-News sitemap, latest/
preview plugins. No German specifics.

**`fds_fximport`** — Frontex portal scraper with a Torch captcha solver and a
pinned CA. Single-purpose, pulls in ~2 GB of dependencies. Do not adopt.

**New in DE since the fork:** `fds_easylang` (Leichte Sprache as its own `de-ls`
language with stripped-down templates, deliberately outside `USER_LANGUAGES` — the
best-designed thing to copy, and Austria has an equivalent accessibility
expectation), `fds_events` (event calendar), `fds_paperless` (Paperless-ngx
bridge).

---

## 5. AT-only

No new Django apps. What is AT's alone:

- `fragdenstaat_at/scripts/` — two one-shot 2019/2021 DB migration scripts.
  Historical record; keep as documentation, not runnable.
- `sync_froide_translations.py` — seeds `locale/de_AT/` from froide's catalogue.
  Target directory does not exist yet; reads froide from a hardcoded `../froide/`.
- `.devcontainer/`, `compose-dev.yaml`, `devsetup.sh`, `Makefile`,
  `export_dev_db.py` — a working local environment DE does not have in this form.
  **Preserve through any rebase.**
- `scripts/de_drift.py`, `scripts/froide-source.sh`, `docs/runbooks/`.
- Within shared apps: `RegularDonorsProgressBarCMSPlugin`, the legacy structural
  CMS plugins, `HomepageHero`/`HomepageHow`, `update_georegion.py`.

---

## 6. Constraints on the remaining work

**The production database is not stale.** It is fully migrated against its pinned
dependencies and was ~20 froide migrations behind upstream (since applied cleanly
in rehearsal). The multi-year gap is in the *code*, not the *data*. It runs
django-cms 4/5 with versioning — that major migration is already done in both code
and data.

**The dev extract is schema-faithful but not content-faithful.**
`export_dev_db.py` truncates application tables and writes `public_id` into *both*
the draft and public FKs, so draft/public divergence cannot be exercised locally.
Anything depending on that divergence must be reasoned about, not rehearsed —
and rehearsed against a real production dump before deploy.

**Row counts are unknown.** `foirequest_*`, `account_user`, `fds_donation_*` and
`froide_payment_*` are truncated in the extract. They, not the 10 CMS pages,
determine the migration window. Measure on production before scheduling.

**`values_list(...).distinct()` does not dedupe** when the queryset carries a Meta
ordering — the ordering columns leak into `SELECT DISTINCT`. This silently produced
duplicate rows in a migration that exited 0. Assume it applies to the remaining
forward-ports; verify migration *output*, not just exit codes.

**Migration dependencies are under-declared.** `fds_cms/0002` FK'd
`filingcabinet.DocumentPortal` without depending on the migration that creates it;
it only worked by graph accident. Expect more of these as ordering changes.

**`uv` has two traps.** `uv sync` replaces the editable sibling checkouts (froide,
froide-payment, django-filingcabinet) with git installs and silently breaks
`froide-source.sh` — always re-run the three `uv pip install -e` lines, as
`devsetup.sh` does. And `uv lock` keeps stale-but-satisfiable pins, so loosening a
constraint does not upgrade it; use `--upgrade-package`.

**Environment variables override `pytest.ini`.** A shell left over from a
`manage.py` session runs the suite under the wrong settings. Unset
`DJANGO_SETTINGS_MODULE` and `DJANGO_CONFIGURATION`. `tests/conftest.py` now
refuses to run rather than silently using the wrong settings.

**Elasticsearch:** `deps/elasticsearch/Dockerfile` is bumped to 8.15.1 to match the
locked client, but **this is unverified** — it cannot be rebuilt from inside the
container. Rebuild and re-run a `search_index --rebuild` before relying on it. ES 8
enables security by default; `xpack.security.enabled=false` is already set in
`compose-dev.yaml`.

---

## 7. Remaining work

Marked **[A]** automatable / cheap, **[R]** needs review, **[H]** genuine
design or legal judgement.

### P1b — finish the test harness (D7) · ~3 days

Adopt DE's harness proper: its `fragdenstaat_de/tests/` package layout, async
Playwright, the sequential browser-test group, and the `database-cache` workflow.
AT's suite is now a working baseline to migrate *from*. **[R]**

### P2 — rebuild the AT layer against DE@HEAD · 3–4 weeks

1. **D3 execution — ✅ done.** Both apps vendored from DE@HEAD (138 files) and
   wired, along with `flowcontrol`. `Donor.subscriber` restored as
   `fds_donation/0045` (plain nullable `AddField`, no backfill). Donor admin
   re-coupled: `SetupMailingMixin`, subscriber raw-id/filter/`select_related`/CSV
   column, `DonorAdminForm` widget. The newsletter opt-in is hidden and defaults
   to no, and DE's `?newsletter` bypass is not carried over.

   Three things worth knowing:

   - **The vendored migrations were replaced with generated initials.** DE's
     `fds_mailing.0023` depends on `fds_donation.0063`, unresolvable against AT's
     lineage ending at `0044` (D8(b)). Safe because AT had no newsletter/mailing
     tables and the vendored history holds zero data migrations. Verified on a
     clean extract: 29 tables, exit 0.
   - **Two shims** were needed: `fds_cms.utils.get_alias_placeholder` (ported;
     works because D10 moved static placeholders to aliases) and a minimal
     `theme/admin.py` with `PublicBodyAdmin` — DE's version also customises User,
     GeoRegion, Amenity and InformationObject and would drag back
     `django-amenities` and other apps D6 dropped.
   - **Three DE test modules are ignored** in `pytest.ini`, with the reason and
     the condition for restoring them. They drive subscribe/confirm/unsubscribe
     views through `reverse()`, which cannot resolve while AT routes no
     subscription URLs. ⚠️ One of them,
     `fds_mailing/tests/test_mailing.py`, fails because a mailing embeds an
     unsubscribe link — **if mailing is ever enabled, a working unsubscribe route
     is legally required, not optional**, and those tests must come back with it.

   Fixed in passing: `setup_mailing_messages` reported "Prepared mailing … with N
   recipients" while the `bulk_create` was commented out. It created nothing and
   said it had.

2. **Settings.** Rewrite `settings/base.py` as DE@HEAD's file plus an explicit AT
   override block — configuration, not commented-out code (D2). Resolve the items
   flagged in §3. **[H]**

   *Measured:* DE defines **114** settings in `base.py`, AT **71**. DE has 49 AT
   lacks; AT has 6 DE lacks (`CKEDITOR_SETTINGS`, `CMS_LANGUAGES`,
   `DONATION_SITE_NAME_OVERRIDE`, `LANGUAGE_CODE`, `TESSERACT_LANGUAGE`,
   `TEXT_ADDITIONAL_PROTOCOLS`). Most of the 49 belong to apps AT does not run
   (amenities, campaign, food, govplan, telnyx/fax, paperless, easylang,
   evidencecollection). Worth evaluating for AT:

   `STORAGES` ✅ done · `THUMBNAIL_ALIASES` / `THUMBNAIL_DEFAULT_ALIAS` /
   `FDS_THUMBNAIL_ENABLE_AVIF` · `CMS_COLOR_SCHEME(_TOGGLE)` ·
   `CMS_REDIRECT_TO_LOWERCASE_SLUG` · `VERSIONING_ALIAS_MODELS_ENABLED` (relevant
   post-D10) · `FLOWCONTROL_CONTENT_TYPES` / `FLOWCONTROL_TEMPLATE_FILTERS` (now
   that flowcontrol is installed) · `SENDER_DOMAINS` (mailing sender validation) ·
   `SITE_LOGO` (unset, which is why social shares have no image) · `CREW_GROUP` ·
   `LEAFLET_CONFIG` · `USER_LANGUAGES` · `APP_SITE_URL` ·
   `PAYMENT_SUBSCRIPTION_ACCESS_FUNC` · `FILER_REMOVE_FILE_VALIDATORS` ·
   `COOKIE_CONSENT_*` · `DEFAULT_CURRENCY_LABEL` / `_SYMBOL`.

   ⚠️ **Look for dead configuration, not just missing configuration.**
   `STATICFILES_STORAGE` had been silently ignored since Django 5.1 removed it,
   along with the `MyStaticFilesStorage` subclass it named — which only overrode
   `manifest_strict`, a no-op on a non-manifest backend. Dead twice over and
   invisible. (`CKEDITOR_SETTINGS` was checked for the same failure and is fine:
   `djangocms_text` still reads it.)

3. **`fds_cms` / `theme` / `fds_ogimage`.** Take DE's versions; re-apply
   `HomepageHero`/`HomepageHow`, `export_fdscms`, AT template overrides. Adopt DE's
   `cms_apps.py` apphook to restore CMS pages in site search. Delete the dead German
   machinery identified in §3. **[R]**

4. **`fds_donation`.** Take DE@HEAD, re-apply the AT layer: Austrian banking,
   `DONATION_SITE_NAME_OVERRIDE` 🔁, `MIN_AMOUNT=2` 🔁, `country="AT"`,
   `DONATION_PROJECTS=["FOI"]`, the Erste/George importer 🔁, and
   `RegularDonorsProgressBarCMSPlugin`. Re-enable `update_direct_debit` against
   Austrian reference formats. **[H]**

   ⚠️ Nothing in the suite exercises `RegularDonorsProgressBarPlugin` or the bank
   importer, so both were changed on this branch without test cover — the plugin
   query was checked by hand against an extract whose donation tables are empty,
   which proves the SQL valid but not the arithmetic. Add tests here.

5. **Frontend.** Adopt DE's `frontend/`, re-applying AT's `base.scss`,
   `globalvars.scss`, StixTwo and dropdown tokens. **[R]**

6. **Templates.** Re-derive AT overrides against DE@HEAD. Rewrite `base.html`'s
   `metadescription` for the Austrian IFG. Drop DE's `google-site-verification`.
   Fix the hash-stamped static URLs in the footer alias. **[H]** for copy,
   **[A]** to locate.

7. **Preserve** `.devcontainer/`, `compose-dev.yaml`, `devsetup.sh`, `Makefile`,
   `export_dev_db.py`, `scripts/`, `tests/`, `.github/` verbatim. **[A]**

8. Run the footer gate (`tests/test_footer.py`) after every template or settings
   step — it is the smallest markup exercising the AT identity end to end. **[A]**

### P3 — migrations (D8) · ~1 week + staging

Forward-port DE's `fds_cms` and `fds_donation` model changes as new AT migrations
(`0008…`, `0045…`). No graph reconciliation is needed under D8(b). Verify migration
*output*, not exit codes. Rehearse against a production-shaped dump. **[R]**

Note for the runbook: production needs a one-off
`manage.py migrate --fake fds_cms 0005` (D9), and must **not** be faked on a
database lacking those columns.

### P4 — Austrian donation receipts · 2–4 weeks · independent track

Design and build the Spendenabsetzbarkeit / FinanzOnline flow replacing the German
ZWB pipeline. Until it lands, do not un-hide the `receipt` form field. Gated on
external tax/legal input — **start immediately**, it is the long pole. **[H]**

### P5 — repeatable sync · ~1 day

The drift job is wired into `ci.yml` (non-blocking, limit 260). Remaining: tighten
the limit as P2 lands and the modified count falls, record the new baseline commit
here, and delete the commented-out DE code that D2's configure-out makes
redundant. **[A]**

### P6 — translations (D4/D5) · ~1 week · **LAST**

Deliberately last: relocating `de_AT` before P2 means re-syncing the catalogue every
time a label changes. froide keeps carrying it until then.

Fix `sync_froide_translations.py`'s hardcoded path; run it against the *final*
post-sync string set; fill in the msgstrs; land `locale/de_AT/`. Keep
`LANGUAGE_CODE="de-at"` with `locale/de/` as fallback and `locale/de_AT/` as
override; reconcile against DE's `USER_LANGUAGES`/`de-ls` split. Then drop `de_AT`
from the froide fork and repin to `okfde/froide@main` — the D5 exit criterion.
**[H]**

---

## 8. Sequencing

Critical path **P1b → P2 → P3 → P6**, roughly 6–8 weeks, with **P4 (2–4 weeks)
running alongside from day one** — it is the only part gated on external input.

Open, and needing a human: everything marked **[H]** above, of which P4 is the only
one blocked on someone outside the team.

---

## 9. Pre-deploy TODO

Things that must be decided or done before this branch reaches production. None
of them block the merge work itself.

### 9.1 Settings that are product decisions, not merge mechanics

DE defines these and AT does not. All are optional — nothing crashes without them
(the only setting that *was* load-bearing, `SENDER_DOMAINS`, is already set).
Decide each, or consciously decline it:

| Setting | The decision |
|---|---|
| `USER_LANGUAGES` | Which languages appear in the switcher. AT runs single-language `de-at`; DE splits `LANGUAGES` from `USER_LANGUAGES` to hide `de-ls`. Only matters if AT adds a second language |
| `COOKIE_CONSENT_LOG_ENABLED`, `COOKIE_CONSENT_SECURE` | `django-cookie-consent` ships via D6 but is unconfigured and unused. Does AT want a consent banner? Interacts with whether AT reinstates analytics |
| `MATOMO_SITE_ID` | AT deliberately removed DE's Matomo. Reinstate with an AT instance, or stay untracked |
| `CMS_COLOR_SCHEME`, `CMS_COLOR_SCHEME_TOGGLE` | Dark mode. DE ships a toggle plugin; AT's theme has no dark palette yet, so this is a design decision first |
| `THUMBNAIL_ALIASES`, `THUMBNAIL_DEFAULT_ALIAS`, `FDS_THUMBNAIL_ENABLE_AVIF` | Image sizes and whether to serve AVIF. Affects storage and CDN volume |
| `LEAFLET_CONFIG` | Map defaults. DE's centre/zoom are German — needs Austrian values if AT ever enables maps |
| `DEFAULT_CURRENCY_LABEL`, `DEFAULT_CURRENCY_SYMBOL` | Cosmetic; both sites are EUR |
| `CREW_GROUP` | Name of the staff group froide treats as crew. Must match the group that actually exists in AT's database |
| `FDS_LEGAL_BACKUP_URL`, `FDS_LEGAL_BACKUP_CREDENTIALS` | **Now honoured.** A WebDAV target for the retention backup taken when a user cancels their account. Unset means no backup is kept — decide whether AT needs one, since it is a data-protection commitment either way |
| `CMS_REDIRECT_TO_LOWERCASE_SLUG` | URL normalisation. Changing it on a live site changes canonical URLs — check for SEO impact |
| `VERSIONING_ALIAS_MODELS_ENABLED` | Whether Aliases are versioned. Now relevant, since D10 moved static content into Aliases |
| `FILER_REMOVE_FILE_VALIDATORS`, `DJANGOCMS_VIDEO_YOUTUBE_EMBED_URL`, `APP_SITE_URL`, `PAYMENT_SUBSCRIPTION_ACCESS_FUNC` | Small; adopt with the app that needs them |

Also review `SECRET_URLS["admin"]`, currently the literal `"admin"` on both sites.

### 9.2 One-off production steps

- **`manage.py migrate --fake fds_cms 0005`** (D9). Must **not** be run on a
  database that lacks those columns — check `information_schema` first.
- **Celery task rename** — the five `fragdenstaat_de.fds_donation.*` names. Drain
  and deploy per `docs/runbooks/celery-task-rename.md`; not a code edit.
- **Confirm `remind_unreceived_banktransfers` is in the beat config.** It is
  documented "run on the 15th" but nothing in the repo schedules it.

### 9.3 Verify before trusting

- **Rehearse the migrations against a real production dump.** The dev extract is
  schema-faithful but not content-faithful — it collapses draft/public, so
  `fds_cms/0006` cannot be exercised against real divergence locally.
- **Measure production row counts** for `foirequest_*`, `account_user`,
  `fds_donation_*`, `froide_payment_*`. They set the migration window; the 10 CMS
  pages do not.
- **Rebuild the container to verify the Elasticsearch 8.15.1 bump.** Changed but
  never rebuilt; re-run `search_index --rebuild` afterwards.
- **`RegularDonorsProgressBarPlugin` and the bank importer have no test cover** and
  were both changed. The plugin query was hand-checked against an extract whose
  donation tables are empty — that proves the SQL valid, not the arithmetic.

### 9.4 Known live defects to fix before or with the deploy

- **The footer alias hardcodes hash-stamped static URLs** (four sponsor logos).
  They are orphans from a deployment that used manifest storage; production no
  longer hashes. They resolve today, but `collectstatic --clear` or any edit to
  those source images breaks them.
- **`zwb.html` renders a blank PDF** and the donation receipt field is hidden.
  Leave hidden until P4 lands the Austrian FinanzOnline flow.
- **Attach the CMS search apphook to a page.** `FdsCmsSearchApp` is ported and
  registers, but an apphook does nothing until it is attached to a CMS page in
  the admin (DE attaches it to its help section). Until then CMS pages stay
  missing from site search.
- **If mailing is ever enabled, a working unsubscribe route is legally required.**
  Three DE test modules are currently ignored for exactly this reason.

### 9.5 Housekeeping

- The working branch `sync/de-head-2026-08` is **not pushed**. `main` is safe on
  origin; this branch exists only in the dev container.
