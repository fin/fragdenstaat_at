# fragdenstaat_at

Django/froide deployment for FragDenStaat.at. Sibling checkouts under
`/workspaces/fds_at/` (`froide`, `fragdenstaat_de`, `django-filingcabinet`, …)
are the upstreams this project extends; `fragdenstaat_de` is the reference
implementation most AT code is ported from.

## Django templates

**Never use `{# … #}` for a multi-line comment.** Django's tokenizer is
`tag_re = re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})")` — no `re.DOTALL`, so `{# … #}`
only matches within a single line. A multi-line one is not tokenized as a comment
at all and the text is emitted verbatim into the rendered HTML. It raises no
error and `get_template()` still parses it, so it survives any check that only
greps the output for expected tags.

Use `{% comment %} … {% endcomment %}` for anything spanning more than one line.
Single-line `{# … #}` is fine.

## Settings

Uses `django-configurations`: settings live as attributes on the
`FragDenStaatBase` class in `fragdenstaat_at/settings/base.py`, not at module
level. Bootstrapping needs both env vars, or attribute lookups fail confusingly:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fragdenstaat_at.settings.development")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")
import configurations; configurations.setup()
```

Plain `django.setup()` appears to work but only sees module-level names.

## URLs

Public URL segments are translated via `pgettext_lazy("url part", …)`. The active
catalogue is `de` (`LANGUAGE_CODE = "de-at"`; `de_AT` is sparse and falls back to
`de`), so routes resolve to German paths — `/anfrage/<slug>/`, `/profil/<slug>/`.
Reverse by name; never hardcode a path.

In `theme/urls.py`, anything added to `i18n_patterns` must come **before**
`path("", include("cms.urls"))`, which is a catch-all.

## Conventions

- Lint with `ruff check` / `ruff format` (see `.pre-commit-config.yaml`). djlint
  is configured but commented out; DE's templates are djlint-formatted, AT's are
  largely not — don't reformat AT templates wholesale.
- `MERGE_PLAN.md` tracks the DE→AT port: what was taken, what was deliberately
  dropped, and the remaining checklists. Update it when you change ported code.
