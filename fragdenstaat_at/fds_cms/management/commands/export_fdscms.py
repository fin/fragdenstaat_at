"""Dump the CMS content used by tests/fixtures/cms.json, in load-safe order.

`dumpdata` cannot produce a loadable CMS fixture on django-cms 5. With
--natural-foreign it sorts via `serializers.sort_dependencies`, which orders by
*natural key* dependencies rather than the foreign key graph: models that have
a natural key are emitted first, and `cms.Page` has none, so it lands last --
after `cms.PageContent`, which references it. `cms/signals/pagecontent.py`
dereferences `instance.page` in a post_save handler, so loaddata then dies with
`Page.DoesNotExist` before any test runs.

So dump, then reorder by the actual FK graph. Run against a database loaded
from a `scripts/export_dev_db.py` extract, not a real one -- the extract is what
keeps the fixture small (published versions only, one synthetic user):

    python manage.py export_fdscms --output tests/fixtures/cms.json
"""

import json
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Kept in sync with what the fixture is expected to contain. account.user is
# needed because Version.created_by points at it; on an export_dev_db extract
# that is exactly one synthetic row.
APPS = [
    "cms",
    "djangocms_alias",
    "djangocms_versioning",
    "djangocms_frontend",
    "djangocms_text",
    "sites",
    "account.user",
]


def dependency_order(models):
    """Topologically sort model classes so FK targets precede their referrers."""
    present = set(models)
    deps = {
        m: {
            f.related_model
            for f in m._meta.get_fields()
            if f.is_relation
            and f.concrete
            and (f.many_to_one or f.one_to_one)
            and f.related_model in present
            and f.related_model is not m  # self-refs (Page.parent) load fine
        }
        for m in models
    }

    ordered, remaining = [], dict(deps)
    while remaining:
        ready = sorted(
            (m for m, d in remaining.items() if not (d & remaining.keys())),
            key=lambda m: m._meta.label_lower,
        )
        if not ready:
            # A genuine cycle. Break it deterministically rather than looping
            # forever; loaddata defers integer FKs inside its transaction, so
            # this is usually survivable.
            ready = [min(remaining, key=lambda m: m._meta.label_lower)]
        for model in ready:
            ordered.append(model)
            del remaining[model]
    return ordered


class Command(BaseCommand):
    help = "Dump CMS content for tests/fixtures/cms.json, in load-safe order"

    def add_arguments(self, parser):
        parser.add_argument("--output", help="write here instead of stdout")
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        buf = StringIO()
        call_command(
            "dumpdata",
            *APPS,
            natural_foreign=True,
            indent=options["indent"],
            stdout=buf,
        )
        objects = json.loads(buf.getvalue())

        labels = {o["model"] for o in objects}
        models = [apps.get_model(label) for label in sorted(labels)]
        rank = {m._meta.label_lower: i for i, m in enumerate(dependency_order(models))}
        # stable: preserves dumpdata's ordering within each model
        objects.sort(key=lambda o: rank[o["model"]])

        payload = json.dumps(objects, indent=options["indent"]) + "\n"
        if options["output"]:
            with open(options["output"], "w") as fh:
                fh.write(payload)
            self.stderr.write(
                f"wrote {len(objects)} objects to {options['output']} "
                f"({len(rank)} models, dependency-ordered)"
            )
        else:
            self.stdout.write(payload)
