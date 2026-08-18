# fragdenstaat_at ↔ fragdenstaat_de — sync & merge plan

Written 2026-08-17. Decisions **D1–D9 taken 2026-08-18** (§0).
Analysis only — no application code was changed to produce this.

Compares:

| | ref | date |
|---|---|---|
| **AT** | `fragdenstaat_at` @ `b047758` (main) | 2026-08-17 |
| **DE@hash** | `fragdenstaat_de` @ `abe0781d` — the stated sync baseline | 2023-01-19 |
| **DE@HEAD** | `fragdenstaat_de` @ `938901ef` (main) | 2026-08-17 |

`abe0781d..HEAD` is **2194 commits over 3 years 7 months**.

---

## 0. Decisions — **taken 2026-08-18**

All nine are settled. Rationale for each is in §0b; consequences are folded into
the plan in §5. Where a choice differs from the draft recommendation, the reason
is recorded.

| # | Decision | Choice |
|---|---|---|
| **D1** | Merge direction | **Rebase AT onto DE@HEAD.** Take DE HEAD wholesale, re-apply AT's delta as a branding/config layer. |
| **D2** | Delta style | **Configure-out locally, no upstreaming.** Settings/template-driven deltas; the three otherwise-upstreamable items stay local patches. |
| **D3** | Dropped apps | **Newsletter + mailing back, no signup at all.** Installed for the FK and `MailingMessage`; `hide_contact=True` on every donation form. `fds_blog` and `fds_fximport` stay out. |
| **D4** | Language | **Keep `de-at`; move overrides into `fragdenstaat_at/locale/de_AT/`.** |
| **D5** | froide fork | **No permanent fork.** Stay on `fin/froide` *for now*, solely to prove the `de_AT` catalogue can move wholly into `fragdenstaat_at`; repin to `okfde/froide@main` once proven. |
| **D6** | Dependencies | **Adopt DE's curated `pyproject.toml` + `[dependency-groups]`,** minus apps AT will not run. |
| **D7** | Tests | **Adopt DE's pytest + Playwright harness *before* the code sync.** |
| **D8** | Migration lineage | **Keep AT's graphs; forward-port DE's models** as AT `0006, 0007…` for both `fds_cms` and `fds_donation`. |
| **D10** | Static placeholders | ⚠️ **OPEN — blocks lifting the `django-cms<5.1` pin.** Migrate to djangocms-alias (recommended, during P3) or stay on cms 5.0.x. |
| **D9** | `fds_cms/0005` | **Keep `0005`; `--fake` it on production.** Fresh and post-June-2026 dev DBs run it for real. ✅ **Verified end-to-end — §1b.** |

### What these choices commit you to

- **D3 + D2 together produce one concrete action item.** `hide_contact=True`
  suppresses the donation form's `contact` field, but it is **not sufficient on its
  own**. `services.py:398` in `confirm_donor_email()` does
  `if "newsletter" in request.GET: donor.contact_allowed = True` — so any
  confirmation link carrying `?newsletter` subscribes the donor regardless. There
  are exactly **two** subscribe call sites (`services.py:210-212` and `:402-412`),
  both gated on `contact_allowed`, and exactly **one** bypass. Neutralising lines
  398–400 closes it completely. Do this in the same change that installs the apps.
- **D2 (no upstreaming) means three permanent local patches**, carried forward on
  every sync: `DONATION_SITE_NAME_OVERRIDE` in `fds_donation/forms.py`;
  `MIN_AMOUNT` as a module constant in `form_settings.py` (AT needs 2, DE has 5);
  and the bank-statement column mapping in `external.py` (Erste/George vs DE's
  format). Budget a little re-application time in each future sync.
- **D5 is time-boxed by design.** The fork is a test bed, not a position. Its exit
  criterion is: `fragdenstaat_at/locale/de_AT/` fully replaces
  `froide/locale/de_AT/` (590 msgids, 505 translated) with no regression. Until
  that is proven, P2 runs against a moving base — accept it, but do not let the
  fork acquire unrelated changes. `froide/settings.py` already carries
  uncommitted devcontainer edits that must not be committed with it.
- **D7 before the code sync** front-loads roughly a week that produces no visible
  merge progress. That is the point: P2 and P3 are where regressions get made.
- **D8 for both apps** means `fds_cms` and `fds_donation` can never again be
  `git`-pulled cleanly from DE. §1a justifies this for `fds_cms` (21 plugin rows);
  for `fds_donation` it is forced, since donor rows are real money.
- **D9 requires a one-off production step**, not just a code change:
  `manage.py migrate --fake fds_cms 0005`. Record it in the deploy runbook, and
  note that it must **not** be run on a database that lacks the columns.

## 0b. The decisions as originally posed — rationale and trade-offs

*All nine are now settled (§0). This section is retained because the reasoning
behind each choice is the part worth revisiting when circumstances change; the
recommendations below are the drafts that were put to the team, not open questions.*

### D1 — Merge direction: forward-port DE@hash→HEAD, or rebase AT onto DE@HEAD?

The baseline is genuinely 3.5 years stale, but **AT's own divergence is small**:
of 356 files under `fragdenstaat_at/`, **244 are byte-identical to DE@hash**
(after the `fragdenstaat_de`→`fragdenstaat_at` rename), 56 are modified, and 56
are AT-only. Of the ~1169 lines AT added to shared files, **365 are commented-out
DE code** and most of the remaining ~800 are string/branding/IBAN substitutions.

> **Recommendation: rebase AT onto DE@HEAD.** Take DE HEAD wholesale, then re-apply
> the AT delta as a thin configuration + branding layer. Replaying 2194 commits of
> DE history onto a fork whose main edit is "comment out the German bits" would be
> strictly more work for a worse result.

### D2 — "Comment out" vs. "configure out"

AT's disable pattern today is commenting out lines in `settings/base.py`,
`theme/urls.py`, `theme/views.py`, `fds_donation/*`. That is what makes every
future sync a manual merge-conflict session.

The alternative is to make the AT deltas **declarative**: keep DE's code intact
and drive the differences from settings (`INSTALLED_APPS` subtraction, feature
flags, `DONATION_SITE_NAME_OVERRIDE`-style overrides, template overrides). DE
already has hooks for some of this (`EASYLANG_ENABLED`, `USER_LANGUAGES`,
`DONATION_PROJECTS`). Adopting this is the single highest-leverage decision here;
it converts every future sync from "merge" to "pull".

If chosen, some of it needs upstreaming to DE (see D5).

### D3 — Which of the four dropped apps come back?

`fds_blog`, `fds_newsletter`, `fds_mailing`, `fds_fximport` were all dropped.
`fds_newsletter` + `fds_mailing` are load-bearing in DE: `fds_donation` has
first-class dependencies on them (the `Donor.subscriber` FK is commented out of
AT's model, `SetupMailingMixin` is commented out of `DonorAdmin`). Every future
`fds_donation` sync fights this. Options:

- **(a)** Re-adopt newsletter + mailing. Removes the largest single source of
  merge friction, costs an Austrian newsletter/CRM story.
- **(b)** Stay without them and accept that `fds_donation` needs a permanent
  manual patch on every sync.
- **(c)** Re-adopt the models but leave the UI/CMS plugins disabled — restores the
  FK so `fds_donation` merges cleanly, without running a newsletter.

`fds_blog` and `fds_fximport` are genuinely optional (see §3).

### D4 — Language code: `de-at` or `de` + `de_AT` overrides?

AT sets `LANGUAGE_CODE = "de-at"` with a single-language `CMS_LANGUAGES`, but its
translation catalogues live in `locale/de/` and `locale/en/` — i.e. they are
reached only via Django's `de-at`→`de` fallback. Meanwhile `sync_froide_translations.py`
(commit `b047758`, uncommitted intent) targets a **`locale/de_AT/`** directory
that does not exist yet, and the AT deployment currently depends on **590 `de_AT`
msgids (505 translated) living inside the froide fork** at
`/workspaces/fds_at/froide/froide/locale/de_AT/`.

Pick one and make it consistent, because DE@HEAD has since added a third
language (`de-ls`, Leichte Sprache) and a `USER_LANGUAGES`/`LANGUAGES` split that
AT's single-language CMS config will collide with.

### D5 — Relationship to upstream froide and to DE

AT currently pins a **fork** of froide (`git log`: "update okfde/froide to fin/froide
for translations", "pin froide requirement to fin/froide@at-deploy"), and there is
live in-flight work in `/workspaces/fds_at/froide` and `/workspaces/fds_at/froide-fax`
(see `../HANDOFF.md`) adding a fax transport. Decide whether AT:

- carries a permanent froide fork (then every sync is a three-way merge), or
- upstreams the `de_AT` locale and the transport work to okfde/froide and tracks
  `main` (strongly preferable — and the translation script in `b047758` is
  already a step towards it).

### D6 — Dependency management style

AT's `pyproject.toml` is a **flat, fully-pinned dump of 200+ transitive packages**
(converted from an old `requirements-dev.txt`), including dev tools like `black`,
`flake8`, `coverage` as runtime deps. DE@HEAD has a curated ~100-line direct-dependency
list with ranges plus `[dependency-groups] dev`. Adopting DE's file is a
prerequisite for tracking DE at all — otherwise every DE dependency bump is a
merge conflict against a lockfile-shaped `pyproject.toml`.

### D7 — Test strategy

AT has `tests/` and a `.github/workflows/ci.yml`; DE@HEAD has moved to pytest +
Playwright with a `fragdenstaat_de/tests/` package, a `database-cache` workflow and
two translation workflows. Decide whether AT adopts DE's test harness before or
after the code sync. Before is safer but slower to first value.

### D10 — Static placeholders: migrate to djangocms-alias, or stay on cms 5.0? ⚠️ **OPEN**

*Raised 2026-08-18 during D6. This is the one decision blocking the rest of P2.*

**django-cms 5.1 removes `StaticPlaceholder` entirely** — no model, no admin. AT
has four in live use (`footer`, `top_banner`, `dropdown_banner`, `help_footer`,
plus `message_donation_banner` referenced from a template), and — per the
correction in §2.7 — **the live site footer is one of them**. `fds_cms/admin.py`
and `fds_cms/templatetags/fds_cms_tags.py` both import the removed model.

DE has already completed this move: it has **zero** references to
`StaticPlaceholder` and uses djangocms-alias `{% static_alias "code" %}`.

- **(a) Migrate to djangocms-alias now.** Follow DE. Data migration converting 4
  static placeholders and their plugin trees into Aliases, plus swapping the
  template tag. Unblocks `django-cms>=5.1` and closes the last big gap to DE.
  Touches live editorial content, so it needs a staging rehearsal.
- **(b) Pin `django-cms>=5.0.5,<5.1` and defer.** ⬅ **currently in effect**, so the
  branch stays working. Diverges from DE's `<6`, and the pin has to be lifted
  eventually — cms 5.0.x will not be supported forever.

> **Recommendation: (a), during P3**, where a staging rehearsal against the
> extract is already planned — but it is a live-content migration, so it is the
> user's call. The rest of the cms/alias/versioning upgrade is **already proven
> safe** (§1e), which makes (a) less risky than it would have looked yesterday.

---

### D8 — `fds_cms` migration lineage *(forced by the live database)*

AT squashed `fds_cms` to 4 applied migrations; DE@HEAD has ~60 with entirely
different numbering, different plugin tables, and 3.5 years of provenance.
Production holds real (if small) content in AT's tables. "Adopt DE's `fds_cms`
wholesale" — P2 step 12 as originally written — is therefore **not directly
executable**. Three routes:

- **(a) Fake DE's graph in.** Mark DE's `fds_cms` 0001…N as applied, then
  hand-write one reconciliation migration for the schema delta (DE's newer
  plugins that AT lacks; AT's legacy Row/Column/Container that DE dropped).
  Restores clean pulls from DE afterwards. Highest one-off risk.
- **(b) Keep AT's squashed graph; forward-port DE's *models* as AT `0006, 0007…`.**
  Safest against the live DB and by far the least ceremony. Cost: `fds_cms` can
  never again be a clean `git` pull from DE — every future CMS sync is manual.
- **(c) ~~Rebuild the content.~~** *Retracted on review.* An earlier draft floated
  re-creating the pages on DE's unmodified `fds_cms`, on the strength of "only 10
  pages". That was wrong on three counts: the pages are the site's **legally
  significant** text (Nutzungsbedingungen, Datenschutzerklärung, Impressum), which
  should not be retyped; the team **already did this rebuild once**, in August 2025;
  and it is **unnecessary**, because 64 of 103 plugin instances live in third-party
  tables that a lineage change never touches (§1a). Rebuilding would also cost the
  version history and destabilise page IDs and URLs that `content_urls` depends on.

> **Recommendation: (b).** Keep AT's squashed graph and forward-port DE's model
> changes as AT `0006, 0007…`. It is the least ceremony and the least risk, and it
> gives up only the ability to `git`-pull `fds_cms` cleanly from DE — which §1a
> shows is a small prize, since AT's `fds_cms` content footprint is 21 plugin rows.
> (a) remains viable and is more tractable than it first looked, for the same
> reason; take it only if clean future pulls of `fds_cms` are judged worth one
> risky operation.

---

## 1. Ground truth: what the baseline actually is

The stated baseline is correct but **not uniform**. AT's git history records four
explicit sync points (`cd59b7cc` → `059ffc5e` → `7f53bece` → `abe0781d`), and 244
files still match `abe0781d` byte-for-byte. But three later, hand-done efforts
pulled code from a *much* newer DE:

| AT commit | date | what it pulled from newer DE |
|---|---|---|
| `5515236` | 2025-08-30 | `theme/colors.py` — **byte-identical to DE@HEAD**; DE added it 2024-07-18 (`52ebde68`). Also the Vite/SCSS/`base.scss` build |
| `c865d3e`, `41286c4` etc. | 2023-01 → 2026-06 | django-CMS 4/5 port: `djangocms_versioning`, `djangocms_alias`, `djangocms_text`, `PageContent` in `fds_cms/documents.py`, `djangocms_frontend.fields` in `fds_cms/models.py` |
| — | — | `fds_cms/apps.py` contains DE's `Page.get_absolute_url` monkey-patch **verbatim**, which DE committed 2025-06-27 (`7d29a112`) |

**Consequence, and it is good news:** AT and DE have *independently converged* on
django-cms 5 + `djangocms-versioning` + `djangocms-frontend` + `djangocms-text`.
The single biggest structural obstacle to a re-sync — a CMS major-version gap — is
already gone. `django-cms==5.0.2` (AT) vs `>=5.0.5,<6` (DE) is a patch bump.

**Consequence, and it is bad news:** the hand-port left casualties. See §6 (Defects).

> *Human involvement: **none outstanding.** This section is the evidence base for
> **D1**, which is settled (§0): rebase onto DE@HEAD. Nothing here is a live
> question — it is the justification, kept for when the direction is revisited.*

---

## 1a. The live database — measured, not assumed

*Static analysis. §1b then executed the critical findings against a real load of the extract; all of them reproduced.*

*Added on review. Source: `../test_export_2026-06-14.sql` (produced by
`../export_dev_db.py` run against `settings.production`), cross-checked against
the migration heads of the packages actually installed in `.venv`.*

The dump carries the real `django_migrations` table (628 rows), so the applied
state of production is directly observable rather than inferred.

### The headline: production is *not* stale

| App | Applied in prod | Head of the pinned package | Gap |
|---|---|---|---|
| `cms` | `0041_alter_pageurl_unique_together…` | `0041…` | **0** |
| `djangocms_versioning` | `0017_merge_20230514_1027` | `0017…` | **0** |
| `djangocms_alias` | `0004_alter_aliascontent_language` | `0004…` | **0** |
| `filer` | `0017_image__transparent` | `0017…` | **0** |
| `fds_donation` | `0044_regulardonorsprogressbarcmsplugin_and_more` | repo head | **0** |
| `fds_cms` | `0004_borderedsection…_and_more` | repo head `0005` | **1 — and it will fail, see below** |

Production runs `cms_pagecontent` / `djangocms_versioning_version` /
`djangocms_alias_*` — i.e. **it is already on django-CMS 4.1/5 with versioning**.
There is no `cms_title`. The CMS major-version migration that §1 called "already
gone" from the *code* is also already done in the *data*.

Against upstream froide `main` (`fae1d1cb`, 2026-08-17) the gap is likewise small:
`foirequest` 0072→0076, `account` 0038→0043, `publicbody` 0050→0055,
`georegion` 0013→0014, `guide` 0007→0008, `proof` 0001→0002. **~20 migrations
total**, not the multi-year chasm the code diff implies.

### 🔴 Migration `fds_cms/0005` cannot be applied to production

This is a live deploy blocker that predates the merge question entirely.

Production is recorded at `fds_cms 0004`, **and already has every column that
`0005` adds**: `borderedsectioncmsplugin.attributes`, `cardcmsplugin.attributes`,
`modalcmsplugin.{tag_type,attributes,dialog_attributes}`,
`revealmorecmsplugin.attributes` — all present in the June-14 schema.

The cause is visible in the history: commit `c865d3e` ("migrations now run on
current code version", 108 lines changed in `0004`) **commented the `AddField`
operations out of `0004`** so migrations would run on a *fresh* database; commit
`71970d8` then autogenerated `0005` to put the fields back. That round-trip is
self-consistent for a greenfield install and inconsistent with production, which
was migrated by the *original* `0004`.

`manage.py migrate` on production will raise
`column "attributes" of relation "fds_cms_borderedsectioncmsplugin" already exists`.

**Fix:** make `0005` a `SeparateDatabaseAndState` / `--fake`-able no-op for
already-migrated databases, or gate each `AddField` behind an introspection check.
Do this **before** anything in P1–P5, and rehearse with `export_dev_db.py`.

### Provenance of the dump — checked, because a lot rests on it

Production-derived, not a scratch dev database. Reference data spans **2015 →
2026-06-08** (six days before the export). 2269 public bodies, 12 FOI laws.

The CMS content, however, was **all authored 2025-08-30/31** — ten pages in a
single ~17-hour window. That is not scaffolding: the pages are `Nutzungsbedingungen`
("Stand: 31.8.2025"), `Datenschutzerklärung`, `Über uns` (with a real Impressum),
`Fragen & Antworten`, `Behörden-Infos`, `Spenden`, `Hilfe`, `Info`, `Homepage`.
It is the site's real content, **rebuilt from scratch during the August 2025
django-CMS 4 modernization** — which is exactly why the tree is small and the
timestamps cluster.

*(`created_by` reads `'dev'` and `account_user` has one row on every page — those
are the export script's scrubbing, not evidence about the source. The timestamps
and the content itself are not scrubbed, and they are what the above rests on.)*

### The CMS footprint of `fds_cms` is tiny — 21 of 103 plugin instances

This is the number that actually governs D8, and it is much smaller than the page
count suggested:

| Owner | Plugin instances |
|---|---|
| Third-party (`TextPlugin` 20, `GridContainer/Row/Column` 43, `Picture` 1) | **64** |
| `fds_cms` modern (`FdsCard*` 14, `DesignContainer` 3, `FoiRequestList` 1) | 18 |
| `fds_cms` **legacy** (`SubMenu` 6, `Row` 3, `Column4/6/8` 5, `ContainerGrey` 1, `PageSubMenu` 2) | 17 |
| `fds_donation` (`DonationForm`) + AT homepage (`HomepageHero/How`) | 4 |

**A change to `fds_cms` migration lineage does not touch the text or the grid
layout at all** — 64 of 103 plugin instances live in third-party tables that are
unaffected. Only ~21 rows are in play, and zero aliases exist.

⚠️ **Not measurable from this dump:** `export_dev_db.py` truncates all application
tables, so the row counts for `foirequest_*`, `account_user`,
`fds_donation_{donor,donation}` and `froide_payment_*` are unknown. Get those
before committing to any migration window — they set the downtime, not the CMS.

### Orphaned schema

The live database still carries **24 `bootstrap4_*` tables** (djangocms-bootstrap4,
long since replaced by djangocms-frontend), `djangocms_text_ckeditor`,
`campaign_campaign`, `letter_*`, `guide_*`, `proof_*`, `foisite_*` — with their
migration rows still recorded, for apps no longer in `INSTALLED_APPS`. Harmless
today, but a hazard the moment DE's code reintroduces one of those app labels.


---

## 1b. Verified against the extract — 2026-08-18

*Everything in §1a was static analysis. This section is what was actually executed,
on branch `sync/de-head-2026-08`, against `test_export_2026-06-14.sql` loaded into a
scratch database (`fds_verify` on the devcontainer's `db` service).*

**Setup.** The extract loads cleanly into PostGIS 16 — 229 tables, 628
`django_migrations` rows. Two benign load errors: `transaction_timeout` (a pg17
parameter absent in pg16) and one syntax error on a version comment. Neither
affects the schema.

| # | Check | Result |
|---|---|---|
| 1 | `fds_cms` recorded state | `0004`, `0005` unapplied — **as predicted** |
| 2 | The six columns `0005` adds | all six present — **as predicted** |
| 3 | `manage.py migrate fds_cms` | 🔴 **fails**: `ProgrammingError: column "attributes" of relation "fds_cms_borderedsectioncmsplugin" already exists` — **blocker reproduced** |
| 4 | `manage.py migrate --fake fds_cms 0005` (**D9**) | ✅ `FAKED` — **the chosen fix works** |
| 5 | Full `manage.py migrate` afterwards | ✅ **exit 0**, 23 migrations applied, no manual intervention |
| 6 | Content intact after migrating | ✅ 10 pages, 103 plugins, 2269 public bodies |
| 7 | `makemigrations --check` | drift in `account`, `publicbody`, `djangocms_frontend`, `contractor`, `sortabletable` — **all third-party; none in `fds_cms`, `fds_donation` or `theme`** |

### What this changes

- **D9 is no longer a proposal, it is a tested procedure.** Reproduce the failure,
  apply the fake, migrate forward. Put steps 3–5 in the deploy runbook verbatim.
- **The froide catch-up is a non-event.** Check 5 applied `account` 0039–0043,
  `campaign` 0008–0009, `document` 0031–0032, `filingcabinet` 0032, `foirequest`
  0073–0076, `georegion` 0014, `guide` 0008, `proof` 0002, `publicbody` 0051–0055
  and the new `searchalert` app — **23 migrations, cleanly, in one command.** §1a
  estimated ~20 from migration-file counting; measured is 23. P1's database risk is
  now close to zero. *(Caveat: this is against the pinned `fin/froide`, not
  `okfde/froide@main` — re-run check 5 after the D5 repin.)*
- **AT's own models have zero drift** against the production schema (check 7). The
  drift that exists is upstream packages whose shipped migrations lag their models —
  a pre-existing annoyance, unrelated to the sync, and it will need a decision when
  D6 changes those pins.
- **Defect §6 #10 confirmed live:** every management command prints
  `devtemplates [{...}]` to stdout before doing anything.

### How to rebuild this environment

```
psql -h db -U fragdenstaat_at -d postgres -c "CREATE DATABASE fds_verify"
psql -h db -U fragdenstaat_at -d fds_verify -c "CREATE EXTENSION postgis; CREATE EXTENSION hstore;"
psql -h db -U fragdenstaat_at -d fds_verify -f ../test_export_2026-06-14.sql
DATABASE_HOST=db DATABASE_NAME=fds_verify \
  DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.development DJANGO_CONFIGURATION=Dev \
  .venv/bin/python manage.py migrate
```

⚠️ **Parallel work must use separate scratch databases** (`fds_verify_<task>`), not
this one — concurrent migrations against one database will corrupt each other's
`django_migrations` state.


---

## 1c. Porting against upstream froide, with a switch back — built 2026-08-18

Per **D5**, porting happens against `okfde/froide`. The fax-transport work lives on
the fork and must stay reachable, so the source is switchable rather than replaced.

**How froide is actually wired** (this is what makes the switch cheap):
`pyproject.toml` already declares `froide = { git = "okfde/froide", rev = "main" }`.
But the venv installs it **editable** from the sibling checkout
`/workspaces/fds_at/froide` (`__editable__.froide-6.0.0.pth`), so what Python
imports is that working tree, whatever `pyproject.toml` says. Only the checkout had
been repointed at `fin/froide`. **Switching source is therefore a `git checkout` —
no `uv sync`, no reinstall.**

```
./scripts/froide-source.sh status   # which source is active
./scripts/froide-source.sh okfde    # upstream — the porting baseline
./scripts/froide-source.sh fin      # the fork — fax transport work
```

The script resolves remotes **by URL, not by name**, because `origin` is the fork in
the current checkout but upstream in a fresh `devsetup.sh` clone. It leaves `origin`
alone, adds an `okfde` remote if missing, and reports uncommitted edits on each
switch.

**Verified round-trip:** `fin → okfde → fin → okfde`, with the uncommitted
devcontainer edits to `froide/settings.py` byte-identical throughout (that file does
not differ between the two sources, so a checkout carries it cleanly).

**One dev-script change was needed.** `devsetup.sh` pulled with
`git pull origin --autostash "$(git branch --show-current)"`, which breaks on a
branch tracking `okfde` — it would ask `origin` (the fork) for a branch it lacks. It
now pulls from the branch's configured **upstream**, falling back to the old
behaviour when a branch has none. A `devsetup.sh` re-run no longer undoes a switch.

⚠️ **Migration divergence between the two sources.** The fork adds
`foirequest/0076_alter_foimessage_kind`; upstream's head is `0075`. A database
migrated against the fork has an applied migration with no file upstream. Use a
separate scratch DB per source — the script prints this on every switch to upstream.


---

## 1d. Test suite resurrected — 2026-08-18

**Before: zero tests could run. After: 10 passed, 1 skipped, 0 errors.**

D7 put harness work before the code sync. That turned out to be more urgent than
"adopt DE's pytest/Playwright setup": AT's own suite was not merely stale, it was
**completely non-executing**, and had been since the Python 3.13 and django-cms 5
moves. Five separate blockers, each hiding the next:

| Order | Blocker | Fix |
|---|---|---|
| 1 | `time-machine==2.9.0` uses `uuid._load_system_functions`, gone in Py3.13 — failed at **pytest plugin load**, before collection | `time-machine>=2.16` (#15) |
| 2 | `factory-boy==3.2.1` predates `Meta.skip_postgeneration_save`, used by froide's `UserFactory` — `conftest.py` failed to import | `factory-boy>=3.3` (#16) |
| 3 | `tests/fixtures/cms.json` held **django-cms 3** models (`cms.treenode`, `cms.title`) | regenerated from the production extract (#17) |
| 4 | `fds_cms/views.py` imported `cms.models.Title`, removed in cms 4 | → `PageContent` (#18) |
| 5 | `tests/test_misc.py` imported `djangocms_text_ckeditor`, broken on cms 5 — killed **collection of the whole suite** | → `djangocms_text` (#19) |

Plus `playwright install chromium`, which the devcontainer had never run.

### Why this matters beyond the test suite

- **#18 is a production defect the suite would have caught years ago.** The CMS
  search view cannot be imported. It is latent only because `fds_cms.urls` is not
  routed in production — routing it would 500 the site.
- **The regenerated fixture is now real production content** (10 pages, versioning
  rows, the scrubbed dev user) rather than 2021-era hand-made data. Tests exercise
  the same page tree the site actually has.
- **D7's ordering is vindicated.** Three of the five blockers were CMS-upgrade
  casualties of exactly the kind P2/P3 will produce more of.

### Running it

```
env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION \
  DATABASE_URL="postgis://fragdenstaat_at:fragdenstaat_at@db:5432/fragdenstaat_at" \
  DJANGO_ELASTICSEARCH_HOSTS=elasticsearch:9200 \
  .venv/bin/python -m pytest -q
```

⚠️ **Unset `DJANGO_SETTINGS_MODULE` and `DJANGO_CONFIGURATION` first.** Environment
variables override `pytest.ini`, so a shell left over from a `manage.py` session
silently runs the suite under `Dev` instead of `Test` — which is how #17 was
initially misdiagnosed. Worth a `conftest.py` guard.

### Still to do for P1b

Adopt DE's harness proper: its `fragdenstaat_de/tests/` package, async Playwright,
the sequential browser-test group, and the `database-cache` CI workflow. AT's suite
is now a working baseline to migrate *from*, which it was not this morning.


---

## 1e. D6 executed — dependency set adopted, upgrades verified — 2026-08-18

AT's `pyproject.toml` was a flat dump of 200+ pinned transitive packages. It is now
DE's curated direct-dependency list, minus the apps AT does not enable (verified
against the **runtime** `INSTALLED_APPS`, not the source, since much of AT's
settings file is commented out):

> `froide-campaign`, `froide-food`, `froide-fax`, `froide-legalaction`,
> `froide-exam`, `froide-crowdfunding`, `froide-govplan`,
> `froide-evidencecollection`, `froide-pressconference`, `froide-election`,
> `django-amenities`, `django-legal-advice-builder`, `osmium`, **`torch` +
> `torchvision`** (only `fds_fximport`'s captcha solver needed those, and D3 keeps
> it out — this alone drops ~2 GB from the image).

`django-flowcontrol` and `mjml-python` are included *ahead of need*, because D3's
`fds_newsletter`/`fds_mailing` require them.

### What the upgrade actually moved

| | before | after |
|---|---|---|
| django-cms | 5.0.2 | 5.0.10 *(5.1.1 blocked by **D10**)* |
| djangocms-versioning | 2.3.1 | **2.7.0** |
| djangocms-alias | 2.0.4 | **3.1.1** (major) |
| django-countries | 7.5 | 9.0.0 |

### The P3 "biggest data risk" turned out to be a non-event

P3 step 18a called the alias/versioning major bumps a bigger data risk than the
sync itself. Rehearsed against a fresh load of the production extract:

```
djangocms_alias.0005_dynamic_slot_names                        OK
djangocms_alias.0006_alter_alias_id_alter_aliascontent_id…     OK
djangocms_alias.0007_alter_category_options_alter_aliasplugin… OK
djangocms_frontend.0003_slotmodel                              OK
djangocms_versioning.0018_fix_typo                             OK
… plus the froide catch-up …                                   OK
```

**Exit 0, no intervention, content intact** (10 pages, 103 plugins, 4 static
placeholders). `manage.py check` clean, suite green (10 passed, 1 skipped).

### Two traps worth knowing

1. **`uv sync` clobbers the editable sibling installs.** froide, froide-payment and
   django-filingcabinet are installed `-e` from `../`; a sync replaces them with git
   checkouts and silently breaks `scripts/froide-source.sh`. Always re-run the three
   `uv pip install -e ../<pkg>` lines afterwards, exactly as `devsetup.sh` does.
2. **`uv lock` keeps satisfiable stale pins.** Dropping `django-countries==7.5` did
   not upgrade it — nothing else constrained it, so the old resolution carried over
   and `pkg_resources` (gone from modern setuptools) broke startup. Needed an
   explicit `uv lock --upgrade-package`. Expect more of these; upgrade per package
   as breakage appears rather than assuming the lock refreshed.


---

## 2. Apps present in **both** repos, with AT changes

### 2.1 `fds_cms`

AT-side changes vs DE@hash:

**Gained**
- Full **django-CMS 4/5 port**, hand-done ahead of DE: `documents.py` indexes
  `PageContent` instead of `Title`; `listeners.py` listens on
  `djangocms_versioning.signals.post_version_operation` instead of
  `post_publish`/`post_unpublish`; `utils.get_plugin_children` uses a flat
  `CMSPlugin.objects.filter(parent=...)` instead of `get_descendants()`.
- Local `concat_classes()` in `utils.py`, replacing `djangocms_bootstrap4.helpers`.
- **Legacy structural CMS plugins**: `RowPlugin`, six generated `ColumnNPlugin`s,
  `ContainerPlugin`, `ContainerFluidPlugin`, `ContainerGreyPlugin`,
  `SubMenuPlugin`, `PageSubMenuPlugin`. Pre-`djangocms_frontend` Bootstrap
  scaffolding that DE deleted. AT does still have live content on them — but
  **17 plugin instances in total** (§1a), alongside 43 modern
  `GridContainer/Row/Column` ones. Retiring them is a contained data migration,
  not a project.
- `HomepageHeroPlugin` / `HomepageHowPlugin` — AT's own homepage, with FOI-request
  and public-body counters.
- `Page.get_absolute_url` monkey-patch (multi-site domain-qualified URLs).
- Management commands `export_fdscms.py` (dumpdata for CMS apps) and a local
  `load_georegion.py`.
- **Squashed migrations**: AT has 5 migrations (`0001_initial` is 337 lines) where
  DE@hash had 55. ⚠️ This is a hard blocker for any migration-level merge; see §5 P3.

**Lost**
- `PublicBodyFeedbackPlugin` + `contact.py` (contact form) — commented out.
- `search_registry.register(add_search)` — **CMS help pages are not in site search**.
- AVIF thumbnail generation (`store_as_avif`), and the whole `listeners` module is
  never imported (`apps.ready()` has `# from . import listeners`).
- `static/css` assets.

**Germany-specific in what AT kept:** low. `load_georegion.py` maps German
Bundesland/Kreis/Gemeinde shapefile schemas (`ARS` keys, `borough` under
`municipality`) — Austrian equivalents are Gemeindekennziffern, so the command is
DE-shaped even in AT's copy.

**What AT would gain from DE@HEAD (200 commits):** datashow/Datawrapper embed
plugins, search-alert plugin, dark-mode toggle + language-switcher plugins, video
consent banner, `AttributesField` on design containers, FoiRequest **map** template
for the request-list plugin, page-annotation titles/lazy-loading, 1h caching of
plain CMS views, CMS-5 sitemap fix, a bulk CSS-class migration script.

> *Human involvement: **medium** — revised down twice.* **D8** chose (b), so the
> migration squash needs no reconciliation at all. And §1a measured the legacy
> Row/Column/Container/SubMenu plugins at **17 instances**, not an unbounded content
> risk — a scriptable data migration with human review. What remains genuinely
> human: deciding which of DE's 200 commits' worth of new plugins AT wants.*

---

### 2.2 `fds_donation`

The most heavily AT-modified app, and the most Germany-entangled.

**Gained**
- `RegularDonorsProgressBarCMSPlugin` (model + plugin + template + migration
  `0044`) — progress bar counting *recurring donors* against a goal, with an
  optional `minimal_annual_contribution` floor. AT's own feature; no DE equivalent.
  ⚠️ Its `get_donor_count()` does `Donor.objects.all()` in Python and sums
  subscription lists — O(donors) queries. Fine at AT scale, will not survive growth.
- Austrian banking throughout: IBAN `AT69 2011 1824 3494 2000` / BIC `GIBAATWWXXX`,
  creditor ID `AT54ZZZ00000060559`, account holder **Forum Informationsfreiheit**.
- `DONATION_SITE_NAME_OVERRIDE` setting + `get_payment_metadata()` support, so
  payment descriptors read "Forum Informationsfreiheit" while `SITE_NAME` stays
  "FragDenStaat.at". A clean, reusable pattern — **this is the model for D2**.
- `MIN_AMOUNT` lowered 5 → 2 EUR.
- Rewritten `external.py` bank-statement importer for **Erste Bank/George** column
  names (`Valutadatum`, `Buchungsdatum`, `Partnername`, `Zahlungsreferenz`,
  `Partner IBAN`, `BIC/SWIFT`, `Buchungs-Details`) instead of DE's generic
  `Datum`/`Name`/`Verwendungszweck`.
- `sepa_notification_subject.txt` (DE had body but no subject template).

**Lost / disabled**
- **All newsletter coupling**: `Donor.subscriber` FK commented out of the model,
  `subscribe_to_default_newsletter` and `subscribe_donor_newsletter` disabled in
  `services.py`/`utils.py`, `subscriber` dropped from `MERGE_DONOR_FIELDS` and
  from CSV export. *(The live schema has no `subscriber_id` column — verified
  against the production dump, see §1a. Re-adopting the FK is therefore an
  additive, all-NULL migration with no backfill.)*
- **All mailing coupling**: `SetupMailingMixin` removed from `DonorAdmin`,
  `send_mailing` admin action neutered (it still reports "Prepared mailing of N
  recipients" but creates nothing — see §6).
- Donation **purpose** selector → `HiddenInput` (DE offers a project picker).
- Donation **receipt** opt-in → `HiddenInput`, default 0.
- `update_direct_debit()` / `DEBIT_PATTERN` — SEPA direct-debit reconciliation from
  bank statements is commented out.
- `DONATION_LOGIC_PLUGINS` (IsDonor / IsRecurringDonor / ContactAllowed… CMS
  conditional plugins) removed from `CMS_PLACEHOLDER_CONF`.
- Stripe **Sofort** provider (correctly — Sofort was discontinued 2024).

**Germany-specific details needing Austrian adaptation:**

1. **`zwb.html` — the Zuwendungsbestätigung.** AT wrapped the *entire body* in
   `{% comment %}`, leaving only the title changed to "Zahlungsbestätigung". The
   PDF renders as an **empty document**. The German form is the official
   §50 EStDV Muster with the OKF Berlin letterhead embedded as base64. Austria's
   equivalent is **Spendenabsetzbarkeit** with mandatory **FinanzOnline**
   electronic reporting (§ 18 Abs 1 Z 7 EStG) — a *data submission*, not a PDF.
   The whole `export.py` / `get_zwb_data()` / `send_jzwb_mailing_task` /
   `backup_jzwb_pdf_task` pipeline is built for the German paper model and needs a
   ground-up Austrian replacement. **This is the single largest genuinely new
   piece of work in the whole plan.**
2. `country` field default `"DE"` → `"AT"` — done.
3. `DONATION_PROJECTS` `FDS`/`CFG`/`JH`/`GM` → `FOI` — done. CFG and JH are OKF
   Germany programmes.
4. Sender-org identity in `sepa_notification.txt`: OKF's Vereinsregister VR 30468 B
   / Amtsgericht Charlottenburg → Forum Informationsfreiheit (done, though the AT
   version now carries *no* registration data, which Austrian ZVR practice
   arguably requires).
5. `remote_filing.py` and `DONATION_BACKUP_URL` — DE's remote filing backend.
   Unchanged in AT; needs confirming it points somewhere Austrian.

**What AT would gain from DE@HEAD (374 commits — the biggest delta of any app):**
a `Recurrence` model with cancel reasons, upgrade flows and admin filters;
`DonorEvent` audit trail; donor **self-service auth** (`auth.py`, magic-link donor
login, subscription access); `django-flowcontrol` integration (tag/recent-donation/
segment condition actions); gift-order shipping with Post-Internetmarke CSV export;
IBAN in donor export; refund + partial-refund handling; `form_settings.py` +
`triggers.py`; `DonationFormViewCount`; a proper `tests/` suite. Migration count
44 → 79.

> *Human involvement: **required**, highest of any item.* The Austrian tax-receipt
> replacement is a legal/finance design task, not a merge. The newsletter/mailing
> re-coupling is settled by **D3** and is now execution, not choice (see P2 step 9 —
> including the `?newsletter` bypass). The branding/IBAN substitutions **are**
> automatable and are
> already correctly done — preserve them mechanically.

---

### 2.3 `fds_ogimage`

**Byte-identical to DE@hash** (modulo package rename), but **disabled**:
commented out of `INSTALLED_APPS`, out of `theme/urls.py`, and its template tags
are `{% comment %}`-ed out of `account/profile.html` and `foirequest/show.html`.
`FDS_OGIMAGE_URL = ""`. Those two templates therefore emit
`<meta property="og:image" content="" />` — an empty og:image tag on every profile
and request page (§6).

DE@HEAD changed it only 4 times. Re-enabling needs an AT-hosted ogimage service
(DE's is `ogimage.frag-den-staat.de`), or the meta tags should be removed properly.

> *Human involvement: **low**. Decide host-or-remove; the code change is trivial
> and automatable either way.*

---

### 2.4 `theme`

**Gained**
- `colors.py` — Bootstrap/theme colour token lists (verbatim from DE 2024-07).
- `theme/static/fonts/` — Kreon + FontAwesome webfonts vendored locally.
- `theme/templates/` — local overrides of `header.html`, `account/settings.html`,
  `emails/footer.txt`, `snippets/meta.html`, `cms/container.html`.
- `management/commands/update_georegion.py`.

**Lost**
- `theme/templatetags/fds_tags.py` — emptied (was the glyphosat + frontex filters).
- `theme/admin.py`, `theme/cms_plugins.py`, `theme/glyphosat.py`, `theme/locale/`.
- `views.index` (custom homepage), `glyphosat_download`, `meisterschaften_tippspiel`
  — all commented out.
- `inject_status_change` — DE redirects a user to a donation ask after they mark a
  request successful. AT disabled it. Worth revisiting as an AT fundraising hook.
- Management commands `attach_topics`, `calculate_stats`, `extract_fax`,
  `import_blog`, `load_berlin`/`brandenburg`/`hamburg`/`nrw`.

**Germany-specific in what remains:**
- `legal_backup.py` + `make_legal_backup` task — Google-Drive backup of a user's
  request record, built for the German **Klageautomat** / legal-action workflow.
  Still present and wired in AT. Useless without `froide_legalaction` (disabled).
- `amenity_updater.py` + `update_amenities` task — OSM amenity ingestion for
  `froide_food` / `froide_campaign` (both disabled). Dead code in AT.
- `search.py` analyzers — German decompounding/stemming; largely fine for Austrian
  German, but `TESSERACT_LANGUAGE = "de"` and the analyzer config should be reviewed.
- `load_berlin.py` etc. correctly dropped.

> *Human involvement: **medium**. Deciding what dead German machinery to delete
> outright vs. keep is judgement; identifying it is automatable (grep for imports
> of disabled apps).*

---

### 2.5 `settings/`

`base.py`: 413 diff lines vs DE@hash. AT's changes are almost entirely
**subtraction by comment** plus identity substitution.

**Identity / locale**
`LANGUAGES = (("de-at", …),)`, `LANGUAGE_CODE="de-at"`, `TESSERACT_LANGUAGE="de"`,
single-entry `CMS_LANGUAGES` and `PARLER_LANGUAGES`, `hide_untranslated=False`,
`redirect_on_fallback=False`. `SITE_NAME`/`SITE_EMAIL`/`DEFAULT_FROM_EMAIL`/
`FOI_EMAIL_DOMAIN=["foi.fragdenstaat.at"]`/`bounce_format`/`unsubscribe_format`/
`dryrun_domain` all `.at`. `search_engine_query` → `google.at`.

**Notable AT-only settings**
`CMS_CONFIRM_VERSION4`, `CMS_MIGRATION_USER_ID = 1`, `CMS_SIDEFRAME_ENABLED=False`,
`DONATION_SITE_NAME_OVERRIDE`, `MyStaticFilesStorage(manifest_strict=False)`,
`PAYMENT_CHECK_THRESHOLD` from env, ES hosts from `DJANGO_ELASTICSEARCH_HOSTS`,
`DATABASE_HOST` from env, `traces_sample_rate` 0.2 → 0.01.

**Extra CMS templates AT added:** `page_minimal.html`, `pub_base.html`
("Book Publication"), `page_anon.html` (page without tracking — DE independently
added the same idea in `847dd1f1`).

**Germany-specific config AT correctly removed:** `FROIDE_FOOD_CONFIG` (Google
Places/Yelp/Foursquare keys), `AMENITY_TOPICS`, Telnyx fax credentials,
`SLACK_DEFAULT_CHANNEL="fragdenstaat-alerts"`, `FRONTEX_CAPTCHA_MODEL_PATH`,
`CAMPAIGN_PROVIDERS`, `sanktionsfrei.de` in `ALLOWED_REDIRECT_HOSTS`,
`FOI_EMAIL_DOMAIN=["fragdenstaat.de","echtemail.de"]`.

**Germany-specific config AT kept and should review:**
- `FROIDE_CONFIG["greetings"]` / `closings` — AT *added* Austrian forms
  ("Grüß Gott", "Sehr geehrte Frau …") on top of DE's. Good.
- `recipient_blocklist_regex` — still blocks `.de-mail.de`,
  `z@bundesnachrichtendienst.de`, `empfangsbestaetigung@bahn.de`,
  `eingangsbestaetigung@jobcenter-ge.de`. ⚠️ AT's edit **duplicated** the pattern
  rather than replacing it (§6).
- `default_law` 2 → 1, `publicbody_empty` True → False, `target_countries` removed
  (DE had `("DE","CH","AT")`).
- `content_urls` re-pointed to `/info/…`; `pseudonym` help URL commented out, so
  the pseudonym help link is dead.
- `TEXT_ADDITIONAL_PROTOCOLS = ("bank",)` — for the German banking-app deep links
  that AT then deleted from `banktransfer.html`.

**What AT would gain from DE@HEAD (188 commits):** `django-cookie-consent`,
`django-datashow`, `django-flowcontrol`, `USER_LANGUAGES`/`de-ls`,
`CELERY_TASK_ROUTES` overrides, `FDS_LEGAL_BACKUP_*`, `user_can_claim_vip`,
`query_preprocessor`, `TEXT_EDITOR` config, `FLOWCONTROL_TEMPLATE_FILTERS`, a
`XFrameOptionsCSPMiddleware`, and a much larger `djangocms_frontend.contrib` set.

> *Human involvement: **required**, but narrowed. **D2** fixes the *form* (an
> explicit override block, not commented-out code) and **D6** the dependency side, so
> what is left is per-line judgement on which retained settings are still right for
> Austria — notably the duplicated `recipient_blocklist_regex`, `target_countries`,
> and the dead `pseudonym` content URL. The mechanical part — producing the
> `AT-overrides` diff against DE@HEAD's `base.py` — is automatable (P2 step 11).*

---

### 2.6 Celery / scheduled jobs

Small surface, one real bug.

- Neither repo defines `CELERY_BEAT_SCHEDULE` in `base.py`; it is inherited from
  froide. AT's `production.py` **adds** `check_mail_log` (`crontab()`, every
  minute) — this is AT-only and matters for delivery-status parsing.
- DE@HEAD adds `CELERY_TASK_ROUTES` to route `run_subscriber_import` to the
  `convert` queue. AT has no task routing.
- AT tasks are: `theme.make_legal_backup`, `theme.cleanup_legal_backups_task`,
  `theme.update_amenities` (the last two operate on disabled features), plus the
  five `fds_donation` tasks.
- ⚠️ **All five AT donation tasks are still registered under
  `name="fragdenstaat_de.fds_donation.*"`.** `theme` tasks were renamed to
  `fragdenstaat_at.*`; `fds_donation` was missed. It works — but any beat schedule,
  queue route, or flower/monitoring rule keyed on the task name has to use the DE
  namespace, and it will silently break the day someone "fixes" it without
  draining the queue.
- `remind_unreceived_banktransfers` is documented "to be run on the 15th of each
  month" but nothing in AT schedules it. Confirm it is in the deployment's beat
  config, or it never runs.

> *Human involvement: **low for the audit, required for the rename.* Renaming a
> live Celery task name is a drain-and-deploy operation, not a code edit.*

---

### 2.7 Templates

56 shared files modified, 56 AT-only. The pattern is uniform: AT extends the
froide/DE template and **empties the blocks** that referenced disabled apps.

**Emptied to nothing:** `foirequest/header/tabs.html` (crowdfunding + Klageautomat
tabs), `foirequest/body/body.html` (crowdfunding/legalaction panes, campaign
questionnaire), `foirequest/body/message/message.html` (fax send, frontex import,
the entire **glyphosat BfR download modal**), `foirequest/sent.html` (donation ask
+ newsletter signup), `account/settings.html` (newsletter settings + fax
signature), `snippets/tracking.html` (Matomo at `traffic.okfn.de`).

**Emptied from `foirequest/header/header.html`** — worth listing because each is a
DE editorial hook AT has no equivalent for: EU-office banner for jurisdiction 107,
Umwelt→Klima-Helpdesk banner, a hardcoded **Corona/RKI** banner, and the
Schriftformerfordernis fax-signature prompt.

**AT-only templates:**
- `footer.html` — Forum Informationsfreiheit + OKF Deutschland credit + **Easyname
  server sponsorship**. Impressum/Nutzungsbedingungen/Datenschutz links.
  ⚠️ **Duplicated — and it is the _template_ that is dead, not the CMS copy.**
  *(Corrected 2026-08-18; an earlier draft of this document had it backwards.)*
  The database also holds a `footer` CMS **static placeholder** built from
  djangocms-frontend Grid/Text plugins. `base.html` renders **that** via
  `{% fds_static_placeholder "footer" %}`, and the live page proves it: absolute
  `https://fragdenstaat.at/info/…` links, `<u>` tags, a `d-sm-none` responsive
  duplicate of the sponsor block — none of which `templates/footer.html` produces.
  The template uses relative `{% content_url %}` links and a different column
  layout, and appears nowhere in the served HTML.

  Two consequences: editing `templates/footer.html` has **no effect on the site**,
  and the live footer therefore **depends on static placeholders**, which
  django-cms 5.1 removed — see **D10**. Also note the placeholder stores
  *hash-stamped* static URLs (`nessus_easyname_logo.64f39f3e3594.png`) pasted into
  the HTML, so the sponsor logos break on any `collectstatic` that changes those
  files.
- `foirequest/emails/presserecht/overdue_reply.txt` — **Austrian press-law
  (Informationsrecht der Presse) chase-up email.** Genuinely AT-specific law; no DE
  counterpart.
- `snippets/homepage_hero.html`, `homepage_how.html` — AT homepage.
- `legal_advice_builder/foirequest_list.html` — a "Klageautomat testen" harness
  page, German-titled, for a disabled app.
- `account/emails/confirmation_mail.*` — reworded signup confirmation.
- `djangocms_frontend/bootstrap5/hero/`, `header_minimal.html`, `header_reduced.html`.
- `snippets/temp.html` — an empty stub. Delete.

**Germany-specific left in AT templates:** `base.html`'s `metadescription` block
is still the **German IFG boilerplate** ("IFG-Anfrage nach Behördendokumenten…",
"Informationsfreiheitsgesetz"). Austria's regime is the
Informationsfreiheitsgesetz (in force since 2025) replacing the Auskunftspflichtgesetz
— the meta description should say so. `snippets/meta.html` still carries DE's
`google-site-verification` token.

> *Human involvement: **required** for copy/legal text; **automatable** to
> *find* every emptied block and every remaining `.de`/German-law string.*

---

### 2.8 Frontend (`frontend/`, not a Django app but part of the merge)

AT: 65 files; DE@hash 63; DE@HEAD 98. AT added `base.scss` + `globalvars.scss`,
switched `$font-family-serif` to StixTwo, added dropdown/modal tokens, and moved
to Vite 6 + pnpm. `main.ts` imports were re-pointed to froide's current snippet
paths and gained `color-mode`, `share-links`; **search is commented out**
(`// import { initSearch }`). `donation-form.ts` learned `de-at` for the fee hint.

`package.json` still declares `froide_campaign`, `froide_exam`, `froide_food`,
`froide_legalaction` as JS dependencies for Python apps that are disabled, still
describes itself as "Freedom of Information Portal in **Germany**", and its
`favicon` script points at `fragdenstaat_de/theme/static/img/favicon/`.

> *Human involvement: **low**. Dependency pruning and the description string are
> mechanical; the SCSS token merge against DE@HEAD's 98 files needs a designer's eye.*

---

## 3. Apps in DE@hash that are **absent** from AT

Short feature summaries, for the D3 decision.

### `fds_newsletter` — ✅ **re-adopted (D3), no signup surface**
Self-hosted newsletter subscription. Models: `Newsletter` (title/slug/sender
identity/visibility), `Subscriber` (per-newsletter, optional `user` FK, double
opt-in via `activation_code`, `subscribed`/`unsubscribed` timestamps,
`unsubscribe_method`, `email_hash`, plus `reference`/`keyword` campaign
attribution and taggable). Ships CMS plugins, a subscription form, a legacy
unsubscribe URL, an onboarding-schedule mechanism
(`NEWSLETTER_ONBOARDING_SCHEDULE` with the "three days ago but not Sundays" send
window), and `cleanup_subscribers` / `trigger_onboarding_schedule` tasks.
DE@HEAD has since added segments, archiving, subscriber import with data columns,
and admin actions to start flowruns.
**Germany-specific:** none structurally. The DE settings hardcode newsletter slugs
`"fragdenstaat"` / `"spenden"`.

### `fds_mailing` — ✅ **re-adopted (D3), for the `fds_donation` coupling**
Campaign email composition and sending. `EmailTemplate` (subject + text + a CMS
placeholder body edited with the `EmailActionPlugin`/`EmailSectionPlugin`/
`EmailStoryPlugin`/`EmailHeaderPlugin` set, bound to a froide `mail_intent`),
`Mailing` (template × newsletter, sender identity, ready/submitted/sending/sent
state machine, scheduled `sending_date`), `MailingMessage` (per-recipient row
linked to Subscriber **or Donor** or User, with sent/bounced tracking).
`send_mailing` / `continue_sending` tasks chunk the send. Also a public web archive
of past mailings. DE@HEAD added sender-domain validation and mjml rendering.
**Germany-specific:** none.

### `fds_blog` — ❌ **stays out (D3)**
Full editorial CMS: `Article` composed from mixins (`OrderedAuthorsEntry`,
`CategoriesEntry`, `TagsEntry`, `LanguageEntry`, `CMSContentEntry`,
`ArticleImageEntry`, `FeaturedEntry`, `DetailsEntry` with kicker/teaser/credits),
a separate `Author` model decoupled from `User`, translatable `Category` (parler),
Elasticsearch document, RSS feeds, Google-News sitemap, CMS apphook, and
`LatestArticlesPlugin`/`ArticlePreviewPlugin` with filtering by
category/author/tag/language.
**Germany-specific:** none. `ARTICLE_CONTENT_TEMPLATES` in DE names one German
template. AT stubbed `ARTICLE_CONTENT_TEMPLATES = []` rather than removing the
setting, so re-adoption is cheap.

### `fds_fximport` — ❌ **stays out (D3)**
Frontex-specific: logs into the Frontex PAD portal (`askfx.py`), solves its
captcha with a **local Torch model** (`captcha.py`, `FRONTEX_CAPTCHA_MODEL_PATH`),
pins the portal's CA (`pad_cadata.pem`), and imports the resulting documents onto
a FoiRequest. Single-purpose EU-agency scraper attached to DE's Frontex campaign.
Pulls in `torch`+`torchvision` — a very large dependency for one campaign.

### Also DE@hash-only, non-app
`templates/campaign/`, `templates/froide_crowdfunding/`,
`templates/legal_advice_builder/klageautomat_info.html`,
`templates/account/new_terms.html`, `templates/foirequest/emails/request_footer.txt`,
`theme/glyphosat.py`, `theme/cms_plugins.py`, `theme/admin.py`, `theme/locale/`.

### New in DE **since** the hash (not in either at the baseline)
- **`fds_easylang`** — "Leichte Sprache" (`de-ls`) as its own language code with
  dedicated stripped-down templates and a toggle button, deliberately kept out of
  `USER_LANGUAGES`. Austria has an equivalent accessibility expectation; this is
  the best-designed thing to copy.
- **`fds_events`** — event calendar: `Event` model with tags, apphook, CMS toolbar,
  `NextEventsCMSPlugin`.
- **`fds_paperless`** — Paperless-ngx bridge (filters/forms/views, no models) for
  pulling scanned post into the platform.
- Plus new external deps DE now uses: `froide-evidencecollection`,
  `froide-pressconference`, `froide-election`, `django-flowcontrol`,
  `django-datashow`, `django-cookie-consent`.

> *Human involvement: **none outstanding.** **D3** is settled (§0): newsletter and
> mailing return with no signup surface; blog and fximport stay out. The inventory
> above is retained as the description of what is being adopted, and as the record of
> what was declined.*

---

## 4. Apps in AT that weren't in DE@hash

Strictly speaking there are **no new AT Django apps**. What is AT-only:

### `fragdenstaat_at/scripts/`
Two one-shot bash DB-migration scripts (`2019-04-…`, `2021-12-…`) that rename
`auth_user`→`account_user`, fake-apply froide migrations, and de-duplicate users by
case-insensitive email across `foirequest_foirequest` / `foimessage` / `foievent`.
Historical record of the original fragdenstaat.at → froide data migration.
**Keep as documentation; they are not runnable today.** No German specifics.

### Root-level AT-only tooling
- `sync_froide_translations.py` (2026-08-17, uncommitted intent) — greps froide's
  `de` catalogue for `Open Knowledge`, `FragDenStaat.de`, `gelber Brief`, `Spende`,
  `IBAN`, `DE` and seeds a `fragdenstaat_at/locale/de_AT/` override file. Directly
  implements D4/D5: moving AT's string overrides out of the froide fork and into
  this repo. **Its target directory does not exist yet, and it reads froide from a
  hardcoded sibling path `../froide/`.**
- `.devcontainer/`, `compose-dev.yaml`, `devsetup.sh`, `Makefile`, `export_dev_db.py`,
  `test_export_*.sql` — a working local dev environment, which DE does not have in
  this form. **This is a real AT asset; do not lose it in a rebase.**
- `tests/` + `.github/workflows/ci.yml`.

### AT-only within shared apps
`RegularDonorsProgressBarCMSPlugin`, the legacy Row/Column/Container/SubMenu CMS
plugins, `HomepageHero`/`HomepageHow`, `theme/management/commands/update_georegion.py`,
`fds_cms/management/commands/export_fdscms.py`, and the templates listed in §2.7.

**Germany-specific details in AT-only code that still need adaptation:**
`update_georegion.py` is built around the **German ARS** (Amtlicher Regionalschlüssel)
hierarchy — `get_higher_ars()` hardcodes the 2/3/5/9/12-digit German key lengths.
For Austria the analogue is the 5-digit Gemeindekennziffer with a
Bundesland/Bezirk/Gemeinde hierarchy. The command as written cannot load Austrian
regions correctly.

> *Human involvement: **low**, except `update_georegion.py` which needs an Austrian
> data model. The dev-environment preservation is a checklist item, automatable.*

---

## 5. The plan

Phased so that each phase leaves a deployable tree. Each step is marked
**[AUTO]** (scriptable, low judgement), **[ASSIST]** (script produces a diff, human
reviews), or **[HUMAN]** (genuine design/legal decision).

### P0 — Freeze the ground truth *(≈½ day)*

1. **[DONE 2026-08-18]** `scripts/de_drift.py` — classifies every file under
   `fragdenstaat_at/` as identical / modified / at-only / de-only against a
   fragdenstaat_de checkout, applying the package rename first. Supports `--ref`,
   `--list <bucket>`, `--json`, and `--check-max-modified N` as a CI drift gate.

   **Measured, and the two reference points differ sharply:**

   | vs | identical | **modified** | at-only | de-only |
   |---|---|---|---|---|
   | DE @ `abe0781d` (baseline) | 243 | **57** | 51 | 255 |
   | DE @ HEAD (target) | 42 | **240** | 69 | 635 |

   The second row is the real P2 workload: **240 files to reconcile**, not 57. The
   57 is only how far AT drifted from where it forked. This is the strongest
   argument yet for **D2** — without configure-out, that 240 is what every future
   sync re-litigates. Re-run the script instead of hand-editing these numbers.
2. **[AUTO]** Same for `frontend/`, `pyproject.toml`, `package.json`, root config.
3. ~~Ratify D1.~~ **Settled: rebase onto DE@HEAD** (§0).
4. **[AUTO]** Tag the current AT tree (`pre-sync-2026-08`) and snapshot the
   production database schema — P3 depends on knowing exactly which migrations are
   applied in production.

### P1 — Port against upstream froide *(≈2 days, blocking)*

Do this **first**. Until AT builds against `okfde/froide@main`, every other merge
is a three-way merge against a moving fork. **Translations are explicitly excluded
from this phase** and deferred to P6.

5. **[DONE 2026-08-18]** Port against **upstream** `okfde/froide` from the start,
   with a one-command switch back to the fork: `./scripts/froide-source.sh
   okfde|fin|status` (§1c). froide is installed *editable* from `../froide`, so the
   switch is a checkout — no `uv sync`, no reinstall, and local devcontainer edits
   to `froide/settings.py` carry across untouched.

   ⚠️ **Translation work is deliberately NOT here — it is P6, at the end.** The
   `de_AT` relocation is the *last* step, not a prerequisite. Porting proceeds
   against upstream froide while froide keeps carrying `de_AT` as it does today.
6. **[HUMAN]** Upstream (or park on a clearly-named branch) the fax-transport work
   described in `../HANDOFF.md`. `froide/plan.md` §2.4 is still open and is why
   `froide-fax` carries a duplicated `send_foimessage_sent_confirmation`.
7. **[ASSIST]** `pyproject.toml` already declares `okfde/froide@main`; only the
   sibling checkout pointed at the fork, and step 5 fixed that. Keep unrelated
   changes out of `../froide`, and never commit its `froide/settings.py`
   devcontainer edits. **Verified:** the full migrate against upstream applies 22
   migrations cleanly (§1b). The fork's `foirequest/0076_alter_foimessage_kind` does
   not exist upstream, so upstream verification runs need a *fresh* scratch DB.
8. *(moved to **P6** — see below. Language configuration changes land last.)*

### P2 — Rebuild the AT layer against DE@HEAD *(≈3–4 weeks)*

9. **[ASSIST]** **D3 execution.** Add `fds_newsletter` and `fds_mailing` (renamed)
   back to `INSTALLED_APPS`; restore `Donor.subscriber` and `SetupMailingMixin` in
   `fds_donation`; set `hide_contact=True` on every donation form; **and neutralise
   `services.py:398-400`** (§0), without which `?newsletter` still subscribes.
   Publish no newsletter CMS plugin. `fds_blog` and `fds_fximport` stay out.
10. **[ASSIST]** Adopt DE@HEAD's `pyproject.toml` and `[dependency-groups]` per
    **D6**, subtracting packages for apps AT will not run (`fds_blog`,
    `fds_fximport`, `froide-food`, `froide-fax`, `froide-govplan`,
    `froide-crowdfunding`, `froide-legalaction`, `torch`/`torchvision`). Keep the
    `fds_newsletter`/`fds_mailing` deps per **D3**. Produce a fresh `uv.lock`.
11. **[HUMAN + ASSIST]** Per **D2**, rewrite `settings/base.py` as *DE@HEAD's file
    plus an explicit AT override block* — configuration, not commented-out code. A script can produce the starting diff from §2.5;
    a human decides each retained/dropped setting. Specifically resolve:
    the duplicated `recipient_blocklist_regex`, `target_countries`,
    `TEXT_ADDITIONAL_PROTOCOLS`, the dead `pseudonym` content URL, and DE's
    `USER_LANGUAGES`/`de-ls` split vs AT's single-language CMS config.
12. **[AUTO]** Take DE@HEAD's `fds_cms`, `fds_ogimage`, `theme` wholesale.
    Re-apply the AT delta: `HomepageHero`/`HomepageHow`, the legacy structural
    plugins (until P3 retires them), `export_fdscms.py`, AT template overrides.
    Drop AT's hand-ported CMS-5 code — DE@HEAD's is the maintained version, and
    it fixes AT's broken `listeners.py` (§6) for free.
13. **[HUMAN]** `fds_donation`: take DE@HEAD, then re-apply the AT layer. Three are
    the **permanent local patches D2 accepts** (marked 🔁 — re-apply every sync) —
    IBAN/BIC/creditor-ID, 🔁 `DONATION_SITE_NAME_OVERRIDE`, 🔁 `MIN_AMOUNT=2`,
    `country="AT"`, `DONATION_PROJECTS=["FOI"]`, 🔁 the Erste-Bank/George importer in
    `external.py`, and `RegularDonorsProgressBarCMSPlugin` (rewrite its
    `get_donor_count()` as a single ORM query while you are in there).
    Re-enable `update_direct_debit` against Austrian reference formats.
14. **[AUTO]** Adopt DE@HEAD's `frontend/`, re-applying AT's `base.scss`,
    `globalvars.scss`, StixTwo and dropdown tokens. Prune the dead
    `froide_campaign`/`exam`/`food`/`legalaction` JS deps and fix `package.json`'s
    description and `favicon` path.
14a. **[AUTO]** **Footer comparison gate.** `tests/test_footer.py` compares the
    rendered footer against `tests/snapshots/footer_live.json`, captured from the
    live https://fragdenstaat.at/ on 2026-08-18 *before* any sync work. It asserts
    the FOI/OKF credit and Easyname sponsorship copy, the three sponsor logos
    through the static pipeline, and the `content_urls` legal links. Run it after
    **every** template or settings step in P2 — the footer is the smallest markup
    that exercises the AT identity end to end, so a DE template winning over the AT
    override shows up here first.
    Verified to fail correctly: removing `templates/footer.html` fails 3 of 6.
    Needs no database, CMS fixtures or services, so it stays usable mid-port.

15. **[ASSIST]** Re-derive the AT template overrides against DE@HEAD's templates.
    Delete `snippets/temp.html`. Rewrite `base.html`'s `metadescription` for the
    Austrian IFG. Drop DE's `google-site-verification` token.
16. **[AUTO]** Preserve `.devcontainer/`, `compose-dev.yaml`, `devsetup.sh`,
    `Makefile`, `export_dev_db.py`, `scripts/`, `tests/`, `.github/` — verbatim.

### P3 — Migrations *(revised down; ≈1 week + staging, was 1–2 weeks)*

§1a changes this phase materially. Production is **fully migrated against AT's
pinned dependencies** and only ~20 froide migrations behind upstream `main`, so
the third-party surface is nearly free. The remaining risk concentrates in exactly
two places: `fds_cms` lineage (**D8**) and the third-party *major* bumps that
tracking DE implies.

16a. **🔴 Do this first, before P1.** Per **D9**: leave `0005` as it is and run
    `manage.py migrate --fake fds_cms 0005` on production. Fresh and post-June-2026
    dev databases run it for real. ⚠️ Must **not** be faked on a database that
    lacks the columns — check `information_schema` first. Add to the deploy runbook.

17. **[n/a]** **D8** chose (b) for `fds_cms`: keep AT's squashed graph and add DE's
    model changes as AT `0006, 0007…`. **There is no graph reconciliation to do.**
18. **[ASSIST]** `fds_donation`: **D8** chose (b) here too. Keep AT's `0044` as head
    and forward-port DE's `0045–0079` model changes as new AT migrations. Includes
    the `Donor.subscriber` `AddField(null=True)` that **D3** now requires (§1a: no
    backfill needed — the column does not exist yet).

18a. **[HUMAN]** Budget for the third-party *major* bumps that tracking DE
    implies, each of which runs migrations over live CMS content:
    `djangocms-alias` **2.0.4 → ≥3.1.0** (major), `djangocms-versioning`
    2.3.1 → ≥2.5.1, `django-cms` 5.0.2 → ≥5.0.5. These are a bigger data risk
    than the fragdenstaat_de sync itself and deserve their own rehearsal.
19. **[AUTO]** `Donor.subscriber`: the live table has **no** `subscriber_id`
    column (§1a). Under D3(a)/(c) this is a plain `AddField(null=True)` against a
    populated table — cheap, no backfill, no downtime. Under D3(b) there is
    nothing to do at all.
20. **[ASSIST]** Retire the legacy Row/Column/Container/SubMenu plugins with a data
    migration onto their `djangocms_frontend` equivalents — **17 plugin instances**
    (§1a), against 43 already on the modern grid. Contained enough to script and
    verify; no content rebuild required.
20a. **[ASSIST]** Decide the fate of the 24 orphaned `bootstrap4_*` tables and
    the other dead app schemas (§1a) — drop them, or leave them and document why.
    Must be settled before DE code that reuses any of those app labels lands.

20b. **[HUMAN]** Measure `foirequest_*`, `account_user`, `fds_donation_*` and
    `froide_payment_*` row counts on production. They are invisible in the dump
    and they, not the CMS, determine the migration window.

21. **[ASSIST]** Rehearse the whole thing against a production-shaped dump.
    `export_dev_db.py` already produces one, privacy-preserving and schema-complete
    — **this is the single most valuable asset AT has for this programme** and it
    makes every step above cheap to dry-run.

### P4 — Austrian donation-receipt compliance *(independent track; ≈2–4 weeks)*

22. **[HUMAN]** Design and build the Austrian **Spendenabsetzbarkeit** flow to
    replace `zwb.html` / `get_zwb_data()` / `send_jzwb_mailing_task` /
    `backup_jzwb_pdf_task`: FinanzOnline electronic reporting rather than a German
    §50 EStDV PDF. Until this lands, un-hide the `receipt` form field only if there
    is something behind it.
23. **[HUMAN]** Confirm `remote_filing.py` / `DONATION_BACKUP_URL` point at
    Austrian infrastructure.

### P5 — Establish a repeatable sync *(≈2 days, do it while P2 is fresh)*

24. **[HUMAN]** Land the D2 mechanism so AT's delta is configuration, not comments.
25. **[AUTO]** Commit the P0 inventory script as a CI check that reports drift
    from DE `main`, so the next sync is measured in days.
26. **[AUTO]** Record the new baseline commit in this file and delete the
    commented-out DE code that D2 makes redundant.

---

### P6 — Translations: relocate `de_AT` out of froide *(≈1 week, LAST)*

**Deliberately last.** Until this lands, froide keeps carrying the 590 `de_AT`
msgids (505 translated) exactly as it does today, and nothing in P1–P5 depends on
that changing. Doing it earlier would mean re-syncing the catalogue against a
moving target every time a template or form label changes during P2.

27. **[HUMAN]** Fix `sync_froide_translations.py`'s hardcoded `../froide/` path,
    then run it against the *final* post-sync string set — not the current one.
28. **[HUMAN]** Fill in the `de_AT` msgstrs and land `fragdenstaat_at/locale/de_AT/`.
29. **[ASSIST]** Apply the **D4** language configuration: keep
    `LANGUAGE_CODE="de-at"` and `locale/de/` as the fallback, with `locale/de_AT/`
    as the override layer. Reconcile against DE's `USER_LANGUAGES` / `de-ls` split.
30. **[HUMAN]** **D5 exit criterion:** AT's catalogue fully replaces
    froide's `de_AT` with no regression. Then drop `de_AT` from the froide fork and
    confirm nothing else keeps AT on `fin/froide`.
31. **[AUTO]** Re-run the footer test and the §1b migrate check under `de-at` —
    translation changes are exactly the kind of thing that silently alters
    user-visible copy.

## 6. Defects found during the analysis

Independent of the merge; several are live bugs today.

| # | Where | Problem |
|---|---|---|
| 1 ✅ | `fds_cms/listeners.py` | **FIXED on this branch.**  Uses `search_instance_save`, `search_instance_delete`, `saved_file`, `Image`, `generate_thumbnails` — **none are imported**. The module would `NameError` on import. It is only inert because `apps.ready()` has `# from . import listeners` commented out. Net effect: **CMS page (un)publishing no longer updates the search index.** |
| 2 | `fds_cms/apps.py` | `search_registry.register(add_search)` removed → **CMS help pages are missing from site search**. `add_search`, `reverse`, `NoReverseMatch`, `_`, `BytesIO`, `ContentFile` are now unused imports/dead code. |
| 3 ✅ | `fds_cms/apps.py` | **FIXED on this branch** (dead helper removed).  Defines `async_optimize_thumbnail()` referencing `.tasks.optimize_thumbnail_task` — **`fds_cms/tasks.py` does not exist**. Dead, but it will bite whoever re-enables it. |
| 4 ✅ | `fds_donation/cms_plugins.py:107` | **FIXED on this branch.**  `from fragdenstaatat.fds_mailing.utils import …` — **typo, missing underscore**. Inside `render_text()`, so it only fires when a donation plugin is rendered into an email. |
| 5 | `fds_donation/admin.py` | The `send_mailing` action still returns *"Prepared mailing of emailable donors with {count} recipients"* while the `MailingMessage.objects.bulk_create()` is commented out. **Reports success, does nothing.** |
| 6 | `fds_donation/tasks.py` | All five tasks registered as `fragdenstaat_de.fds_donation.*` (see §2.6). |
| 7 | `fds_donation/templates/…/pdf/zwb.html` | Entire `<body>` wrapped in `{% comment %}`. **Generates a blank PDF.** |
| 8 ✅ | `settings/base.py` | **FIXED on this branch** (duplicate removed; verified the pattern still blocks `.local`/`noreply`/`postmaster` and passes `amt@wien.gv.at`). Was: `recipient_blocklist_regex` — AT prepended an unescaped copy of the pattern but left DE's; Python implicit string concatenation glues them, producing one dead alternation branch (`.*\.local$.*\.de-mail\.de$`, unmatchable) and a fully duplicated blocklist. Verified still functionally correct — the duplicate copy covers every case — but it is a trap for the next editor, and the whole list is German (`de-mail.de`, BND, `bahn.de`, `jobcenter-ge.de`) with nothing Austrian in it. |
| 9 ✅ | `settings/base.py` | **FIXED on this branch — and it was hiding a real bug.** The hand-edited `{"*": {...}}` form omitted `src`, so nh3 **stripped the `src` from every `<iframe>` and `<embed>`**, silently breaking any video embed in CMS text. Latent only because AT currently has 0 such plugins. Now uses DE's per-tag shape (which includes `src`), and drops the deprecated `TEXT_ADDITIONAL_TAGS` — verified byte-identical sanitiser output for the old cases, `src` now preserved, the `bank:` protocol still allowed, `manage.py check` clean. ⚠️ DE's config additionally permits `form`/`input`/`button`/`textarea`; **deliberately not adopted** — it widens what CMS editors can inject. Decide in P2. |
| 10 ✅ | `settings/development.py` | **FIXED on this branch.**  `print('devtemplates', TEMP)` in the `TEMPLATES` property — fires on every settings access. |
| 11 ✅ | `fds_donation/external.py` | **FIXED on this branch.** `\|` binds tighter than `>=`, so the filter read `amount >= (0 \| contains(...))` — a comparison against a boolean. Measured impact on a sample frame: it silently dropped **every FDS-referenced transfer under €1 and every FDS refund**. Now parenthesised, with `na=False` (`reference` is only filled in on the following statement). Stray debug `print` in the import loop removed. |
| 12 ✅ | `templates/account/profile.html`, `foirequest/show.html` | **FIXED on this branch.**  `ogimage_url` commented out but `<meta property="og:image" content="{{ og_image_url }}" />` left in → **empty og:image on every profile and request page.** |
| ~~13~~ | `settings/production.py` | ~~`frag.denstaat.at` looks like a bad search-and-replace.~~ **Withdrawn — verified 2026-08-18.** Both hosts are real and serving: `https://static.frag.denstaat.at/static/img/foi_logo.e81e7e609d90.png` → HTTP 200, `https://media.frag.denstaat.at/` → HTTP 200. The live footer references them. Not a defect. |
| 14 | `fds_donation/cms_plugins.py` | `RegularDonorsProgressBarPlugin.get_donor_count()` iterates every `Donor` in Python (§2.2). |
| 15 ✅ | `pyproject.toml` | 🔴 **The test suite could not run at all.** `time-machine==2.9.0` uses `uuid._load_system_functions`, removed in Python 3.13 — it fails at pytest *plugin load*, so every test errors before collection. **Fixed on this branch:** `time-machine>=2.16`. |
| 16 ✅ | `pyproject.toml` | 🔴 Same class: `factory-boy==3.2.1` predates `Meta.skip_postgeneration_save`, which froide's `UserFactory` uses — `tests/conftest.py` fails to import, so nothing runs even with #15 fixed. **Fixed on this branch:** `factory-boy>=3.3`. |
| 17 ✅ | `tests/fixtures/cms.json` | 🔴 The CMS fixture was written for **django-cms 3**: it contains `cms.treenode` and `cms.title`, both removed in cms 4. `test_web.py` and `test_admin.py` died with `Invalid model identifier: cms.treenode`. Masked until now by #15/#16. **Fixed on this branch:** regenerated from the production extract (`cms.page`/`pagecontent`/`pageurl`/`placeholder` + `djangocms_versioning.version` + the scrubbed dev user). *(An earlier draft blamed `FIXTURE_DIRS`; that was a misdiagnosis caused by leaked `DJANGO_CONFIGURATION=Dev` in the analysis shell — `FIXTURE_DIRS` is correct.)* |
| 18 ✅ | `fds_cms/views.py` | 🔴 `from cms.models import Title` — removed in django-cms 4. The 2026 hand-port updated `documents.py` to `PageContent` but **missed `views.py`**, so `CMSPageSearch` raises `ImportError` on import: the CMS search view cannot run. Latent in production only because `fds_cms.urls` is not routed there. **Fixed on this branch** (`PageContent`), matching DE. Third casualty of the hand-port, after `listeners.py` (#1) and `apps.py` (#2). |
| 19 ✅ | `tests/test_misc.py` | 🔴 Imports `djangocms_text_ckeditor.cms_plugins`, which fails on cms 5 (`No module named 'cms.utils.copy_plugins'`). A module-level import, so it broke **collection of the entire suite** even though the test itself is `@unittest.skip`-ped. **Fixed on this branch:** import from `djangocms_text`, the package actually in `INSTALLED_APPS`. |
| 21 ✅ | `fds_cms/documents.py` | 🔴 **The CMS search index could not be built at all.** `select_related("page__node")` — `Page.node` was removed in django-cms 4 (`FieldError`). Two more in the same path: `page.placeholders` moved to `PageContent`, and the `MAX_CHARS` slice truncated HTML *before* `strip_tags` instead of after. **FIXED:** adopted DE's version wholesale (AT's was DE's pre-cms4 copy with no AT-specific content; `PLACEHOLDERS_SEARCH_LIST` verified unused). Fourth hand-port casualty. |
| 22 ✅ | `fds_cms/utils.py` | 🔴 `get_request()` calls `CMSToolbar(request)` but the hand-port deleted the import — `NameError` on every indexing run. **FIXED:** deferred import inside the function, as DE does (it must not be imported at module level during app loading). Fifth hand-port casualty. |
| 23 ✅ | `settings/{base,test,production}.py`, `.devcontainer/compose.yaml` | 🔴 **Elasticsearch was unreachable in every environment.** elasticsearch-py 8 rejects a bare `host:port` with `ValueError: URL must include a 'scheme'…`, and every host setting was schemeless (`localhost:9200`, `elasticsearch:9200`). **FIXED:** an `es_hosts()` normaliser in `base.py` that prepends `http://` when no scheme is given, so existing deployments and running containers keep working without changing their env vars. |
| 24 | devcontainer | The Elasticsearch image is **7.15.0** (`deps/elasticsearch/Dockerfile`) while the pinned client is **8.15**. They interoperate for indexing and search today, but this is an unsupported pairing and DE runs ES 8. Align during **D6**. |
| 20 | `pyproject.toml` | `djangocms-text-ckeditor==5.1.1` is still pinned but is unused (settings use `djangocms_text`) **and** incompatible with cms 5. Dead weight; drop it under **D6**. |

> *Human involvement: **low to fix, required to prioritise.** #1, #5, #7, #8 and #12
> are user-visible or silently-wrong today and are worth fixing **before** the merge,
> so the merge is not blamed for them.*

---

## 7. Automation summary

| Analysis / work area | Can be automated | Needs a human |
|---|---|---|
| File-level inventory & drift detection | ✅ fully | — (**D1 settled**) |
| Branding / IBAN / domain substitutions | ✅ fully (already correct — preserve) | spot-check |
| Dependency file adoption (**D6 settled**) | ✅ mostly | — (drop list fixed by D3, see P2 step 10) |
| Frontend dep pruning, `package.json` cleanup | ✅ fully | — |
| Locating dead code from disabled apps | ✅ (grep imports of disabled apps) | delete-vs-keep |
| `settings/base.py` reconstruction | ⚠️ produces the diff | ✅ every policy line |
| Template override re-derivation | ⚠️ mechanical part | ✅ all copy & legal text |
| `fds_cms` / `theme` / `fds_ogimage` adoption | ✅ mostly | which new DE plugins to take; 17-row legacy retirement |
| `fds_donation` adoption | ❌ | ✅ throughout |
| **Migration reconciliation (P3)** | ⚠️ **reduced by D8** — no graph reconciliation; forward-porting models is scriptable | ✅ review each forward-ported migration |
| `fds_cms/0005` fix (D9) | ✅ one `--fake` command | ✅ verify columns exist first |
| **Austrian donation receipts (P4)** | ❌ | ✅ legal + finance design |
| Newsletter/mailing re-adoption (**D3 settled**) | ✅ mostly — reinstall apps, restore FK, set `hide_contact` | ✅ verify the `?newsletter` bypass is closed |
| Defect list §6 | ✅ fixes are small | prioritisation |

---

## 8. Effort shape

| Phase | Rough size | Blocking? |
|---|---|---|
| **P3 step 16a — `--fake fds_cms 0005` on prod** (D9) | **½–1 day** | **🔴 blocks all deploys, merge or not** |
| P0 inventory | ½ day | yes, trivially |
| ~~P1 froide detach~~ **✅ done 2026-08-18** (§1c) | — | was blocking |
| **P1b test harness (D7)** — ⚠️ **partly done 2026-08-18: suite now green** (§1d) | ~3 days left | **yes — D7 puts it before the code sync** |
| P2 rebuild AT layer — **D6 ✅ done (§1e)**; D1/D2/D3 remain | 3–4 weeks | ⚠️ **D3 blocked behind D10** |
| P3 migrations (D8) | ~1 week + staging | risk now concentrated in the alias/versioning bumps |
| P4 AT donation receipts | 2–4 weeks | independent track |
| P5 repeatable sync | 2 days | — |
| **P6 translations / `de_AT` relocation (D4, D5)** | **~1 week** | **LAST — by instruction** |

The critical path is **16a → P1b → P2 → P3 → P6**, roughly **7–9 weeks**, with P4
(2–4 weeks) running alongside from day one — it is the only part gated on external
tax/legal input, so start it immediately.

**Translations moved to the end (P6).** Relocating `de_AT` before P2 would mean
re-syncing the catalogue every time a template or form label changed during the
port. froide keeps carrying `de_AT` until then, exactly as today; nothing in P1–P5
depends on that changing.

**D7 adds ~1 week (P1b) before any visible merge progress.** That is deliberate:
P2 and P3 are where regressions get made, and D8's forward-port approach means
`fds_cms` and `fds_donation` schema changes are hand-written rather than inherited.

**What the database evidence changed:** P3 came down from "highest risk, 1–2 weeks"
to roughly a week. Production is current with its pinned deps and only ~20 froide
migrations behind upstream — the multi-year gap is in the *code*, not the *data*.
And AT's `fds_cms` content footprint turns out to be **21 plugin instances out of
103**, the rest sitting in third-party tables a lineage change never touches.

In exchange it surfaced one blocker that outranks every decision here
(`fds_cms/0005`, which blocks all deploys today), and one decision the code alone
did not reveal (**D8**).

The overall recommendation — rebase onto DE@HEAD — stands, with the refinement
that **code lineage and migration lineage should be decided separately, per app**.

*One earlier suggestion is withdrawn:* a draft of D8 floated rebuilding the CMS
pages by hand. Measuring the plugin footprint showed that to be both unnecessary
and worse than the alternative. **No content rebuild is part of this plan.**
