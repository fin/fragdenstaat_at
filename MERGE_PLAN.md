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
1. [x] **`zwb.html` — the Zuwendungsbestätigung.** AT wrapped the entire body in
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

Byte-identical to DE and **deliberately kept** — an AT ogimage service is to be set
up later. Currently inert: absent from `INSTALLED_APPS` and `theme/urls.py`, with
`FDS_OGIMAGE_URL` empty (now read from the environment rather than hardcoded).
Social shares fall back to `SITE_LOGO`, which is set, so the interim behaviour is
sane rather than broken. Enabling it is a four-step checklist in §9.2.

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
uninstalled apps). `update_georegion.py` is **left in place on purpose** — it is
German (hardcoded **ARS** key lengths 2/3/5/9/12) and cannot load Austrian
Gemeindekennziffern, but georegions are not in use, so it is inert. See §9.7.

### `settings/`

AT's changes are subtraction-by-comment plus identity substitution. `de-at` single
language, `.at` domains throughout, `google.at` search, Austrian greetings added on
top of DE's.

*Correctly removed:* `FROIDE_FOOD_CONFIG`, `AMENITY_TOPICS`, Telnyx, Slack channel,
Frontex captcha, campaign providers.

*Kept and needs review:* `recipient_blocklist_regex` is entirely German (de-mail,
BND, bahn.de, jobcenter-ge.de) with nothing Austrian; `default_law` 2→1;
`target_countries` removed; `TEXT_ADDITIONAL_PROTOCOLS = ("bank",)` supports
banking deep links AT deleted from its templates. (`content_urls` is now fully
populated — `514038b` — but the six froide-rendered keys point at AT help pages
that must be confirmed to exist; §9.0.)

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

*Germany-specific:* both fixed. `base.html`'s `metadescription` was DE's copy
describing German law (incl. `Transparenzgesetz`, a German-state concept) and is
rewritten for Austria — ⚠️ **it is SEO copy and wants review by whoever owns AT's
messaging**. `snippets/meta.html` carried a `google-site-verification` token
identical to DE's, which is wrong in both directions; removed.

### Frontend

AT: 65 files, DE@HEAD: 98. AT added `base.scss`/`globalvars.scss`, StixTwo serif,
dropdown/modal tokens, Vite 6 + pnpm. Search is commented out of `main.ts`.

⚠️ **Do not "adopt DE's frontend" wholesale.** Unlike the Python apps, most of
this tree is *visual identity*, not shared machinery: DE carries Gregory Grotesk,
its UBF campaign artwork and its own palette, while AT has its own dropdown, dark
mode and colours. Treat the frontend as AT's, and cherry-pick DE's *functional* JS
fixes only. 32 files differ; almost all are stylesheets.

**Fixed:** every `@font-face` in AT's CSS was 404ing in production — the site
rendered in system fallback fonts. `type.scss` came from DE in Aug 2025 and builds
its `src` paths from a mixin expecting variable-weight subsets
(`fonts/inter/inter-latin.woff2`, `fonts/stixtwo/stixtwo-latin.woff2`), but AT
shipped the older static-weight naming and no StixTwo at all. Vite passes an
unresolvable `url()` straight through instead of failing, so the build stayed
green and nothing surfaced it.

#### The 32 differing files, categorised

Not all 32 need to stay different — only ~11 do. Measured by inspecting each diff:

| | Category | Files | Action |
|---|---|---|---|
| **A** | Formatting noise — missing trailing newline, `: number = 0` vs `= 0` | `styles/variables.scss`, `styles/main.scss`, `javascript/sentry.ts`, `javascript/magnifier.ts` | **Take DE.** Zero behaviour change; removes 4 files from the diff for free |
| **B** | DE bugfixes AT never got | `javascript/fds_cms.js` (`room.close()` + stale-`cms_cookie` bust), `javascript/smooth-scroll.ts` (guard against cross-host/cross-path anchors), `javascript/misc/highlight-anchor.ts` (try/catch around an invalid selector), `javascript/slider.js` (AT replaced the error log with `/* */`) | **Take DE.** |
| **C** | DE utilities/features AT simply lacks | `javascript/vegacharts.js` (dark-mode chart theme + tooltips), `styles/misc.scss` (`.hyphens-auto`, `.highlight-target`), `javascript/misc/reveal-more.ts`, `misc/shuffle-items.ts`, `styles/cards.scss`, `cms_documents.scss`, `cms_elements.scss`, `glider.scss`, `help.scss` | **Take DE**, then eyeball. Additive, but they touch rendering |
| **D** | AT's visual identity | `styles/header.scss`, `homepage.scss`, `blog.scss`, `donations.scss`, `collapsible.scss`, `cms_utils.scss`, `vega.scss`, `type.scss` | **Keep AT.** This is the genuine 8-file divergence |
| **E** | AT's deliberate module/import lists | `styles/base.scss` (`banner`/`legal_actions` commented out — apps AT lacks; DE added `easylang`), `javascript/misc.ts`, `javascript/main.ts` | **Keep AT's**, but merge DE's *new* entries selectively — AT is missing `datawrapper`, `autosubmit`, `inline-detailbox` |
| **F** | Stale DE config AT must not keep | `javascript/misc/matomo.ts` | **Fix or delete.** AT's copy hardcodes `setDomains(['*.fragdenstaat.de'])` and `setSiteId('25')` — DE's Matomo property. Inert only because `misc.ts` has the import commented out; enabling analytics as-is would report AT traffic to DE |
| **G** | Belongs with its Python app | `javascript/donation-form.ts` | ✅ **Taken**, once step 4 landed. One AT override re-applied: the fee hint keyed on `lang === 'de'`, but AT serves `de-at`, so Austrian visitors silently got the English string — widened to `startsWith('de')` |
| **H** | Font tooling | `fonts/make_subsets.sh`, `fonts/requirements.txt` | **Take DE** — it generates the subsets AT now ships |

**Done.** A, B, C, H taken from DE; E merged selectively (only
`misc/autosubmit.ts` — AT already had `data-autosubmit` markup in the newsletter
templates with no JS behind it; `datawrapper` and `inline-detailbox` skipped as
zero-reference dead weight); F replaced with DE's host-derived version. **32 → 13
differing files**, all deliberate: AT's visual identity (8), its import lists (3),
and `donation-form.ts` (G, deferred to P2 step 4). `matomo.ts` was subsequently
deleted outright rather than kept in sync.

Noted in passing: `javascript/request.ts` is identical to DE's and hotlinks
`media.frag-den-staat.de` for a glyphosat loading GIF. Dead in AT — the feature's
templates were removed — but it still ships in the bundle.

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
- `manage_at_translations.py` — maintains `locale/de_AT/`: scan, adopt, and
  `--from-source` seeding of AT's own untranslated strings.
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

### Status board

- [x] **P1b** — test harness *(config + DE's donation tests: 37 → 119 passing, 1 xfail)*
  - [x] pytest config: markers, `--reuse-db`, warning filters, xdist grouping
  - [x] DE's `fds_donation/tests/` (15 modules), landed with P2 step 4
  - [x] align test tooling with DE — see "Dependency audit" below *(119 passing)*
  - [x] port DE's `theme/tests/` — search + translation *(121 → 154 passing)*
  - [ ] DE's `database-cache` CI workflow
  - [ ] revisit parallelism now the suite is larger
- [ ] **P2** — rebuild the AT layer *(7 of 8 done; only step 2 left, and it is [H])*
  - [x] 1. D3 execution — newsletter + mailing, no signup surface
  - [ ] 2. Settings — **[H]**, remainder is product judgement (§9.1)
  - [x] 3. `fds_cms` / `theme` / `fds_ogimage`
  - [x] 4. `fds_donation`
  - [x] 5. Frontend — 32 → 12 differing files
  - [x] 6. Templates
  - [x] 7. Preserve the dev environment
  - [x] 8. Footer gate in force (now joined by the page-render harness)
- [ ] **P3** — migrations
  - [x] forward-port as `fds_cms/0008` and `fds_donation/0046`
  - [x] **rehearsed against a production dump** — went through cleanly; see `docs/runbooks/live-db-verification.md`
- [ ] **P4** — Austrian donation receipts *(not started; needs external tax/legal input)*
- [x] **P5** — repeatable sync
  - [x] drift job wired into CI
  - [x] tighten `--check-max-modified` 260 → 140 (measured 127)
  - [x] record the new baseline commit
  - [x] delete commented-out DE code in `theme/views.py`, `theme/urls.py`
- [ ] **P6** — translations *(mostly done; D5 exit and 44 strings remain)*
  - [x] `de_AT` override catalog built, pruned to real overrides, annotated
  - [x] AT's own German ported from DE (`locale`, `fds_donation`, `fds_cms`)
  - [x] sync script covers AT's own catalogs and flags hardcoded German
  - [ ] 44 strings still untranslated (26 + 17 + 1), mostly admin-side
  - [ ] **D5 exit:** drop `de_AT` from the froide fork, repin `okfde/froide@main`

### Ported: DE's `theme/tests/` — and what they caught

AT had no `theme/tests/` at all, while running byte-identical copies of DE's
`theme/search.py` and `theme/translation.py`. Both modules are now ported
(`test_search.py`, `test_translation.py`, plus 342 lines of token/query fixtures),
taking the suite from **121 to 154 passing**. Three things fell out.

**1. `LanguageSwitcherPlugin` was broken — fixed.** `fds_cms/cms_plugins.py`
registers it, its template does `{% load fds_translation_tags %}`, and AT never
had that tag library — the port took the template and left
`theme/templatetags/fds_translation_tags.py` behind. Loading the template raised
`TemplateSyntaxError: 'fds_translation_tags' is not a registered tag library`, so
any editor adding "Language Switcher" from the Elements module would have got a
500. Not present in live content, so it was latent. The tag library is now ported
and the template loads.

**2. Elasticsearch 8.15.1 is too old — needs a devcontainer rebuild.**
`theme/search.py` sets `no_sub_matches=True` on the hyphenation_decompounder to
stop `formation`/`format`/`form` being pulled out of *Informationsfreiheit*.
Elasticsearch below 8.16 **accepts the option and silently ignores it** — no
error, just a noisier index and worse search. `deps/elasticsearch/Dockerfile` now
pins **8.19.3**, matching DE. 8.15 → 8.19 is within one major version, so the
existing `es-data` volume is compatible (unlike the 7.15 → 8.x bump, which had to
be reverted).

Both repos keep the server image and the Python client on the *same* version —
AT's 8.15.1 image was not arbitrary, it matched AT's pinned client. Bumping the
image alone would have broken that convention, so the client stack moved with it
and AT now matches DE exactly:

| | before | after / DE |
|---|---|---|
| `elasticsearch` | 8.15.1 | **8.19.3** |
| `elasticsearch-dsl` | 8.15.2 | **8.18.0** |
| `django-elasticsearch-dsl` | 8.0 | **8.2** |

Same stale-lock pattern as playwright and pytest-factoryboy: nothing pinned these
down, the entries had simply never been upgraded.

✅ **Rebuilt and confirmed.** The devcontainer now runs 8.19.3 and all 102
decompounder tests pass — the capability gate in `theme/tests/conftest.py`
cleared itself, as designed. It stays in place: it is the thing that turns "our
search silently got worse" into a legible skip message.

The Dockerfile also now pins the german-decompounder data to DE's commit instead
of tracking `master` — those two files define how compounds split, so an upstream
change would silently move the expectations in `testdata/search_tokens.py`.

- [ ] **Check the production Elasticsearch version.** If it is below 8.16, AT's
  search is quietly running without `no_sub_matches` today. Nothing errors; the
  index is just noisier. Dev is now on 8.19.3. **[R]**

### Library drift beyond the test tooling

**130 of 228 shared packages resolve to different versions than DE** — 97 where
AT is behind, 33 ahead. Nearly all of the "behind" set is 2022-era: `packaging`
22.0, `urllib3` 1.26.13, `faker` 15.3.4, `idna` 3.4, `pytest-django` 4.5.2. These
are unconstrained transitive and dev dependencies that were locked around the
January 2023 fork and never refreshed. Declared constraints are *identical*
between the repos; this is purely lock staleness.

Acted on, because it was on a live path:

- [x] **`django-payments` 1.0.0 → 3.1.0.** froide-payment declares it
  unconstrained and it is the library froide-payment is built on. AT sat two
  majors behind DE while running `froide-payment@main`, which upstream develops
  against 3.x. Left free it resolves to **4.1.0**, so `[tool.uv]
  constraint-dependencies` pins `>=3.1,<4`.

  The cap is a hard incompatibility, not caution. **4.0.0 dropped
  `StripeProvider`** (deprecated in 3.0.0); 4.1.0's `payments/stripe/` exports
  `StripeProviderV3` and nothing else — the old name appears nowhere in the
  package. `froide_payment/provider/stripe.py:21` still does `from
  payments.stripe import StripeProvider` and subclasses it at line 1140 for
  `StripeSofortProvider`, and `provider/__init__.py` imports that
  unconditionally. On 4.x, `import froide_payment.provider` raises
  `ImportError` and the site does not boot — taking down the Stripe and PayPal
  providers AT does use, not just Sofort.

  Lifting the cap is a froide-payment change, not a bump here: port
  `StripeSofortProvider` to `StripeProviderV3`, or drop it (AT already has it
  commented out at `settings/production.py:104`). 4.0 also drops Django < 5.2
  and Python < 3.10 — AT satisfies both — and fixes a `StripeProviderV3`
  `captured_amount` bug that breaks refunds, which is worth having eventually.

  DE is on 3.1.0 too, but by **lock inertia, not decision**: DE declares no
  bound either, and its 2026-08-17 "Update dependencies" commit changed a
  single unrelated `uv.lock` line. Do not read DE's 3.1.0 as a tested ceiling.

Worth a decision, not yet acted on:

- [ ] **`django` 5.2.6 → 5.2.15.** Nine patch releases behind inside the pinned
  `>=5.2,<5.3` range. Django patch releases are where security fixes ship. **[R]**
- [ ] **`urllib3` 1.26.13 → 2.7.0** — a whole major behind, and the 1.26 series
  carries known advisories. **[R]**
- [ ] **`pandas` 3.0.3 — AT is a major *ahead* of DE's 2.3.3.** pandas 3.0
  changed defaults (copy-on-write, string dtypes), and AT parses bank statements
  with it (`fds_donation/external.py`: `read_excel` for Erste/George `.xls`,
  `read_csv` for PayPal). `tests/test_external.py` covers the import and passes,
  which is real reassurance, but this is the one place where being ahead of DE
  carries risk rather than benefit. **[R]**
- [ ] AT's CMS stack is also ahead: `django-cms` 5.1.1 vs 5.0.7,
  `djangocms-versioning` 2.7.0 vs 2.5.1, `djangocms-frontend` 2.5.1 vs 2.4.0. We
  ported DE's CMS code onto a newer CMS than DE tests against. Nothing has broken,
  but it explains oddities like the stale `page.placeholders` test. **[R]**

A blanket `uv lock --upgrade` would close most of the remaining 97 and the suite
(256 tests) would catch a lot of it, but it should be a deliberate step of its
own, not folded into the merge.

**3. Two AT-specific adaptations in the port**, both recorded in the files:
`get_document_classes()` drops `ArticleDocument` and evidencecollection's
documents (apps AT does not install — and it runs at collection time inside
`@parametrize`, so an import would break the whole module rather than skip a
test); and the test index attaches its mapping via `elasticsearch_dsl.Index`
rather than froide's `get_index().document()`, which would also call
`registry.register_document()` and demand a `class Django: model = ...`. DE hands
it `fds_blog.Article`; AT has no fds_blog, and registering an unrelated model
would wire it into the global document registry for the whole session.

### Dependency audit — AT vs DE

Compared declared dependencies *and* resolved lock versions against DE.

**Runtime, DE has / AT lacks (15).** All deliberate D6 omissions, re-verified:
the eleven `froide-*` apps AT does not enable, plus `django-amenities`,
`django-legal-advice-builder`, `osmium`, and `torch`/`torchvision`. No action.

**Runtime, AT has / DE lacks (6).** `daphne`, `django-leaflet`,
`django-localflavor`, `django-tinymce`, `drf-spectacular`, `xlrd`. These are
mostly AT declaring explicitly what DE inherits transitively through froide —
harmless, and arguably more honest than DE. `xlrd` is a genuine AT need (the
Erste/George `.xls` bank import). No version conflicts: **every dependency the
two declare in common carries an identical constraint.**

**Dev.** DE has `prek` (AT installs it as a system tool in the devcontainer, not
as a dev dep) and `pywatchman` (optional). AT adds `beautifulsoup4` (froide's
test package, installed `--no-deps`) and `polib` (`manage_at_translations.py`).

**The real finding was in the lock, not the manifest.** AT's declared constraints
looked fine while resolved versions had drifted years behind DE's, silently:

| package | AT (was) | DE | consequence |
|---|---|---|---|
| `playwright` | **1.18.1** | 1.60.0 | 4 years stale. No `get_by_role` — every DE browser test `AttributeError`s. |
| `pytest-factoryboy` | **2.5.1** | 2.8.1 | Calls `__pytest_wrapped__`; **collection of `fds_donation/tests/` died outright.** |
| `pytest-playwright` | sync | `-asyncio` | Wrong plugin entirely — DE's browser tests are `async def`. |

Nothing pinned any of these; the lock entries had simply never been upgraded.
Both packages now carry an explicit floor with the reason in `pyproject.toml`, so
a future `uv lock` cannot silently walk back. Also fixed: AT set
`DJANGO_ALLOW_ASYNC_UNSAFE` in `tests/conftest.py`, which only covers `tests/` —
DE sets it in `settings/test.py`, which covers everything. AT now matches.

Because `pytest-playwright` and `pytest-playwright-asyncio` both define a `page`
fixture and cannot coexist, AT's own browser test (`tests/test_donation.py`) and
the `page` fixture in `tests/conftest.py` were converted to async.

**Two AT-vs-DE divergences surfaced once the tests actually ran** — both were
masked while collection was broken:

- DE's donation form has three "Nein, danke." opt-outs; D3 removes the
  contact/newsletter one, so AT has two and DE's `get_by_text(...).nth(1)/.nth(2)`
  pointed at the wrong controls. Rewritten to address `#id_receipt_0` and
  `#id_account_1` by id, in all three of `test_banktransfer`, `test_stripe`,
  `test_paypal`.
- **AT addresses donors formally, DE informally.** AT's catalogue translates the
  thank-you as *"Vielen Dank für Ihre Spende!"*; DE's tests assert *"…für Deine
  Spende!"*. 11 assertions corrected. Worth remembering as a general rule when
  porting DE tests or copy: **Sie, not Du.**

Then §9.8 — the `Plan.slug` blocker — fell out of the recurring test.

### P1b — finish the test harness (D7) — ⚠️ mostly done

*Config adopted.* `pytest.ini` now registers DE's markers (`stripe`, `paypal`,
`elasticsearch`, `xdist_group`), excludes externally-keyed tests by default,
reuses the test database (**71s → 6.9s**), filters third-party deprecation noise,
and groups the browser test for `--dist loadgroup`.

Worth knowing: DE declares all of this under `[tool.pytest]` in `pyproject.toml`,
but pytest reads `[tool.pytest.ini_options]` and DE ships no `pytest.ini`, so
**upstream it has no effect** — hence the `PytestUnknownMarkWarning`s in DE's
output. AT's `pytest.ini` does work.

Parallelism is configured but not enabled: measured **156s at `-n 4` versus 6.9s
serial**, because each xdist worker builds its own database and setup dominates a
38-test suite. Revisit once DE's donation tests land and the suite is large enough
to amortise it.

✅ **DE's `fds_donation/tests/` landed with step 4** — 15 modules, taking the suite
from 37 to 118. *Remaining:* DE's `database-cache` CI workflow, and revisiting
parallelism now the suite is larger. **[R]**

### P2 — rebuild the AT layer against DE@HEAD — ⚠️ 7 of 8 done

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

2. [ ] **Settings.** Rewrite `settings/base.py` as DE@HEAD's file plus an explicit AT
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

3. [x] **`fds_cms` / `theme` / `fds_ogimage`.** ✅ **Done.**

   - **`fds_cms`**: DE's modules and templates adopted, schema forward-ported as
     AT `0008`. The 9 AT-only plugin classes re-applied. `datashow` and
     `cookie_consent` registered. Verified by rendering all 10 real CMS pages.
     `HomepageHowPlugin` + `snippets/homepage_how.html` since removed (8 AT-only
     plugins now); the hard-coded 3-step homepage block is authored as
     `<ol class="homepage-steps">` in a Text plugin, styled by
     `frontend/styles/homepage.scss` (ported from DE). Deploy: if any page still
     has a placed `HomepageHow` plugin, `manage.py cms delete-orphaned-plugins`
     after the code lands (django-cms renders an unregistered plugin as nothing).
   - **`theme`**: DE's `search.py`, `apps.py`, `cms_utils.py`, `models.py`,
     `utils.py`, `middleware.py`, `translation.py` adopted. Kept as AT's:
     `admin.py` (minimal subset — DE's drags back `django-amenities`),
     `tasks.py` (legal-backup guard), `views.py`, `urls.py`,
     `context_processors.py` (DE's only difference was exposing
     `MATOMO_SITE_ID`, and Matomo is gone from AT), and `update_georegion.py`
     (deferred, §9.6).
   - **`fds_ogimage`**: kept and made env-configurable; enabling checklist in §9.2.
   - Dead German machinery removed (`amenity_updater`); `legal_backup` corrected
     — it was never Klageautomat code and had never worked.

   ⚠️ **Renames on DE's side are the trap here**, not conflicts.
   `cms_utils.HostLanguageCookieMiddleware` became `LanguageUtilsMiddleware`,
   and AT's `MIDDLEWARE` still named the old class — the suite dropped 118 → 79
   until corrected. `theme/translation.py` was a new module `cms_utils` imports.

   ✅ **Search verified** against a live ES 8.15.1: index rebuilds (8 pages),
   `fds_analyzer` / `fds_search_analyzer` / `fds_search_quote_analyzer` all
   present, and relevance is sound — *Datenschutz* → Datenschutzerklärung (3.2),
   *Nutzungsbedingungen* → Nutzungsbedingungen (1.85).

   ⚠️ **Inherited defect, worth reporting upstream:** DE's `decomp` filter sets
   `no_sub_matches=True` with the comment *"Prevent 'formation' from being
   detected as a subtoken of 'informationsfreiheit'"*. The option **is** applied
   in the live index, but `Informationsfreiheit` still analyses to
   `[informationsfreiheit, information, info, formation, format, form, freiheit,
   frei]`. The precision fix does not do what it says on ES 8.15. Not a
   regression — AT is no worse than DE — but the stated intent is unmet.

4. [x] **`fds_donation`.** ✅ **Done.** DE@HEAD adopted (583 → 1359 model lines),
   schema forward-ported as a single AT migration `0046` per D8(b), keeping AT's
   45-migration lineage rather than DE's 79. Applied cleanly to an extract load,
   no drift after. Brings `Recurrence` (recurring donations move off
   froide-payment `Subscription`s), `DonorEvent`, donor self-service auth,
   `form_settings`, flowcontrol actions, gift-order shipping.

   AT's layer was **entirely overwritten by the adoption** and re-applied:
   Austrian bank details and creditor ID (6 templates), `MIN_AMOUNT=2`,
   `DONATION_SITE_NAME_OVERRIDE` on payment descriptors, Austria-first country
   choices, the Erste/George importer (now a named `BANK_COLUMNS` map with DE's
   recorded beside it), and `RegularDonorsProgressBarCMSPlugin`.

   ⚠️ **It also silently undid D3** — both the hidden `contact` field and the
   removed `?newsletter` bypass. Re-applied, and the first now uses DE's
   `hide_contact` setting (defaulting True for AT) instead of the hidden-field
   hack. **Expect the same on every future sync of this app**; the browser test
   catches the form half, nothing catches the bypass.

   Settings this required: `DEFAULT_CURRENCY_LABEL`/`_SYMBOL`,
   `PAYMENT_SUBSCRIPTION_ACCESS_FUNC`, and test-only `PAYMENT_VARIANTS` including
   `sepa` — without it the donor-link tests fail with "Payment variant does not
   exist". `theme/admin.py` also needed `make_tag_autocomplete_admin`.

   **Suite: 37 → 118 passing.** DE's 15 donation test modules now run against AT's
   code. Still unverified: behaviour against real donation rows, since the extract
   has none — that is the live-data rehearsal.

5. [x] **Frontend.** ✅ **Done.** 32 → 12 differing files. Categories A–H applied
   (see the table above): DE's version taken for formatting noise, bugfixes,
   additive utilities and font tooling; AT keeps its palette, dark mode and
   dropdown. Matomo removed entirely. Webfonts fixed — every `@font-face` was
   404ing in production. `donation-form.ts` taken once step 4 landed.

   The 12 remaining are deliberate: AT's visual identity (8), its import lists
   (3), and `banner.scss`/`banner.ts` now shared with DE.

6. [x] **Templates.** ✅ **Done.**
   - ✅ `base.html`'s `metadescription` rewritten for the Austrian IFG (**still
     wants a copy review** — §9.1).
   - ✅ DE's `google-site-verification` token removed.
   - ✅ `fds_cms` templates adopted from DE, after a line-by-line recheck showed
     none contained Austrian content and ~half the diff was djlint reformatting.
   - ✅ Footer-alias static URLs unhashed via `fds_cms/0009`.
   - ✅ **Top-level `templates/` re-derivation assessed, and deliberately not
     adopted.** `header.html` (346 lines) is genuinely AT's: DE links to
     `gegenrechtsschutz.de`, `ueberbrueckungsfonds.de` and `/kontakt/beratung/`,
     AT to `/hilfe` and `/info/ueber/`. The `foirequest/*` overrides are AT's
     deliberate emptying of blocks for features it does not run. Both stay.
   - ⏭️ The third-party plugin templates (`djangocms_picture/*`,
     `djangocms_video/*`) **are** stale copies of DE's, but adopting them pulls in
     `THUMBNAIL_ALIASES`, `THUMBNAIL_DEFAULT_ALIAS` and `FDS_THUMBNAIL_ENABLE_AVIF`
     — image sizes, AVIF and CDN volume, i.e. §9.1 product decisions rather than
     merge mechanics. AT's current template works (`thumbnail_dims` is registered),
     so there is no defect to force the issue. Moved to §9.1.
7. [x] **Preserve** `.devcontainer/`, `compose-dev.yaml`, `devsetup.sh`, `Makefile`,
   `export_dev_db.py`, `scripts/`, `tests/`, `.github/`. ✅ **Held** — all intact;
   `devsetup.sh` and `pytest.ini` gained deliberate changes, `scripts/` gained
   `de_drift.py` and `froide-source.sh`.

8. [x] ✅ **In force.** The footer gate runs in the suite. It has since been joined by
   a stronger check: **rendering all 10 real CMS pages from the extract**, which
   caught four breakages that returned HTTP 200 and that the test suite missed
   entirely (unregistered Column plugins, a missing `PublicBody` import, an
   unregistered `thumbnail_dims` filter, and `get_soft_root` on a lazy `None`).
   Use it after any template, plugin or middleware change.

### P3 — migrations (D8) — ⚠️ forward-port done, rehearsal outstanding

✅ **Forward-porting done.** `fds_cms/0008` and `fds_donation/0046` carry DE's
model changes; both applied cleanly to a fresh extract load with no drift after.
No graph reconciliation was needed under D8(b).

❌ **Remaining: rehearse against real data.** The extract has no donation rows, so
`Recurrence` and the donation schema are unexercised. This is the outstanding
assurance for the whole programme. **[R]**

Note for the runbook: production needs a one-off
`manage.py migrate --fake fds_cms 0005` (D9), and must **not** be faked on a
database lacking those columns.

### P4 — Austrian donation receipts — ❌ not started · 2–4 weeks · independent

Design and build the Spendenabsetzbarkeit / FinanzOnline flow replacing the German
ZWB pipeline. Until it lands, do not un-hide the `receipt` form field. Gated on
external tax/legal input — **start immediately**, it is the long pole. **[H]**

### P5 — repeatable sync — ✅ done

The drift job is wired into `ci.yml` (non-blocking, limit 260). **The limit is now
far too loose** — measured today:

| | at start | now |
|---|---|---|
| identical | 42 | **336** |
| modified | 240 | **134** |
| de-only | 635 | 447 |

✅ **Done.** The gate is now `--check-max-modified 140` (measured: 127), and the
commented-out DE code is gone from `theme/views.py` (68 comment lines → 0) and
`theme/urls.py` (55 → 11, the survivors being real explanations). Per D2, git
history is where dead code belongs.

**Baseline:** compare against `fragdenstaat_de@938901ef` (2026-08-17). Re-measure
with `python scripts/de_drift.py` rather than trusting numbers in prose.

### P6 — translations (D4/D5) — ❌ not started · **LAST**

Deliberately last: relocating `de_AT` before P2 means re-syncing the catalogue every
time a label changes. froide keeps carrying it until then.

✅ **The tooling is ready** — `manage_at_translations.py` (formerly
`sync_froide_translations.py`) no longer hardcodes
froide. It discovers sources from `LOCALE_PATHS` *and* `INSTALLED_APPS`, which
matters because packages disagree about where catalogs live: froide ships one
directory for the whole package (a pure app walk misses it entirely), while
froide-payment and filingcabinet ship one per app. Sources are limited to apps
living in a git checkout — the ones AT could fork — so third-party wheels do not
pollute the results with generic `IBAN` validator strings; `--all-apps` opts back
in. AT's own apps are always skipped: their German belongs in AT's own `de`
catalog, not in an override of itself.

Three modes:

- **scan** (default) — keyword-match each `de` catalog, add matches with an empty
  msgstr. An empty msgstr falls back to the app's own translation, so the entries
  are inert until filled in.
- **adopt** (`--adopt`) — import `de_AT` catalogs that already exist, msgstr and
  all. `--ref froide-payment=fin/main` reads them straight out of a fork branch
  **without checking it out**, which is how a fork's translations get moved into
  AT so the fork can be retired.
- **from-source** (`--from-source`) — extract the msgids AT's own code uses
  *right now* and seed those with no usable German: either untranslated
  anywhere, or carrying a German translation that names Germany. scan and adopt
  both read existing `de` catalogs, so a string nobody has ever translated is
  invisible to them — which is how AT-only wording added since the last catalog
  run ends up rendering in English with nothing to show for it. Extraction goes
  to a throwaway locale, so `locale/de` is never rewritten and stays a mirror of
  DE's. Currently reports **54** such strings, including the fax notice.

Measured today (`--dry-run --ref froide-payment=fin/main`): **585 existing
translations to adopt** (583 froide + 2 froide-payment) and **57 untranslated
candidates** (4 froide + 53 froide-payment). Re-running is idempotent and never
overwrites a msgstr that has content — verified by filling one in and re-running.

This works because AT's locale directory comes **first** in `LOCALE_PATHS`, ahead
of froide's, so one merged AT catalog overrides every app-level catalog.

Remaining, and still **[H]**: run it against the *final* post-sync string set,
fill in the msgstrs, land `locale/de_AT/`. Keep `LANGUAGE_CODE="de-at"` with
`locale/de/` as fallback; reconcile against DE's `USER_LANGUAGES`/`de-ls` split.
Then drop `de_AT` from the froide fork and repin to `okfde/froide@main` — the D5
exit criterion. Note the fork currently checked out is `okfde-main`, not fin's;
run `scripts/froide-source.sh fin` before starting.

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

### 9.0 Blockers — nothing ships until these are done

Ordered by what goes wrong if you skip them. Everything below this subsection is
either a decision, a verification, or a nice-to-have; these are the ones that put
wrong data in front of real people or break the deploy.

**Wrong content reaching users**

- [ ] **German identity in the mailing templates.** `fds_mailing/templates/email/
      default/base.html` carries `fragdenstaat.de` five times plus Open Knowledge
      Foundation Deutschland; `formal/base.html` one more. Every mailing AT sends
      goes out with German footers and links. Find them with
      `python manage_at_translations.py --dry-run` (§9.12). Same class as the
      bank details, which are now fixed.
- [x] **Five dead `reverse_id` links (three of them unguarded)** — §9.3. Set on
      the CMS pages, captured in `tests/fixtures/cms.json`, guarded by
      `tests/test_at_identity.py` (`test_page_url_ids_are_all_accounted_for` +
      `PageUrlResolutionTest`).
- [ ] **Six froide-rendered `content_urls` — settings done, three loose ends.**
      §9.3. `pseudonym`, `throttled`, `help_request_public`,
      `help_request_privacy`, `help_attachments_management`,
      `help_postupload_redaction` were all filled in by `514038b` (2026-08-23), so
      nothing falls back to the homepage. Against a fresh `cms.json`: `pseudonym`
      and `throttled` resolve; three (`help_*_public`, `*_attachments_management`,
      `*_postupload_redaction`) use froide's `/hilfe/plain/…` route, which needs
      the help apphook attached (no page in the extract has one); and
      `help_request_privacy` points at DE's `/hilfe/datenschutz-und-privatsphare/`
      — AT has `hilfe/privatsphaere`, so that one is a wrong value to fix. No test
      covers any of the six (`test_footer.py` only checks
      `terms`/`privacy`/`about`/`help`).

**Security** — both done

- [x] **`django` 5.2.6 → 5.2.17** and **`urllib3` 1.26.13 → 2.7.0.** Neither was
      constrained: `pyproject.toml` already allowed them (`django>=5.2,<5.3`),
      and every dependent's bound was satisfied — the tightest on Django is
      `<5.3` (AT, froide, django-payments) and on urllib3 `<3`. Both were stale
      lock entries from the 2023 fork, not decisions.

**Deploy mechanics, in order**

- [ ] **Check the `fds_cms/0005` precondition, then `migrate --fake`** (D9, §9.3).
      Must not run where those columns are absent — check `information_schema`
      first.
- [ ] **Celery task rename** — drain, then deploy, per
      `docs/runbooks/celery-task-rename.md`.
- [ ] **`migrate froide_fax`** — five migrations (`0001_initial` ..
      `0005_faxoverride_email_copy`), all new tables plus one `AddField`
      (`FaxOverride.email_copy`); nothing pre-existing is touched.
      Introduced by enabling the app, see §9.13.
- [ ] **`migrate fds_cms_at`** — one migration (`0001_initial`), two new tables
      (`RSSFeedCache`, `RSSFeedCMSPlugin`). AT-only app for the RSS-feed CMS
      plugin; `feedparser` is a new dependency (in `uv.lock`). Beat gains
      `refresh-rss-feeds` (every 30 min, `fragdenstaat_at.fds_cms_at.*`, default
      queue).
- [ ] **`uv sync --locked`**, shipping `uv.lock` and `pyproject.toml` with the
      code (§9.10). A plain `uv sync` may re-resolve and hand production an
      untested set.
- [ ] **Rebuild the Elasticsearch image** (8.19.3; also picks up `init: true`),
      and confirm production ES is **≥ 8.16** — below that `no_sub_matches` is
      silently ignored and search quality degrades with no error.
- [ ] **Confirm `django-payments` resolves to 3.x** — free resolution picks
      4.1.0, where `StripeProvider` no longer exists and
      `import froide_payment.provider` raises `ImportError`. The site does not
      boot. Verified against the 4.1.0 wheel, see §7.

**Rehearsal**

- [x] **P3: migrate a real production dump** — done, and it went through cleanly.
      `docs/runbooks/live-db-verification.md` is the procedure.
- [x] **Run §11 of that runbook (Stripe/PayPal) end to end.** All eleven payment
      tests pass against the sandboxes — three PayPal, eight Stripe.

---

### 9.1 Settings that are product decisions, not merge mechanics

DE defines these and AT does not. All are optional — nothing crashes without them
(the only setting that *was* load-bearing, `SENDER_DOMAINS`, is already set).
Decide each, or consciously decline it:

| Setting | The decision |
|---|---|
| ✅`USER_LANGUAGES` | Which languages appear in the switcher. AT runs single-language `de-at`; DE splits `LANGUAGES` from `USER_LANGUAGES` to hide `de-ls`. Only matters if AT adds a second language |
| ✅`COOKIE_CONSENT_LOG_ENABLED`, `COOKIE_CONSENT_SECURE` | `django-cookie-consent` ships via D6 but is unconfigured and unused. Does AT want a consent banner? Interacts with whether AT reinstates analytics |
| ✅~~`MATOMO_SITE_ID`~~ | **Resolved: Matomo is removed entirely.** The module, its commented import and the vestigial `_paq` calls in `top-banner.ts` are gone; nothing in the tree or the bundle references it. Introducing analytics is now a deliberate addition, and would need a decision about the host — DE's pointed at OKF *Deutschland's* instance |
| ✅~~`CMS_COLOR_SCHEME`, `CMS_COLOR_SCHEME_TOGGLE`~~ | **Resolved: shipping without dark mode is fine.** Verified that *nothing installed reads either setting* — not AT, not froide, not django-cms — so omitting them is a no-op, not a risk. AT has no dark palette anyway: `frontend/styles/darkmode.scss` is never imported, so the compiled CSS carries no dark theme (2 stray `data-bs-theme` form-control rules and nothing else), and `onion-darkmode.ts` only fires on `.onion` hostnames. DE's `DarkModeToggle` plugin arrived with its `fds_cms` and is now **unregistered in `fds_cms/apps.py`**, so editors are not offered a control that would do nothing. Reverse that block if AT ever builds a dark palette. |
| ✅`THUMBNAIL_ALIASES`, `THUMBNAIL_DEFAULT_ALIAS`, `FDS_THUMBNAIL_ENABLE_AVIF` | Image sizes and whether to serve AVIF. Affects storage and CDN volume. **Also gates adopting DE's `djangocms_picture`/`djangocms_video` templates**, which are otherwise stale copies (P2 step 6) |
| ✅`LEAFLET_CONFIG` | Map defaults. DE's centre/zoom are German — needs Austrian values if AT ever enables maps |
| ✅`DEFAULT_CURRENCY_LABEL`, `DEFAULT_CURRENCY_SYMBOL` | Cosmetic; both sites are EUR |
| ✅`CREW_GROUP` | Name of the staff group froide treats as crew. Must match the group that actually exists in AT's database |
| `FDS_LEGAL_BACKUP_URL`, `FDS_LEGAL_BACKUP_CREDENTIALS` | **Now honoured.** A WebDAV target for the retention backup taken when a user cancels their account. Unset means no backup is kept — decide whether AT needs one, since it is a data-protection commitment either way |
| ✅`CMS_REDIRECT_TO_LOWERCASE_SLUG` | URL normalisation. Changing it on a live site changes canonical URLs — check for SEO impact |
| ✅`VERSIONING_ALIAS_MODELS_ENABLED` | Whether Aliases are versioned. Now relevant, since D10 moved static content into Aliases |
| ✅`FILER_REMOVE_FILE_VALIDATORS`, `DJANGOCMS_VIDEO_YOUTUBE_EMBED_URL`, `APP_SITE_URL`, ~~`PAYMENT_SUBSCRIPTION_ACCESS_FUNC`~~ | Small; adopt with the app that needs them |

Also review ✅`SECRET_URLS["admin"]`, currently the literal `"admin"` on both sites.

Also: ✅**review the rewritten `base.html` meta description** — it is AT's search
snippet and was written here from the German original, not by anyone who owns the
messaging. And **add AT's own `google-site-verification` token** if AT uses Search
Console; DE's was removed rather than replaced.

#### Systematic settings comparison vs DE

Compared class-scoped (AT's `FragDenStaatBase` against DE's `FragDenStaatBase` +
`CMSSettingsMixin`; DE's `GegenrechtsschutzMixin`/`UbfMixin` are other sites DE
runs and are not comparable). **AT 92 settings, DE 127, 40 DE-only.** Most of the
40 belong to apps AT does not install (amenities, campaign, food, govplan,
evidencecollection, Telnyx/fax, Paperless) or are already-settled choices (Matomo
off, `CMS_COLOR_SCHEME*` — no dark mode). What is left:

- [x] **Rich-text editor.** `TEXT_EDITOR` defaults to `"tiptap"`
  (`djangocms_text/editors.py`), so AT's editors were getting TipTap while DE's
  get CKEditor 4 — and AT's `CKEDITOR_SETTINGS` toolbar block was configuring an
  editor that was not running. `theme/editor.py` is now ported (it also disables
  inline editing) and `TEXT_EDITOR` points at it. Verified: the editor resolves
  to `ckeditor4`.
- [x] **YouTube embeds now use the no-cookie domain**
  (`DJANGOCMS_VIDEO_YOUTUBE_EMBED_URL`), matching DE. AT ships `cookie_consent`,
  so an embed setting cookies on load was a consent problem, not a preference.
- [x] **`flowcontrol` enabled.** django-flowcontrol is an admin-configurable
  automation engine: a `Flow` is a tree of actions — `Condition`, `Delay`,
  `WaitForTrigger`, `State`, `ForLoop`, `EmailAlert`, `StartFlow` — executed per
  object, with a `FlowRun` tracking progress. It is the machinery behind donor and
  subscriber journeys (welcome series, lapsed-donor follow-up).

  AT already had the integration — `fds_donation` and `fds_newsletter` both
  register flowcontrol actions and triggers, and `fds_newsletter/0001` depends on
  `flowcontrol.0007` — only the configuration was missing. Now set:

  - ✅ `FLOWCONTROL_CONTENT_TYPES = ["fds_donation.donor",
    "fds_newsletter.subscriber", "account.user"]`, matching DE. Correcting an
    earlier note in this plan: unset does **not** mean flows have nothing to
    attach to, it means the opposite — `get_content_type_choices()` returns an
    empty `Q`, which filters nothing, so the admin offered all **317** installed
    content types. Now it offers 3.
  - `FLOWCONTROL_TEMPLATE_FILTERS = ["fragdenstaat_at.theme.filters"]`, with
    `theme/filters.py` ported from DE (`has_tag`, `has_all_tags` for use in flow
    conditions). Verified the resolved filter list is
    `['flowcontrol.filters', 'fragdenstaat_at.theme.filters']`.

  Migrations are already applied (7/7, nothing pending).

- [ ] **Schedule the flowcontrol beat tasks before relying on flows.** Nothing
  executes a flow on its own: `flowcontrol.tasks.enqueue_flowruns_task` picks up
  runnable `FlowRun`s and dispatches `execute_flowrun_task`, and
  `continue_flowruns_task` advances waiting ones. Neither DE nor AT schedules
  them in settings, because both run
  `django_celery_beat.schedulers:DatabaseScheduler` — the schedule lives in the
  admin, not the repo. So a fresh AT install has flowcontrol fully configured and
  still silently runs no flows until those two periodic tasks are added. Check
  what DE's production beat uses for intervals. **[R]**
- [ ] **No `CELERY_TASK_ROUTES`.** DE routes tasks across queues; AT runs
  everything on the default queue. **Accepted for now** — it only starts to
  matter when the newsletter is activated and bulk sends can block short tasks.
  Revisit together with the flowcontrol config above. **[R]**
- [x] **`CMS_PAGE_CACHE = True`** (was `False`). The django-cms issue it was
  disabled for is worked around by `monkey_patch_cms_cache()` in
  `fds_cms/models.py` — which AT carries **byte-identical to DE** and calls at
  import; it adds never-cache headers instead of caching whenever a response must
  not be shared between users. Verified with `scripts/verify_render.py` against a
  fully migrated database: 10/10 pages 200, no logged errors.
- [x] **`CMS_REDIRECT_TO_LOWERCASE_SLUG = True`** — capitalised legacy links
  redirect instead of 404ing.
- [x] **`FILER_REMOVE_FILE_VALIDATORS = ["application/octet-stream"]`**, as DE.
  Browsers and office suites send that content type for ordinary uploads, which
  django-filer's extension/content-type check would otherwise reject.

**Answered, no change needed:**

- **`SECRET_URLS`** sets the admin URL prefix: froide builds the admin route as
  `SECRET_URLS.get("admin", "admin")`, so a value moves `/admin/` somewhere
  unguessable and cuts automated login attempts. My earlier note that "AT exposes
  `/admin`" was wrong — `settings/production.py:276` already sets it from
  `DJANGO_SECRET_URL_ADMIN`. Only base/dev uses the literal `admin`, which is
  correct. DE's base `{}` and AT's `{"admin": "admin"}` are functionally the same
  value.
- **`CMS_RAW_ID_USERS`** is a threshold, not a flag: django-cms uses a raw-ID
  input instead of a user dropdown in the *page permission* admin once
  `User.objects.count()` exceeds it (`cms/admin/permissionadmin.py`). AT's `50`
  keeps the friendlier dropdown until there are 50 users; DE's `True` compares
  against `1`, so DE is effectively always raw-ID. Purely an admin-widget nicety
  that avoids rendering a `<select>` of every user, and only applies when
  `CMS_PERMISSION` is on. AT's value is the better default for a smaller install.

✅ **Checked and *not* a problem:** `VERSIONING_ALIAS_MODELS_ENABLED`. DE sets it
explicitly to `True`, AT omits it — but djangocms-alias defaults it to
`VersionableItem is not None`, i.e. enabled whenever djangocms-versioning is
installed, which it is. AT's alias content is versioned exactly as DE's. This one
looked alarming given D10 and turned out to be inherited behaviour.

The intentional divergences, for the record: `LANGUAGE_CODE`/`LANGUAGES`/
`PARLER_LANGUAGES`/`CMS_LANGUAGES` (single `de-at`, no fallback redirect),
`SITE_NAME`, `SENDER_DOMAINS`, `DEFAULT_FROM_EMAIL`, `SITE_EMAIL`,
`DONATION_PROJECTS` (`FOI` / Forum Informationsfreiheit),
`DONATION_SITE_NAME_OVERRIDE`, `PAYMENT_VARIANTS`, `ROOT_URLCONF`,
`ELASTICSEARCH_INDEX_PREFIX`, and `TEXT_ADDITIONAL_ATTRIBUTES` (AT allows
`iframe src`, which DE's set omits — see §9.5).

### 9.2 Nice to have: enabling `fds_ogimage`

The app is kept on purpose; the external rendering service does not exist yet.
Once it does, four things must change together — the last is easy to miss:

1. [ ] Set `FDS_OGIMAGE_URL` (env), in DE's shape:
   `https://<host>/api/{hash}?path={path}`.
2. [ ] Add `fragdenstaat_at.fds_ogimage.apps.FdsOgImageConfig` to `INSTALLED_APPS`.
3. [ ] Uncomment the `fds_ogimage.urls` include in `theme/urls.py` — the service
   fetches the pages it screenshots from these routes.
4. [ ] **Restore the two template overrides that were deleted.**
   `templates/account/profile.html` and `templates/foirequest/show.html` used to
   call `{% ogimage_url %}`, but with the tag commented out they emitted an empty
   `og:image` on every profile and request page, so the overrides were removed in
   favour of froide's `SITE_LOGO` default. Per-page images need them back.

### 9.3 One-off production steps

- [ ] **`manage.py migrate --fake fds_cms 0005`** (D9). Must **not** be run on a
  database that lacks those columns — check `information_schema` first.
- [ ] **Celery task rename** — the five `fragdenstaat_de.fds_donation.*` names. Drain
  and deploy per `docs/runbooks/celery-task-rename.md`; not a code edit.
- [ ] **Confirm `remind_unreceived_banktransfers` is in the beat config.** It is
  documented "run on the 15th" but nothing in the repo schedules it.
- [ ] **Attach the `FdsCmsPlainAPIApp` apphook to the help page** (after the DB
  migrations above). The machinery is fully ported —
  `fds_cms/cms_apps.py:FdsCmsPlainAPIApp`, `urls_plainapi.py`,
  `views.cms_plain_api` — but nothing serves `/hilfe/plain/<slug>/` until the
  apphook is attached to the `/hilfe/` page in the CMS (Advanced settings →
  Application). Three `content_urls` keys depend on it:
  `help_postupload_redaction`, `help_attachments_management`,
  `help_request_public`.

  ⚠️ **The current production deployment does not allow attaching apphooks**, so
  this step is blocked there. Until it is unblocked, point those three keys at the
  **non-`/plain/`** URLs of the same pages, which already exist and render (with
  full chrome instead of bare):
  `/hilfe/fragen-antworten/schwarzungen-durchfuhren/`,
  `/hilfe/fragen-antworten/anhange-verwalten/`,
  `/hilfe/fragen-antworten/anfrage-nicht-offentlich-stellen/`. Switch back to
  `/plain/` once the apphook can be attached.
- [ ] **Check "hide contact" on the two production donation forms.** D3's
  intent is no newsletter opt-in on any donation form. The form drops the
  `contact` field only when `hide_contact` is set. Two surfaces:

  - **`/spenden/`** (`DonationView` → `DonationFormFactory`, no CMS plugin):
    `DonationSettingsForm.hide_contact` defaults `initial=True`, so the opt-in
    should already be gone. Confirm on the live page -- a campaign
    `?pk_campaign=`/`?pk_keyword=` preset could override it.
  - **`/`** (homepage `DonationFormCMSPlugin`): driven by the plugin row's own
    `hide_contact`, and the **model field defaults `False`**, so whatever was
    saved on that plugin in the production CMS wins. After the migrations, edit
    the plugin and tick "hide contact" (or data-update `DonationFormCMSPlugin`).
    Do the same for any other page carrying a donation-form plugin.

  Or land the unconditional fix in `DonationFormCMSPlugin.get_form_settings()`
  before deploy and the CMS step goes away.
- [x] **Set `reverse_id` on the CMS pages the templates link to.** **Five**
  `{% page_url %}` string literals appear in AT's templates (the earlier count
  of four missed `help`), and all five resolve to nothing today, because the
  imported content has **10 pages and 0 reverse_ids**.

  They are not equally bad — two were written with a fallback:

  | reverse_id | used by | on miss |
  |---|---|---|
  | `help` | `cms/help_base.html:19` — "Topics" | **dead link** |
  | `help:donations` | `fds_donation/donor_detail.html:38` — "Häufige Fragen & Kontakt" | **dead link** |
  | `donate` | `fds_donation/donation_failed.html:13` — "Try again" button | **dead link** |
  | `home` | `header.html:16`, `cms/breadcrumbs.html:5` | falls back, `\|default:'/'` |
  | `beginnersguide` | `header.html:99` | link hidden, wrapped in `{% if %}` |

  `page_url` fails silently by design: with the `as` form it returns `""` rather
  than raising, regardless of `DEBUG`
  (`cms/templatetags/cms_tags.py`, `PageUrl.get_value_for_context` swallows
  `Page.DoesNotExist` and `NoReverseMatch`). So the three unguarded ones render
  `<a href="">` — a link that looks live and silently reloads the current page.
  Note the tag is registered under **two** names, `page_url` and `page_id_url`.

  A string argument is looked up as `reverse_id`; the tag also accepts a page
  **pk**, a **dict** of filter kwargs, or a `Page` object (`cms/pub_base.html`
  passes one, which is why it cannot be checked statically).

  **Done.** All five are set in the CMS and captured in a regenerated
  `tests/fixtures/cms.json` (`home`, `donate`, `help`, `beginnersguide`,
  `help:donations`). `scripts/verify_render.py` will *not* catch a regression —
  an empty href still returns 200. Guarded instead by
  `tests/test_at_identity.py`:

  - `test_page_url_ids_are_all_accounted_for` runs green now. It scans the
    templates and fails if a new `page_url` literal appears that the file does
    not classify as guarded-or-required, or if a classified id loses its last
    reference. That is precisely how the three unguarded links got in.
  - `PageUrlResolutionTest` asserts each unguarded id resolves. It was
    `xfail(strict=True)` while the content had no `reverse_id`s; the regenerated
    fixture turned it into an XPASS, which failed the suite and got the marker
    removed — the ratchet worked as intended. It now guards against the ids
    being removed or renamed. **[H]**

  **Regenerating the fixture needs `manage.py export_fdscms`, not `dumpdata`.**
  `dumpdata` cannot emit a loadable CMS fixture on django-cms 5: under
  `--natural-foreign` it orders via `serializers.sort_dependencies`, which sorts
  by *natural key* dependencies rather than the FK graph. `cms.Page` has no
  natural key, so it is written **last** — after `cms.PageContent`, which
  references it — and `cms/signals/pagecontent.py` dereferences `instance.page`
  in a `post_save` handler, so `loaddata` fails with `Page.DoesNotExist` before
  any test runs. Verified: Django's own `sort_dependencies` returns
  `cms.placeholder` first and `cms.page` last for these apps. `export_fdscms`
  was rewritten to dump and then re-sort by the real FK graph; its previous app
  list was stale (`djangocms_text_ckeditor`, `djangocms_picture`,
  `djangocms_video`) and missing alias, versioning and frontend.
- [ ] **Confirm the six `content_urls` target pages exist.** The settings half is
  **done** — `514038b` (2026-08-23) filled in all six keys, so `base.py` now sets
  all ten `content_urls` froide references and `get_content_url()`
  (`CONTENT_URLS.get(name, "/")`) no longer falls back to the homepage for any of
  them. What is left is content: each points at an AT help page that must actually
  exist.

  | key | now points at | target page in `cms.json` | rendered from |
  |---|---|---|---|
  | `pseudonym` | `/hilfe/fragen-antworten/pseudonyme-nutzung/` | ✅ `hilfe/fragen-antworten/pseudonyme-nutzung` | `account/forms.py` |
  | `throttled` | `/hilfe/fragen-antworten/anfragenanzahl/` | ✅ `hilfe/fragen-antworten/anfragenanzahl` | `foirequest/utils.py` |
  | `help_request_public` | `/hilfe/plain/fragen-antworten/anfrage-nicht-offentlich-stellen/` | ✅ page exists; `/plain/` route | `foirequest/views/make_request.py` |
  | `help_attachments_management` | `/hilfe/plain/fragen-antworten/anhange-verwalten/` | ✅ page exists; `/plain/` route | `foirequest/views/message.py` |
  | `help_postupload_redaction` | `/hilfe/plain/fragen-antworten/schwarzungen-durchfuhren/` | ✅ page exists; `/plain/` route | `foirequest/views/message.py` |
  | `help_request_privacy` | `/hilfe/datenschutz-und-privatsphare/` | ❌ **no such page** — DE's path, AT has `hilfe/privatsphaere` | `foirequest/views/make_request.py` |

  All six render from froide, in the request flow and account forms —
  user-facing, not admin. `throttled` and `pseudonym` fire exactly when a user is
  already confused, so a 404 there is worse than most. State against a fresh
  `tests/fixtures/cms.json` (production extract):

  - **Two are clean:** `pseudonym`, `throttled` — target pages exist.
  - **Three depend on the `/hilfe/plain/…` route.** The pages exist under
    `hilfe/fragen-antworten/`, but the value prepends `/plain/`, `fds_cms`'s
    chrome-less help render (for iframes), served by `FdsCmsPlainAPIApp`. That
    route only works once the apphook is attached to `/hilfe/` — the extract has
    `application_urls: ""` on every page, and **the current production deployment
    does not allow attaching apphooks** (see the "Attach the `FdsCmsPlainAPIApp`
    apphook" step above). Interim: point the three keys at the non-`/plain/` URLs
    of the same pages.
  - **One is a bug:** `help_request_privacy` points at `/hilfe/datenschutz-und-privatsphare/`,
    DE's slug, copied unchanged in `514038b`. AT's tree has `hilfe/privatsphaere`.
    Fix the setting to `/hilfe/privatsphaere/` (or whatever the real AT page is).

  No test covers any of the six — `test_footer.py` only checks
  `terms`/`privacy`/`about`/`help`. Add a `PageUrlResolutionTest`-style check for
  `content_urls`, and settle the apphook question. `page_url` and `content_urls`
  are the only two such indirections: neither froide nor froide-payment uses
  `{% page_url %}` at all. **[H]**
- [ ] **Decide whether the proof-of-identity widget should be law-specific.**
  Today it is not gated at all: `MakeRequestView.get_proof_form()` returns a
  form for every authenticated user, on every request, regardless of law or
  public body — the only condition is `is_authenticated`. The view does not even
  resolve a law at that point.

  The data model already anticipates the gate but nothing uses it.
  `FoiLaw.requires_signature` exists and is exposed through the publicbody
  serializer and the generated API types, so the frontend can see it per law —
  but the only references in froide are the model field, the serializer and two
  generated type files. No view, form or template reads it.

  Two ways to wire it, with different reach:

  - **Server-side, AT-only.** Override `get_proof_form()` to return `None`
    unless the law has `requires_signature`. Small and contained, but the law is
    chosen client-side in the Vue flow *after* the page renders, so this only
    works where a single public body is preselected — not the search flow.
  - **Client-side, upstream.** Show or hide the proof section reactively as the
    selected law changes, keyed on `requires_signature`, which the API already
    returns. Correct for every flow, but it is a froide frontend change and so
    needs upstreaming or a fork (D5).

  Either way the laws have to be marked first: `requires_signature` defaults to
  `False` and nothing sets it, so gating on it today would hide the widget for
  every AT law. Which laws genuinely require identity proof is a question about
  the IFG, not about the code. **[H]**
- [ ] **Run the Stripe tests once against real test keys.** They are deselected by
  default (`-m "not stripe"`) because they need Stripe test keys *and* a webhook
  tunnel. The Stripe CLI is now installed in the devcontainer
  (`.devcontainer/Dockerfile`), so the flow is: export the test keys, run
  `stripe listen --forward-to localhost:8000/payments/webhook/stripe/`, then
  `pytest -m stripe`. Nothing has ever exercised AT's Stripe path end to end —
  do this before trusting recurring card donations.
  (The Plan.slug overflow that broke the recurring flows is fixed — §9.8.)

### 9.4 Verification owed before trusting the deploy

- [x] **Rehearse the migrations against a real production dump.** Done.
  📖 **Procedure: `docs/runbooks/live-db-verification.md`** — ten ordered steps
  including the `fds_cms/0005` fake and how to check its precondition first, the
  full 54-migration sequence, and what to do if anything else wants faking.
  The dev extract is schema-faithful but not content-faithful — it collapses
  draft/public, so `fds_cms/0006` cannot be exercised against real divergence
  locally, and it holds no donation rows at all.
- [ ] **Measure production row counts** for `foirequest_*`, `account_user`,
  `fds_donation_*`, `froide_payment_*`. They set the migration window; the 10 CMS
  pages do not.
- [x] **Elasticsearch bumped 7.15 → 8.15.1.** ✅ Done, but note how: ES 8 refuses
  to start on a data directory written by anything older than 7.17 (7.17 → 8.x is
  the only supported direct upgrade), so the first attempt took dev search down
  until the `es-data` volume was discarded. Safe in dev, since the index rebuilds
  from Postgres.

  ⚠️ **Production is not dev.** The same jump there needs a real upgrade path —
  either 7.15 → 7.17 → 8.x with the data intact, or a full reindex from the
  database during a planned window. Do not discard a production data volume.
- [ ] **`RegularDonorsProgressBarPlugin` and the bank importer have no test cover** and
  were both changed. The plugin query was hand-checked against an extract whose
  donation tables are empty — that proves the SQL valid, not the arithmetic.

### 9.5 Known live defects — fix with the deploy, none are blockers

- [ ] **The footer alias hardcodes hash-stamped static URLs** (four sponsor logos).
  They are orphans from a deployment that used manifest storage; production no
  longer hashes. They resolve today, but `collectstatic --clear` or any edit to
  those source images breaks them.
- [ ] **`zwb.html` renders a blank PDF** and the donation receipt field is hidden.
  Leave hidden until P4 lands the Austrian FinanzOnline flow.
- [ ] **Attach the CMS search apphook to a page.** `FdsCmsSearchApp` is ported and
  registers, but an apphook does nothing until it is attached to a CMS page in
  the admin (DE attaches it to its help section). Until then CMS pages stay
  missing from site search.
- [ ] **`tests/test_misc.py::test_text_plugin_nbsp_span` is skipped as "is flaky",
  but it is actually stale.** It calls `page.placeholders`, a django-cms 3 API
  that CMS 5.1 removed — it would error, not flake. The regression it guards is
  AT-relevant: spans containing only `&nbsp;`, used for the non-selectable
  spacing in **IBANs**, which appear on the donation pages. Port it to the CMS 5
  placeholder API rather than un-skipping it. **[R]**
- [ ] **If mailing is ever enabled, a working unsubscribe route is legally required.**
  Three DE test modules are currently ignored for exactly this reason.

### 9.6 Nice to have (deferred): georegion loading

`theme/management/commands/update_georegion.py` and
`fds_cms/management/commands/load_georegion.py` are both German: they are built
around the **ARS** (Amtlicher Regionalschlüssel) hierarchy and hardcode its
2/3/5/9/12-digit key lengths. Austria's equivalent is the 5-digit
Gemeindekennziffer under a Bundesland/Bezirk/Gemeinde hierarchy.

Deliberately not touched: **georegions are not used by AT at present**, so both
commands are inert. They need rewriting — not adapting — before any feature that
depends on regional data (map plugins, region-scoped search, `LEAFLET_CONFIG`).
Until then they are harmless, and deleting them would throw away the shape of a
working loader.

### 9.7 Nice to have: filesystem caveat for macOS developers

This workspace is a **case-insensitive** bind mount, so `Inter-Italic-latin.woff2`
and `inter-italic-latin.woff2` are one path locally but two on CI and production
Linux. It already caused one near-miss: a font rename appeared to work locally
while leaving capitalised names in the tree that would have 404'd on deploy. When
changing only the case of a filename, verify with `git ls-tree`, not `ls`, and
rename through `git update-index` if `git mv` refuses.

### 9.8 Fixed: recurring donations 500'd on `Plan.slug`

**Resolved locally — no upstream dependency, no product change.** Recorded
because the failure mode is instructive and the workaround should be removed
once upstream moves.

Every recurring donation failed with
`DataError: value too long for type character varying(50)`. froide-payment
builds a Plan with `slug=slugify(plan_name)` into a bare `models.SlugField()` —
Django's default `max_length=50`, while the adjacent `name` allows 256. AT's
plan name, `"5 EUR Spende monatlich an Forum Informationsfreiheit"` (the site
name is `DONATION_SITE_NAME_OVERRIDE`, the legal recipient), slugifies to **52
characters**. DE's `"…an FragDenStaat"` gives **38**, which is why upstream has
never hit it — a textbook Germany-specific assumption.

Fixed by `fds_donation.listeners.truncate_plan_slug`, a `pre_save` receiver on
`Plan` wired up in `apps.py`. This sits at the model, so it covers all four
write sites at once (`provider/mixins.py` for bank transfer, `provider/paypal.py`
twice, `provider/stripe.py`) rather than one provider.

Truncating is safe, and was checked rather than assumed:

- `Plan.slug` is **written in four places and read in none**. The only other
  reference is the admin's `prepopulated_fields`, a JS convenience for manually
  created plans.
- The field is **not `unique`**, so a collision between two truncated slugs
  carries no meaning.
- `name` is untouched — it is the 256-char column donors and PayPal actually see.

The limit is read off the field (`sender._meta.get_field("slug").max_length`)
rather than hardcoded, so if froide-payment ever widens the column the listener
becomes a no-op instead of silently continuing to cut names short.

Regression test: `fds_donation/tests/test_plan_slug.py`, which asserts up front
that AT's name still overflows and tells you to delete both it and the listener
if that stops being true.

- [ ] **Optional, low priority:** upstream `SlugField(max_length=256)` + migration
  to `okfde/froide-payment`, so the next deployment with an organisation name
  longer than Germany's does not have to rediscover this. Not a blocker for AT.

### 9.9 The froide-payment fork is not in the dependency set

`fin/froide-payment@main` and `fin/2026-08-fdsat-deployed` are **identical**, so
production runs the fork — while `pyproject.toml` and `uv.lock` both declare
`okfde/froide-payment@main`. The switch therefore drops eight commits. Audited:

| commit | effect | still missing from okfde? | handled |
|---|---|---|---|
| `3b869ff`+`ef68ff9` | `Plan.slug` → `max_length=256` + migration `0018_alter_plan_slug` | **yes** | ✅ §9.8 listener |
| `9c24aed` | `get_stripe_locales` gains `"de-at"` | **yes** | ❌ see below |
| `134cc6f` | PayPal `application_context.locale` → `LANGUAGE_CODE.split("-")[0]` | **yes** | ❌ see below |
| `b303254` | pins `stripe.api_version = "2020-08-27"` | **yes** | ❌ see below |
| `e8d5c30` | `locale/de_AT/` catalog (2 strings) | **yes** | ✅ adoptable, see P6 |
| `eea1787`, `4d01a02` | README only | yes | n/a — no runtime effect |

**Migration-graph consequence: none. Measured, not assumed.** froide-payment is
a *shared upstream* app, unlike the site-specific `fds_*` apps — the fin fork
tracked okfde rather than diverging from it, so the production dump already has
**all twenty** okfde migrations applied, including `0018_order_remote_reference…`,
`0019` and `0020`. `showmigrations froide_payment` against the dump with the
okfde checkout reports every migration `[X]`; switching sources requires no
migration at all.

The only residue is one orphan row, `0018_alter_plan_slug`, recorded for a file
that exists solely on the fork. Django ignores applied rows with no corresponding
node — `check_consistent_history` only fires when a migration is applied *before*
its dependencies — so this is inert. Do not "clean it up" with `migrate --prune`
without thinking: the row is the only remaining trace of why the column is wide.

One asymmetry to be aware of: the dump's `froide_payment_plan.slug` column is
`varchar(256)` (fin's migration widened it) while okfde's model declares 50.
Harmless — the column is wider than the model, `makemigrations` compares model
state against *migration* state and so stays quiet, and the §9.8 listener
truncates to the model's limit. It does mean production slugs get cut to 50 in a
column that could hold 256, which matters not at all for a field nothing reads.

⚠️ This paragraph previously claimed three migrations would arrive unapplied.
That was wrong — checked against `fds_final` and corrected.

**Resolved by pinning the fork; upstreaming is what remains. [H]**

- [x] **Stripe locale** (`9c24aed`) and **PayPal locale** (`134cc6f`) — both are
  rebased onto current `okfde/main` as `fin/froide-payment@2026-08-de-sync`, and
  `pyproject.toml` pins it (lock records `f7d3120`). The PayPal one is not
  hypothetical: `application_context.locale` was sending `de-at`, which is not
  valid BCP-47 — the region subtag must be uppercase — so PayPal rejected every
  recurring subscription with "violates schema". `test_paypal_recurring` proves
  the fix. A third one-liner was added on the branch: the same locale bug in the
  subscription-*modify* flow, which upstream had introduced after the 2023 fork.
- [ ] **Upstream all three to `okfde/froide-payment` and repin to `@main`.** They
  are one-liners any non-German deployment needs. Until then AT depends on a
  personal fork, which is the D5 exit criterion.
- [x] **`stripe.api_version`.** `b303254` pins the API version to `2020-08-27` at
  import. This one should probably **not** be carried over verbatim — it is a
  2023-era pin against a since-upgraded Stripe library, and silently freezing the
  API version is exactly the kind of thing that misleads later. Decide
  deliberately: re-pin to a current version, or drop it and test. Trivially
  settable from AT's `apps.py` either way.

These are the strongest argument for the D5 exit being a small upstream PR to
`okfde/froide-payment` rather than an indefinite fork: all three are one-liners
that any non-German deployment needs.

### 9.10 Dependency sync before deploy

Production installs from `uv.lock`, not from what happens to be in a developer's
`.venv`. The lock moved a lot during this merge — pytest tooling, playwright,
the whole Elasticsearch client stack, and `django-payments` — so the deploy must
carry the lock, not just the source.

- [ ] **Deploy `uv.lock` and `pyproject.toml` together with the code, and install
  with `uv sync --locked` (or `--frozen`).** A plain `uv sync` may re-resolve and
  quietly hand production a different set than was tested. `--locked` fails
  instead, which is what you want on a deploy.
- [ ] **Rebuild the Elasticsearch image.** `deps/elasticsearch/Dockerfile` now
  pins 8.19.3 and pins the german-decompounder data to a commit. If production
  ES stays below 8.16, `no_sub_matches` is silently ignored and search quality
  degrades with no error — see §9.5 and the search section in §7.
- [ ] **Decide the outstanding version bumps** before deploying rather than
  after: `django` 5.2.6 → 5.2.15 (nine patch releases, where security fixes
  ship), `urllib3` 1.26.13 → 2.7.0 (a major behind, with advisories), and a
  review of `pandas` 3.0.3 against the bank-statement import. All three are
  detailed under "Library drift beyond the test tooling" in §7. **[R]**
- [x] **Check `django-payments` resolves to 3.x.** `[tool.uv]
  constraint-dependencies` pins `>=3.1,<4` deliberately (§7): 4.0.0 dropped
  `StripeProvider`, which `froide_payment/provider/stripe.py` imports at module
  level, so 4.x turns every payment page into an `ImportError` at startup. If a
  future lock refresh drops the constraint this regresses — loudly at boot
  rather than silently, but only once something imports the app.

**Developer trap: changing a vite entry needs a Django restart.**
`froide/helper/templatetags/frontendbuild.py` keeps a module-level
`FrontendBuildLoader()` and caches the manifest on first use, for the lifetime
of the Python process:

```python
def get_entry_point(self, name):
    if self.entry_points is None:
        self.entry_points = self.load_manifest()
```

So adding or repointing an entry in `vite.config.ts` — as
`makerequest` was, from froide's `makerequest.js` to AT's `makerequest.ts` —
has no effect on a `runserver` that was already up. It keeps emitting the old
source path, the new module never loads, and the page behaves exactly as it did
before with nothing in the console to suggest why. Rebuilding does not help;
only a restart does.

Editing the *contents* of an already-mapped entry needs no restart, because the
vite dev server serves that live. That asymmetry is what makes this confusing:
every other frontend edit appears immediately.

Cost this once: the fax notice looked broken in the multi-request flow, and the
JS, the bundle, the dev server and the manifest on disk were all correct.

---

**Developer trap, not a deploy step — now guarded.** `uv sync` replaces the
editable sibling checkouts (`froide`, `froide-payment`, `froide-fax`,
`django-filingcabinet`) with the git pins from `pyproject.toml`, because that is
what the manifest declares. The frontend has the exact same trap: a bare
`pnpm install` replaces the `pnpm link --global` sibling links (`froide`,
`froide_payment`, `@okfde/filingcabinet`) with the `github:` pins from
`package.json`, after which `pnpm run build` compiles the pinned revision. Both
are correct for production, which has no siblings and builds from the lockfiles.
In the devcontainer they mean you silently start testing / building the pinned
revision instead of your own checkout.

Re-apply both link sets with:

```
./scripts/sync-editables.sh            # Python + frontend; idempotent; --check reports only, exit 1 if stale
```

Keeping `package.json`'s fork ref *in step with* `pyproject.toml`'s is a
separate, committed-config concern (dev is immune, only CI/prod build from the
pins): `scripts/check_fork_pins.py`, wired into `.pre-commit-config.yaml` so it
runs in the lint job. `tests/test_fork_pins.py` covers the parser.

`fragdenstaat_at.theme.checks` (`fragdenstaat_at.E001`) now makes this loud:
`manage.py check` — and therefore `runserver`, `migrate` and the test suite —
**refuses to start** when a sibling checkout exists on disk but the package
resolves somewhere else. It names only the affected packages and points at the
script. The check scopes itself by the presence of the sibling directory, so it
is a silent no-op in production.

**There is no uv setting that avoids the trap**, which is why this is a guard
rather than a fix. Tested against uv 0.12.5:

- `[tool.uv.sources]` with `path = "../froide", editable = true` does work for
  dev, but it needs bare-name `override-dependencies` to defeat froide's own
  transitive git pin on `django-filingcabinet`, and it rewrites `uv.lock` to
  `source = { editable = "../froide" }` — production can then no longer install
  from that lock at all.
- The two cannot coexist in one lockfile. `uv.lock` holds a single source per
  package, and `--locked` asserts the lock matches what `pyproject.toml`
  currently means, so `uv sync --locked` fails outright: *"The lockfile at
  `uv.lock` needs to be updated, but `--locked` was provided."*
- `uv.toml` cannot carry `sources` (uv rejects it: *"`sources` is only
  applicable in the context of a project"*), so there is no gitignored local
  override either.
- Extra-conditional sources (`{ path = ..., extra = "localforks" }`) are
  accepted by uv but had no effect here — both plain sync and
  `--extra localforks` still installed from git.
- **Do not reach for `uv lock --no-sources` as an escape hatch.** Combined with
  the bare-name overrides above it strips the git URLs too, and resolves
  `froide` from **PyPI** — an unrelated package of the same name — with no
  error. Verified: the lock came back with
  `source = { registry = "https://pypi.org/simple" }`.

### 9.11 Nice to have: housekeeping

- The working branch `sync/de-head-2026-08` is **not pushed**. `main` is safe on
  origin; this branch exists only in the dev container.

---

### 9.15 QR code on outgoing fax letters

Built; see `docs/qr-code-on-faxes.md`. Encodes `mailto:<secret_address>` bare —
no `?subject=`/`?body=`, which would balloon the payload. Lives entirely in
`fragdenstaat_at.theme`; **froide-fax has a zero-line diff**, which matters
because that repo is MIT and headed upstream to okfde.

The same override also fixes froide-fax's hardcoded `Via: Fax and email`, which
is wrong when the fax *replaces* the email (`FaxOverride`) and promises a mail
that never arrives. Keys on `object.kind`, not `object.original`:
`send_fax_message` renders `fax_message.original or fax_message`, so `original`
is `None` in both modes.

- [x] Renders in both modes, WeasyPrint keeps the SVG vector, and the QR decodes
      out of the generated PDF.
- [x] Simulated Group 3: decodes at 204x98 **and** 204x196, greyscale and 1-bit.
      Models detail loss only — no halftoning, skew or photocopy noise.
- [ ] **Send one real fax and scan the received page.** The only test that
      counts, per the doc. Faxbeep answers free. Until then this is unproven on
      the path it exists for. **[H]**
- [ ] Decide whether it goes on Mode A faxes at all — there an email already
      carries the reply address, so it buys much less.
- [ ] Measure it. The doc is explicit that this is an experiment: an office that
      refuses email may not scan QR codes either.

---

### 9.14 GitHub Actions is dead scaffolding

`.github/workflows/ci.yml` is untouched from the 2023 fork. The repo modernised
around it — uv, pnpm, ruff, Python 3.13, Elasticsearch 8, django-cms 5 — and the
workflow still describes the old world. It cannot pass in its current form:

| step | why it fails |
|---|---|
| `pip-sync requirements-dev.txt` | the file does not exist; deleted in the uv migration |
| `python-version: '3.10'` | `requires-python = ">=3.12"`, so resolution fails regardless |
| `flake8` / `black==22.12.0` / `isort` | none are configured or installed; the repo lints with **ruff** |
| `yarn install` / `node-version: 16` | the repo is on **pnpm 9.15**; `yarn.lock` is a stale leftover |
| `elasticsearch:7.5.1` | `no_sub_matches` needs **≥ 8.16**; dev runs 8.19.3 |
| `postgis:12-3.0` | `compose-dev.yaml` uses `postgis:16-3.4` |
| `actions/checkout@v1`, `setup-python@v1`, `cache@v1` | Node 16 actions, no longer runnable on current runners |

`make testci` itself is fine (`coverage run -m pytest --reuse-db`), and
`pytest.ini` is correct — the failure is entirely in the workflow's environment
setup.

**Not verified:** whether Actions is enabled on the repo at all, or how long it
has been red. There is no `gh` CLI in the devcontainer to check run history.

**Differences from DE, and whether each is still justified:**

| | DE | AT | keep? |
|---|---|---|---|
| install | `uv sync --locked` | `pip-tools` | **no** — port DE's |
| python | 3.12 / 3.13 / 3.14 matrix | 3.10 | **no** |
| lint | `prek-action` | flake8 + black + isort | **no** — but see below |
| node | pnpm, node 24 | yarn, node 16 | **no** |
| services | `docker compose -f compose-dev.yaml up --wait` | inline `services:` | **no** — AT has the compose file |
| DB cache | restore a cached dump | none | optional; DE-specific speedup |
| translations | `translations.yml`, `translations-pr.yml` | none | **deferred** — translation work is last (P6) |
| `de-drift` job | none | yes, `continue-on-error` | **yes** — AT-only and legitimate |
| pytest config | `[tool.pytest]` in pyproject | `pytest.ini` | **AT is correct**; see below |
| compilemessages | `-i node_modules -l de` | all locales | **AT is correct** — it must compile `de_AT` |

Two places AT is *ahead* of DE and must not be "aligned" backwards:

- **`pytest.ini`.** DE declares markers and addopts under `[tool.pytest]` in
  `pyproject.toml`, which pytest does not read (it wants
  `[tool.pytest.ini_options]`), so upstream they have no effect and DE's CI
  passes `-n auto` on the command line instead. AT's `pytest.ini` works.
- **`compilemessages`.** DE compiles `-l de` only. AT needs `de_AT` compiled or
  the Austrian overrides never load.

**Before adopting `prek-action`:** AT's `.pre-commit-config.yaml` has the ruff
hooks **commented out**, so prek currently runs eslint and nothing else. That is
why local commits report only `eslint ... Skipped`. Uncomment them, or CI
lints nothing.

- [x] **Ported DE's `ci.yml`**, keeping the `de-drift` job, `pytest.ini` and the
      full-locale `compilemessages`. Now: `uv sync --locked`, pnpm + node 24,
      `docker compose -f compose-dev.yaml up --wait`, `prek-action`, and
      `actions/*@v6`. Python is **3.13 only** — dev and production both run it;
      DE's 3.12/3.14 entries can be added once this is reliably green.
- [x] **Enabled the ruff hooks** (`ruff-check`, `ruff-format`, pinned to v0.16.3
      to match the dev group). They had been commented out, so prek ran eslint
      and nothing else. Three settings files needed reformatting.
- [x] **Deleted `yarn.lock`** and **`.eslintrc.js`**. The latter was a dead
      legacy config (`module.exports = require('froide/.eslintrc')`) shadowed by
      `eslint.config.mjs`, and it was the *only* eslint failure on the tree:
      flat-config eslint lints it and rejects the `require()`. DE deleted it
      long ago and has the identical `eslint.config.mjs`.
- [x] **Added `[tool.coverage]`** to `pyproject.toml`, mirroring DE's. Without
      it `pytest --cov` would measure `.venv` too. Reports 43% over 18204
      statements.

- [x] **Made `de-drift` mean something.** The job does work — both repos are
      checked out side by side under `$GITHUB_WORKSPACE`, so
      `../fragdenstaat_de` resolves, and `de_drift.py` is stdlib-only and
      compares working trees, so it needs no install and does not care that
      checkout is shallow. But it was **permanently tripped and invisible**:
      the gate was 140 while the real count is 142, so it failed on every run,
      and `continue-on-error` meant that could never surface. The limit is now a
      ratchet at the true 142, and the table is written to
      `$GITHUB_STEP_SUMMARY` — otherwise the numbers stay buried in a log
      nobody opens, which is the sense in which the job really was doing
      nothing.

Verified locally rather than by pushing: `prek run --all-files` passes all three
hooks, `pytest -n auto --cov --cov-report=` gives 269 passed / 1 skipped,
`coverage report --format=markdown` renders, and `de_drift.py` exits 0 at the
new limit — checked both in place and in a CI-shaped directory layout. The
workflow itself has **not** run on GitHub yet — the branch is still unpushed
(§9.11).

---

### 9.13 froide-fax is now in the dependency set

Pinned to **`fin/froide-fax@main`** (`7b74f80c`), which carries webhook
hardening (replay and malformed-envelope rejection), classification of
permanently-undeliverable faxes so they stop being retried, per-recipient
fax/email routing on replies (`handle_foirequest_outgoing_messages` keyed on
`recipient_email`), an optional email carbon copy of faxed messages
(`FaxOverride.email_copy`, migration `0005`), Telnyx's OpenAPI examples as
fixtures, `README_LIVE_TESTS.md`, and `FAX_BACKEND` (§9.15). AT is running
**ahead of okfde here**, so unlike the froide-payment pin (§9.9) there is no
"repin to upstream" exit criterion yet — upstream would have to catch up first.

It was briefly pinned to `docs/live-tests`; that branch and `main` were the same
commit, and `main` is the one that moves, so the pin follows `main`.

Wired into five places, all committed:

| where | change |
|---|---|
| `pyproject.toml` | `froide-fax @ git+…@main` |
| `uv.lock` | `froide-fax 0.0.1 (7b74f80c)`, plus `pynacl`, `pytz` |
| `settings/base.py` | `froide_fax.apps.FroideFaxConfig` uncommented |
| `theme/urls.py` | `path("fax/", include("froide_fax.urls"))`, DE's mount point |
| `devsetup.sh` | `froide-fax` added to `REPOS` |

Python-only, so it is deliberately **not** in `FRONTEND`/`FRONTEND_DIR` — same
as DE. It is also covered by the editable-fork guard (§9.10,
`fragdenstaat_at.E001`) and by `scripts/sync-editables.sh`.

`uv lock` added only `froide-fax`, `pynacl` and `pytz`; no existing pin moved.

**Still owed before fax actually sends anything:**

- [ ] **Set the four `TELNYX_*` env vars in production.** `settings/base.py`
      already reads `TELNYX_API_KEY`, `TELNYX_APP_ID`, `TELNYX_PUBLIC_KEY` and
      `TELNYX_FROM_NUMBER`, each defaulting to `""` — so the app loads and the
      URLs resolve with no credentials, and fails only when a fax is sent.
- [x] **Fax message handler enabled.** `base.py:784` sets
      `"fax": "froide_fax.fax.FaxMessageHandler"` in
      `FROIDE_CONFIG["message_handlers"]`, matching DE. (Turning it on changes how
      messages reach public bodies and costs money per fax in production — but the
      cost gate is the `TELNYX_*` env vars above, not the handler registration.)
- [x] **froide-fax ↔ froide fork method-name drift — fixed in the working tree,
      needs upstreaming.** The `FaxOverride` ("fax instead of email") path only
      works if froide's `get_request_outgoing_message_kind()` (fork commit
      `7520e6a2b`) can call the handler's hook. The fork calls
      `handle_foirequest_outgoing_messages`; froide-fax `main` defined
      `handle_request_outgoing_messages` — a name that was never invoked, so an
      overridden request silently went out by **email** with no fax and no PDF.
      froide-fax's own `test_fax_override.py` called the method directly and
      passed, hiding it. Renamed in `../froide-fax/froide_fax/fax.py` + tests,
      with two integration tests asserting `get_request_outgoing_message_kind()`
      returns `MessageKind.FAX`.
- [x] **`fax_media_url` fed `requests.get()` a relative URL — fixed in the
      working tree, needs upstreaming.** Surfaced once the routing fix above let
      a fax actually render: opening the console backend's printed `PDF:` link
      500'd with `MissingSchema`. `get_absolute_domain_file_url()` only prepends
      MEDIA_URL's *domain part*, which is empty under the dev default
      `MEDIA_URL = "/files/"`, so the view proxied `/files/foi/6/fax.pdf?token=…`
      through `requests.get()` with no scheme. Absolute in production only
      because `MEDIA_URL` there carries a host. Fixed in
      `../froide-fax/froide_fax/views.py` with `urljoin(settings.SITE_URL, url)`;
      regression test in `test_fax_numbers.py`.
- [ ] **Upstream both froide-fax fixes.** Commit the method rename and the
      `fax_media_url` scheme fix to `fin/froide-fax@main` (AT's pin) and re-lock
      `uv.lock`.
- [x] **Fax transports** — froide-fax now has `FAX_BACKEND`, mirroring
      `EMAIL_BACKEND`, with console and dummy backends that run the whole path
      (fax message, rendered `fax.pdf`, delivery status) without a Telnyx
      account or a network call. AT's `settings/development.py` uses the
      console backend, since dev has no credentials and a real send would fail
      *after* the message and PDF had been created.
- [x] **Fax log normalised** — the polling sweep stored Telnyx's REST object
      verbatim (`from`, `id`, `page_count`), while `report.html` reads `from_`,
      `sid`, `num_pages`. A fax resolved by poll rather than callback rendered a
      report with blank sender, recipient, pages and date; nothing raised,
      because Django resolves a missing key to `''`. Both paths now share one
      builder.
- [x] **Fax numbers in national format** — `FAX_NUMBER_REGION = "AT"` is now set
      in `settings/base.py`. froide_fax resolved the region from
      `LANGUAGE_CODE` by taking the **first** subtag, so `de-at` gave **DE** and
      every Austrian number in national format (`01 4000 81510`,
      `0316 872-2571`) was parsed as German, found invalid and rejected — the
      "This is not a usable fax number." seen in the FaxOverride admin. Fixed
      upstream in the fork (a language tag is language-first; the region is the
      *second* subtag) and pinned explicitly here as well.

- [x] **"This request will be sent by fax" notice on `/anfrage-stellen/`.**
      A `FaxOverride` diverts a request away from email entirely, which the
      request form said nothing about. Lives in AT only, overriding froide's
      `foirequest/request.html` through the `before_form` block; froide and
      froide-fax are untouched.

      Two halves, because the page mixes server rendering with a Vue chooser.
      Initial visibility is decided server-side, so a body chosen before load is
      covered even if the script never runs. `frontend/javascript/makerequest.ts`
      then follows the selection by watching froide's Vuex store — a module
      singleton the bundler shares, so no DOM archaeology. An earlier version
      read `input[name="publicbody"]` and was wrong: the selection is a *hidden*
      input once committed, never `:checked`, and the swap happens in a Vue
      re-render that fires no event. Covered by browser tests.

      The wording is composed client-side, since it depends on how many bodies
      are selected and how many of those are diverted. Variants are passed as
      data attributes so gettext still sees them. Open: the strings have **no
      German translation yet** (P6), and the "more about delivery" link points
      at the generic `help` page as a placeholder — §9.3 for setting a proper
      `reverse_id`.

      The **multi-request flow is now covered too**, both by "select all" and by
      ticking bodies one at a time, including the `{count} of {total}` wording.
      Reaching it needs a logged-in user with `foirequest.create_batch` (or a
      superuser), which is why it was missed at first. That flow is also the
      clearest evidence for using the store: its checkboxes render with an
      **empty `name` attribute**, so `input[name="publicbody"]` matches nothing
      there and the original DOM-based implementation could never have worked in
      it.

      **`build/` is gitignored**, so a checkout that has not run
      `pnpm run build` still serves the previous bundle — the notice then
      behaves like the version that shipped with that build, not the one in the
      source tree.

- [ ] **froide's own `validate_fax` has the same class of bug, and is not
      fixable from here.** `froide/publicbody/validators.py:99` passes
      `settings.LANGUAGE_CODE.upper()` straight to `phonenumbers.parse` as the
      region, so an AT site passes **`"DE-AT"`**, which is not a region code at
      all. Every national-format fax number is then unparseable — *including
      German ones*:

      ```
      validate_fax('01 4000 81510')  -> ValidationError: Fax number cannot be parsed
      validate_fax('0316 872-2571')  -> ValidationError: Fax number cannot be parsed
      validate_fax('030 12345678')   -> ValidationError: Fax number cannot be parsed
      validate_fax('+43 1 4000 81510') -> OK
      ```

      This governs `PublicBody.fax`, so any fax number typed into the public
      body admin must be in international format or it is refused. DE never
      sees it: `LANGUAGE_CODE = "de"` uppercases to a valid `"DE"` by
      coincidence. Worth an upstream patch — `parse(fax, get_fax_region())` —
      but AT is pinned to `okfde/froide@main`, so it needs either a froide PR
      or a fork. **[H]**

- [ ] **Run the live Telnyx test once** (`README_LIVE_TESTS.md` on the branch,
      ~20 min and one fax). It closes the one gap no offline test covers: every
      signature test generates its own keypair, so they prove nacl agrees with
      nacl, not that we interoperate with Telnyx's signing.

**Optional, later: a transport-neutral delivery hook in froide.**
`froide_fax.status.apply_fax_status` reimplements the tail of
`froide.foirequest.signals.save_delivery_status` — `DeliveryStatus`
update-or-create, requester confirmation, deduped `BOUNCE_PUBLICBODY`
ProblemReport — because that receiver is welded to the email transport at every
step: it fires only on `email_left_queue` (postfix log parsing), guards on a
`<foimsg.…>` Message-ID, does its own `email_message_id` lookup, takes a
pre-mapped status and a `"".join(log)` string, reports on the first failure with
no retry, and `send_foimessage_sent_confirmation` early-returns for a non-email
message (hence the copy in `froide_fax/delivery.py`).

Split it: extract `record_delivery_outcome(message, status, log="",
failure_reason=None)` in froide (does the update-or-create + confirmation +
report), leave `save_delivery_status` as a thin `email_left_queue` adapter that
looks the message up and calls it, and make the confirmation transport-neutral
(drop the `is_email` guard, keep the `original is not None` one). Then
`apply_fax_status` keeps only the Telnyx status mapping and the retry /
permanent-failure decision and calls `record_delivery_outcome` directly — no
signal — which lets `froide_fax/status.py`'s duplicated tail and
`froide_fax/delivery.py` go away. Spans both forks (froide + froide-fax); AT
owns both, so it is a real but bounded refactor. **[H]**

---

### 9.12 Finding Germany-specific strings that no catalog can reach

`manage_at_translations.py` ends with a scan of AT's own templates and code for
hardcoded German identity. This is deliberately separate from the translation
work: a hardcoded IBAN is not a msgid, so no `de_AT` override can ever fix it —
the source has to change.

```bash
python manage_at_translations.py --dry-run     # scan runs at the end
python manage_at_translations.py --no-hardcoded-check   # skip it
```

It looks for German domains (`fragdenstaat.de`, `okfn.de`), the German legal
entity, German IBANs and BICs, GLS Bank, Deutsche Post's *gelber Brief*,
*Zuwendungsbestätigung*, and bank codes in both the spaced display form
(`430 609 67`) and bare (`43060967`).

This is how `banktransfer_instructions.html` was found still holding Open
Knowledge Foundation Deutschland's account holder, IBAN, BIC, Bankleitzahl and
SEPA QR code on an Austrian donation page. That file is now clean.

Current state: **17 hits across 7 files**, of which

- `fds_mailing/templates/email/{default,formal}/base.html` — the blocker in §9.0.
- `fds_donation/templates/fds_donation/pdf/zwb.html` — moot while the ZWB export
  stays behind the §9.8 kill switch, and superseded by the P4 decision.
- `templates/footer.html` — **intentional**, the OKF Deutschland *supporter*
  credit. Leave it.
- One known false positive: `settings/production.py:34`, an 8-digit byte limit
  caught by the bare-BLZ pattern. Kept, because the alternative is missing a
  wrong bank code.

