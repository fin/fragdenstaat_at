"""Rebuild CMSPlugin.position so it matches the plugin tree.

django-cms 4+ keeps one dense ``1..n`` ``position`` sequence per
(placeholder, language), and a child must sort *after* its parent -- adding a
plugin is refused with "Plugin position must be greater than N"
(``cms/admin/forms.py``) when that does not hold.

``Placeholder._recalculate_plugin_positions()`` only *compacts* the sequence:
it re-numbers "ordered by the current position", so a child that already sits
before its parent stays there. This walks the actual parent/child tree instead
and assigns positions in depth-first order, which is what repairs an ordering
broken by a dump restore, a cms3->4 conversion, an interrupted move, or plugin
rows left behind by a removed plugin class.

    manage.py fix_plugin_positions --dry-run
    manage.py fix_plugin_positions
    manage.py fix_plugin_positions --placeholder 42
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPlugin, Placeholder


def tree_order(plugins):
    """Depth-first order of `plugins`, roots and siblings by current position.

    Anything unreachable from a root (parent outside the group, or a cycle) is
    appended rather than dropped, so no plugin ever loses its row.
    """
    children = defaultdict(list)
    ids = {p.pk for p in plugins}
    for plugin in plugins:
        parent = plugin.parent_id if plugin.parent_id in ids else None
        children[parent].append(plugin)

    order = []
    stack = list(reversed(children[None]))
    while stack:
        plugin = stack.pop()
        order.append(plugin)
        stack.extend(reversed(children[plugin.pk]))

    seen = {p.pk for p in order}
    order.extend(p for p in plugins if p.pk not in seen)
    return order


def violations(plugins):
    """Children ordered at or before their parent."""
    positions = {p.pk: p.position for p in plugins}
    return [
        p
        for p in plugins
        if p.parent_id in positions and p.position <= positions[p.parent_id]
    ]


def rebuild(placeholder, language, *, dry_run=False):
    """Renumber one (placeholder, language) group. Returns (changed, n)."""
    plugins = list(placeholder.get_plugins(language).order_by("position", "pk"))
    if not plugins:
        return False, 0

    order = tree_order(plugins)
    wanted = {p.pk: i for i, p in enumerate(order, start=1)}
    if all(p.position == wanted[p.pk] for p in plugins):
        return False, len(plugins)
    if dry_run:
        return True, len(plugins)

    # (placeholder, language, position) is unique, so move in two disjoint
    # blocks: park above every current position, then drop back to 1..n.
    base = max(max(p.position for p in plugins), len(order))
    with transaction.atomic():
        for plugin in order:
            CMSPlugin.objects.filter(pk=plugin.pk).update(
                position=base + wanted[plugin.pk]
            )
        for plugin in order:
            CMSPlugin.objects.filter(pk=plugin.pk).update(position=wanted[plugin.pk])
    return True, len(plugins)


class Command(BaseCommand):
    help = "Rebuild CMSPlugin.position from the plugin tree (depth-first)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="report what would change, write nothing",
        )
        parser.add_argument(
            "--placeholder",
            type=int,
            default=None,
            help="only this placeholder id",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        placeholders = Placeholder.objects.all()
        if options["placeholder"]:
            placeholders = placeholders.filter(pk=options["placeholder"])

        before = len(violations(list(CMSPlugin.objects.all())))
        groups = changed = touched = 0

        for placeholder in placeholders.iterator():
            languages = (
                CMSPlugin.objects.filter(placeholder=placeholder)
                # .order_by() clears CMSPlugin.Meta.ordering: leaving it in
                # adds `position` to the SELECT, so DISTINCT would dedupe on
                # (language, position) and yield each language once per plugin.
                .order_by()
                .values_list("language", flat=True)
                .distinct()
            )
            for language in languages:
                groups += 1
                did, count = rebuild(placeholder, language, dry_run=dry_run)
                if did:
                    changed += 1
                    touched += count
                    self.stdout.write(
                        f"placeholder {placeholder.pk} [{language}]: "
                        f"{count} plugins renumbered"
                    )

        after = len(violations(list(CMSPlugin.objects.all())))
        verb = "would renumber" if dry_run else "renumbered"
        self.stdout.write(
            self.style.SUCCESS(
                f"{groups} group(s) scanned, {verb} {changed} "
                f"({touched} plugins). "
                f"child-before-parent violations: {before} -> {after}"
            )
        )
        if after and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "still broken -- those plugins likely point at a parent in "
                    "another placeholder or language; inspect them by hand."
                )
            )
