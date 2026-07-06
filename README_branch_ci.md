# CI fixes: workflow rewrite + test suite repairs

This branch makes both GitHub Actions jobs (`lint`, `test`) run again and fixes
everything that kept the test suite from passing on the current stack.
Verified locally end-to-end: `make testci` (4 passed, 1 skipped, exit 0),
`ruff check`, `pnpm lint`, and `pnpm run build` all green.

## The workflow (`.github/workflows/ci.yml`)

The old workflow predated the repo's current tooling (it used the deprecated
`actions/cache@v1`, flake8/black/isort, yarn, pip-tools and a
`requirements-dev.txt` that no longer exists). It was rewritten modeled on
upstream fragdenstaat_de's CI:

- **lint**: `uvx ruff check` (matches `make test`) + eslint via pnpm.
- **test**:
  - Python **3.13 only** (per `UV_PYTHON="3.13"` in devsetup.sh and
    `requires-python = ">=3.13"` in pyproject.toml)
  - `uv sync --locked` instead of pip-tools/`requirements-dev.txt`
  - pnpm 9.15 (pinned; devsetup.sh requires it) + node 22 (matches devcontainer)
  - services started via `docker compose -f compose-dev.yaml up --wait`, so CI
    uses the same Postgres 16/PostGIS and the custom Elasticsearch image
    (German decompounder) as local development
  - `DATABASE_URL` points at the compose Postgres on port 5432 — the test
    settings' default port 5436 doesn't exist in CI

## What else had to change for CI to actually pass

The workflow file was the small part — the suite itself was broken on the
current dependency stack:

### Dependency bumps (`pyproject.toml`, `uv.lock`)

- `time-machine` 2.9.0 → 2.19.0 — 2.9.0 cannot even be imported on
  Python 3.13 (`uuid._load_system_functions` was removed)
- `factory-boy` 3.2.1 → 3.3.3 — froide's factories use the
  `skip_postgeneration_save` Meta attribute, which needs ≥ 3.3

### Ruff fixes

- 13 unused imports auto-fixed (including in two fds_donation migrations)
- `fragdenstaat_at/fds_cms/listeners.py`: added the missing imports
  (`search_instance_save`/`search_instance_delete` from `froide.helper.tasks`,
  taken from upstream fragdenstaat_de). Removed the `generate_thumbnails_async`
  handler: it referenced a `generate_thumbnails` task that does not exist in
  this fork (upstream has it in `fds_cms/tasks.py`, which was removed here),
  and the whole module is dead code anyway — its import in `apps.py` is
  commented out.
- `fragdenstaat_at/fds_cms/utils.py`: added the missing `CMSToolbar` import,
  lazily inside `get_request()` like upstream does, because
  `cms.toolbar.toolbar` touches the Django app registry at import time.

### django-cms 5 compatibility

- `fragdenstaat_at/fds_cms/views.py` used `cms.models.Title`, removed in
  django-cms 4/5 → now `PageContent`, matching upstream and `documents.py`.

### Missing migration

- The fds_cms plugin models had gained `attributes`, `tag_type` and
  `dialog_attributes` fields with no corresponding migration — every
  page-rendering test failed on missing columns. Generated
  `fragdenstaat_at/fds_cms/migrations/0005_borderedsectioncmsplugin_attributes_and_more.py`.

### Tests rewritten off the CMS 3-era fixture

- `tests/fixtures/cms.json` was a django-cms **3.x** dump (draft/public page
  pairs, `cms.title`, `cms.treenode`, `cms.staticplaceholder`) and cannot be
  deserialized under CMS 5 — deleted.
- `tests/test_web.py` now creates and publishes a home page programmatically
  via `cms.api.create_page` + djangocms-versioning instead of loading the
  fixture. (`test_homepage` follows the language-prefix redirect, since the
  CMS URLs sit inside `i18n_patterns`.)
- `tests/test_donation.py` turned out not to need the fixture at all; the
  fixture-loading `django_db_setup` override was removed.
- Upstream fragdenstaat_de dropped these fixture-based tests entirely, so
  there was no template to port.

### Test settings (`fragdenstaat_at/settings/test.py`)

- `ELASTICSEARCH_DSL` hosts now honor the `DJANGO_ELASTICSEARCH_HOSTS` env var
  like `base.py` does. CI behavior is unchanged (defaults to
  `localhost:9200`), but tests are now runnable inside the devcontainer where
  Elasticsearch lives at `elasticsearch:9200`.

## Running the tests locally (devcontainer)

- The devcontainer shell exports `DJANGO_CONFIGURATION=Dev` and
  `DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.development`, which
  **override pytest.ini's defaults** if you run `pytest` directly — use
  `make testci` / `make test`, which export the Test settings.
- Pass the DB explicitly, since the test settings' default port doesn't match
  the compose setup:

  ```sh
  DATABASE_URL=postgis://fragdenstaat_at:fragdenstaat_at@db:5432/fragdenstaat_at make testci
  ```

- Playwright needs its browser + system libraries once per container:
  `playwright install chromium` and (the pinned playwright's
  `install-deps` package list is outdated for Debian trixie)
  `sudo apt-get install -y libxcomposite1 libxdamage1 libxfixes3 libxrandr2
  libasound2 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libcups2
  libdbus-1-3 libdrm2 libgbm1 libxkbcommon0`.
- Translations must be compiled or the translated URL patterns 404:
  `python manage.py compilemessages -i node_modules`.

## Note

The new migration
`fragdenstaat_at/fds_cms/migrations/0005_borderedsectioncmsplugin_attributes_and_more.py`
is a new file — make sure it gets `git add`ed to the branch.
