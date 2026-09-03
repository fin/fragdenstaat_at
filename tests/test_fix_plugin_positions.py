"""fix_plugin_positions: rebuild CMSPlugin.position from the plugin tree.

The failure this repairs is a child ordered at or before its parent, which
makes django-cms refuse new plugins with "Plugin position must be greater than
N". Placeholder._recalculate_plugin_positions() cannot fix it -- it renumbers
"ordered by the current position", so a mis-ordered child stays mis-ordered.
"""

from io import StringIO

from django.core.management import call_command

import pytest
from cms.models import CMSPlugin, Placeholder

from fragdenstaat_at.fds_cms_at.management.commands.fix_plugin_positions import (
    tree_order,
    violations,
)

pytestmark = pytest.mark.django_db

LANG = "de-at"


def _plugin(placeholder, position, parent=None):
    return CMSPlugin.objects.create(
        placeholder=placeholder,
        plugin_type="TextPlugin",
        language=LANG,
        position=position,
        parent=parent,
    )


def _positions(placeholder):
    return {
        p.pk: p.position
        for p in CMSPlugin.objects.filter(placeholder=placeholder, language=LANG)
    }


def test_repairs_a_child_ordered_before_its_parent():
    ph = Placeholder.objects.create(slot="content")
    parent = _plugin(ph, 2)
    child = _plugin(ph, 1, parent=parent)  # child sits *before* its parent

    assert violations(list(CMSPlugin.objects.filter(placeholder=ph)))

    call_command("fix_plugin_positions", stdout=StringIO())

    pos = _positions(ph)
    assert pos[parent.pk] < pos[child.pk]
    assert sorted(pos.values()) == [1, 2]
    assert not violations(list(CMSPlugin.objects.filter(placeholder=ph)))


def test_leaves_a_healthy_placeholder_alone():
    ph = Placeholder.objects.create(slot="content")
    first = _plugin(ph, 1)
    _plugin(ph, 2, parent=first)
    _plugin(ph, 3)
    before = _positions(ph)

    out = StringIO()
    call_command("fix_plugin_positions", stdout=out)

    assert _positions(ph) == before
    assert "renumbered 0" in out.getvalue()


def test_closes_gaps_and_keeps_depth_first_order():
    ph = Placeholder.objects.create(slot="content")
    a = _plugin(ph, 10)
    a1 = _plugin(ph, 20, parent=a)
    a2 = _plugin(ph, 30, parent=a)
    b = _plugin(ph, 40)

    call_command("fix_plugin_positions", stdout=StringIO())

    pos = _positions(ph)
    assert [pos[p.pk] for p in (a, a1, a2, b)] == [1, 2, 3, 4]


def test_dry_run_writes_nothing():
    ph = Placeholder.objects.create(slot="content")
    parent = _plugin(ph, 2)
    _plugin(ph, 1, parent=parent)
    before = _positions(ph)

    out = StringIO()
    call_command("fix_plugin_positions", "--dry-run", stdout=out)

    assert _positions(ph) == before
    assert "would renumber 1" in out.getvalue()


def test_only_the_named_placeholder_is_touched():
    broken = Placeholder.objects.create(slot="content")
    p = _plugin(broken, 2)
    _plugin(broken, 1, parent=p)

    other = Placeholder.objects.create(slot="content")
    q = _plugin(other, 2)
    _plugin(other, 1, parent=q)
    other_before = _positions(other)

    call_command(
        "fix_plugin_positions", "--placeholder", str(broken.pk), stdout=StringIO()
    )

    assert not violations(list(CMSPlugin.objects.filter(placeholder=broken)))
    assert _positions(other) == other_before


def test_tree_order_keeps_unreachable_plugins():
    """A parent pointing outside the group must not drop the child."""
    ph = Placeholder.objects.create(slot="content")
    elsewhere = Placeholder.objects.create(slot="other")
    outside = _plugin(elsewhere, 1)
    root = _plugin(ph, 1)
    stray = _plugin(ph, 2, parent=outside)

    order = tree_order(list(CMSPlugin.objects.filter(placeholder=ph, language=LANG)))

    assert {p.pk for p in order} == {root.pk, stray.pk}
