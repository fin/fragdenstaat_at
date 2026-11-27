# Lessons for the next DE → AT sync

Written after P7 (DE@`b70ab730` + okfde/froide@`65bdbb35`, Nov 2026). `MERGE_PLAN.md`
has the full P7 record. This file holds only what to do differently, or keep
doing, next time. Each point names the mistake or near-miss it comes from.

## 1. Know the baseline before planning anything

- **Diff against what production runs, not against a branch name.** Production
  runs `dev` at a specific commit. Ask for it, or read it from the deploy, and
  write it at the top of the plan. In P7, both the plan and the runbook said
  "this deploy renames the Celery tasks". The rename (`e07f8e5`) was already
  live on `dev@55ac7c4`. Comparing with `master` or the previous sync branch
  would have made a no-op look like a migration step.
- **Check production state against the live system, not fixtures.** Use the
  `django_celery_beat` admin list, live help URLs and similar. `cms.json` is a
  stale dev fixture. It made a working `content_urls` entry look broken, and
  hid the one that really 404'd (`help_request_public`). A `GET` against
  fragdenstaat.at settles it.
- **Take DE and froide together.** Move froide to the exact commit DE's lock
  pins. DE's template, a11y and breadcrumb commits pair with froide changes,
  and a half-step tests a combination nobody runs.

## 2. Dependencies: own step, frozen installs, both lockfiles

- **Order: dependencies first, one commit each, suite green after each. Then
  DE's code.** This keeps "upstream moved" breakage apart from "we ported it
  wrong" breakage.
- **Every `package.json` change needs a regenerated `pnpm-lock.yaml` in the
  same commit.** The P7 merge commit raised eight ranges (Vite 7, eslint,
  typescript, sass, postcss, prettier, vue, vite-plugin-dev-manifest) and left
  the lockfile alone. CI's frozen install failed with
  `ERR_PNPM_OUTDATED_LOCKFILE`. Local `pnpm install` is not frozen, so the
  local test run passed. Before pushing, run what CI runs:

  ```sh
  pnpm install --frozen-lockfile
  uv sync --locked
  ./scripts/sync-editables.sh      # both commands above revert the sibling links
  ```

- **A raised floor can need a peer bump that DE made in a separate commit.**
  `@vitejs/plugin-vue` 5.x has no Vite 7 peer support. DE had moved it to
  `^6.0.7` in one of the "Update dependencies" commits the sync skips. After
  raising floors, check `pnpm install` for peer warnings and compare
  `package.json` with DE's line by line, not only the ranges the merged
  commits touched.
- **Refresh the lock towards DE package by package, never with a blanket
  `--upgrade`.** The method that worked: temporary `==` constraints for DE's
  versions, then `uv lock -P <pkg>` for each registry package, then a plain
  `uv lock` with the constraints removed. A blanket `uv lock --upgrade` moves
  the git pins off their commits (froide, froide-payment, froide-fax,
  filingcabinet). It also overshoots DE into majors nobody on this stack runs
  (sentry-sdk 3, pillow 13, dateutil 4, reportlab 5, pypdf 7). Do the same for
  the frontend.
- **Explicit caps stay explicit.** `django-payments<4` is still needed:
  froide-payment imports `StripeProvider`, which 4.0 removed. DE stays on 3.1
  only because its lock happens not to move. Before lifting any cap, check why
  it is there (§9.9).
- **Compare migration sets by installing the old and new wheels** (`pip
  download` into a scratch dir). Don't trust changelogs. In P7, third-party
  packages added no migrations, and froide's edits to historical `document`
  migrations only changed dependencies. Expected `makemigrations --check`
  noise: `djangocms_alias`, `contractor`, `sortabletable`.

## 3. Local test runs that lie

- **`uv sync` and `pnpm install` silently replace the editable sibling
  checkouts** with the pinned copies. Run `./scripts/sync-editables.sh` (or
  `--check`) before trusting a test run. After the P7 lock refresh, five
  failures came only from this.
- **Stale `.mo` files.** Compile catalogues whenever a `.po` changes:
  `python manage.py compilemessages -i node_modules -i .venv`. CI compiles
  them. `tests/test_at_translated_placeholder.py` fails on purpose when a `.mo`
  is older than its `.po`.
- Run pytest with `env -u DJANGO_SETTINGS_MODULE -u DJANGO_CONFIGURATION`
  (CLAUDE.md).

## 4. Merging code

- **Review clean three-way merges too.** The froide-fax auto-merge raised no
  conflict, yet it silently broke `send_fax_telnyx`'s return value. Every
  fork merge gets a test run against the new upstream, and a regression test
  for whatever it broke.
- **Take unused DE code as-is when it keeps files identical.** For example,
  the gift programme commits. Ripping it out would cost a migration and raise
  drift in five files on every future sync.
- **Skip list to recheck every time:** apps absent per D3 (`fds_blog`,
  `fds_easylang`, `fds_events`, `fds_fximport`), the IFG banner, the
  German-specific redaction (online-projektportal.de), the Democracy menu link,
  and the multi-site `CMSSiteBase` settings. AT is single-site.
- **Security-relevant DE changes get adapted, not copied.** DE's donation embed
  drops X-Frame-Options. AT's version fails closed and uses a per-page
  `frame_ancestors` allowlist.
- **Re-measure drift with `python scripts/de_drift.py`** and re-tighten
  `--check-max-modified` in the same branch. Before P7 the count had crept
  over the gate unnoticed while CI wasn't running.

## 5. Data migrations and live data

- **No live donation data goes through AI tooling** (decided 2026-11-26). Split
  the rehearsal. Claude rehearses on synthetic data that covers every shape
  AT's code has ever written. A human runs `docs/runbooks/p7-deployment-test.md`
  (or its successor) on a staging copy. That checklist reports counts and
  types, never values.
- **Never reuse DE's data migrations without checking AT's data shapes.** DE's
  hstore → JSON `0082` would have misparsed AT's `;`-joined `ibans` strings and
  turned numeric `banktransfer_reference` values into ints. Look up every
  writer of the field in AT's history first.
- A migration that drops a column needs a pre-migration dump to roll back to.
  Put it in the runbook.

## 6. Translations

- **Before writing any German, check `de_AT` and DE's catalogue.** In P7 I
  drafted `de` German for strings that already had AT wording in `de_AT`, and
  had to back it out. Strings that look untranslated are often DE strings
  whose msgid AT changed slightly.
- **Count plurals correctly.** For a plural entry `msgstr` is empty and the
  text is in `msgstr_plural`. Checking `if entry.msgstr` overcounted the
  untranslated strings (25 reported, 19 real).
- **Keep AT's msgids identical to DE's** so DE's German applies:
  - Use `{% blocktrans asvar x %}…{% endblocktrans %}{{ x|linebreaksbr }}`
    rather than adding `<br/>` to the msgid.
  - Use `lazy(fn, str)` rather than `gettext_lazy(...) % arg`. Formatting a
    lazy proxy with `%` evaluates it once, at import.
- **Strings translated only in `de_AT` get a `TRANSLATED IN AT` marker in `de`**,
  followed by the msgid's placeholders, because `msgfmt -c` rejects a msgstr
  that drops them. DE's makemessages hook rejects empty `de` msgstrs.
  `tests/test_at_translated_placeholder.py` makes sure no marker is ever
  served.
- **Catalogue priority is per directory, not "de_AT beats de".**
  `LOCALE_PATHS` is merged last. A directory without `de_AT` contributes its
  `de` at full priority. Adding a `de_AT` to an app directory can therefore
  lose to a marker elsewhere. Run the served-text test.
- **Don't copy DE's `.po` files.** Re-sync with the P6 scripts.

## 7. Before declaring the sync done

- [ ] `pnpm install --frozen-lockfile` and `uv sync --locked` succeed on a clean checkout
- [ ] `scripts/check_fork_pins.py` passes
- [ ] full suite green with the editables re-linked and catalogues compiled
- [ ] `scripts/verify_render.py` after froide template changes
- [ ] drift re-measured, gate tightened
- [ ] runbook rewritten against production's actual commit, not the plan's assumptions
- [ ] every "verified" claim in MERGE_PLAN checked against live, not fixtures
