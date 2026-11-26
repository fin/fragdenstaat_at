"""The "TRANSLATED IN AT" marker in the `de` catalogues must never be served.

Some strings are translated only in `de_AT` (AT's own wording, e.g. the fax
notices). DE's `makemessages-de` hook fails on any empty `de` msgstr, so their
`de` entry carries a static marker instead of German: "TRANSLATED IN AT",
followed by the msgid's placeholders (msgfmt -c rejects a msgstr that drops
them).

The marker reaches visitors as soon as the `de_AT` entry is lost (deleted,
made fuzzy, msgid changed upstream). Which catalogue wins is also not just
"de_AT beats de": Django merges each locale directory into one catalogue,
later directories winning, and a directory with no `de_AT` (fds_donation,
fds_cms) contributes its `de` at full priority. Today AT's only `de_AT` is in
LOCALE_PATHS, merged last, so it wins; a `de_AT` added to an app directory
could lose to a marker elsewhere. Hence two checks: the catalogues on their
own, and what gettext actually returns for every language the site serves.
"""

import os
from pathlib import Path

from django.conf import settings
from django.utils import translation

import polib
import pytest

PLACEHOLDER = "TRANSLATED IN AT"

ROOT = Path(__file__).resolve().parent.parent / "fragdenstaat_at"


def _catalogues(locale):
    return sorted(ROOT.glob(f"**/locale/{locale}/LC_MESSAGES/django.po"))


def _key(entry):
    return (entry.msgctxt, entry.msgid, entry.msgid_plural)


def _is_marker(text):
    return text.startswith(PLACEHOLDER)


def _marked_entries():
    marked = []
    for po_path in _catalogues("de"):
        for entry in polib.pofile(str(po_path)):
            texts = [entry.msgstr, *entry.msgstr_plural.values()]
            if not entry.obsolete and any(_is_marker(t) for t in texts):
                marked.append((po_path, entry))
    return marked


def _de_at_translations():
    translated = {}
    for po_path in _catalogues("de_AT"):
        for entry in polib.pofile(str(po_path)):
            if entry.obsolete or "fuzzy" in entry.flags:
                continue
            texts = [entry.msgstr, *entry.msgstr_plural.values()]
            if any(texts):
                translated[_key(entry)] = entry
    return translated


def _label(po_path, entry):
    return f"{po_path.relative_to(ROOT.parent)}: {entry.msgid[:70]!r}"


def test_every_marker_has_a_de_at_translation():
    translated = _de_at_translations()
    missing = [
        _label(po_path, entry)
        for po_path, entry in _marked_entries()
        if _key(entry) not in translated
    ]
    assert not missing, (
        f"'{PLACEHOLDER}' in a de catalogue, but no de_AT translation (not "
        "fuzzy, same msgctxt/msgid) to override it:\n  " + "\n  ".join(missing)
    )


def test_marker_is_never_a_de_at_translation():
    leaked = [
        _label(po_path, entry)
        for po_path in _catalogues("de_AT")
        for entry in polib.pofile(str(po_path))
        if any(_is_marker(t) for t in [entry.msgstr, *entry.msgstr_plural.values()])
    ]
    assert not leaked, f"'{PLACEHOLDER}' used as a de_AT translation:\n  " + (
        "\n  ".join(leaked)
    )


def test_markers_are_well_formed():
    """Exactly the marker plus the msgid's own placeholders, nothing else.

    Keeps the marker greppable, and keeps it from being mistaken for (or
    edited into) a real translation.
    """
    bad = []
    for po_path, entry in _marked_entries():
        for text in [entry.msgstr, *entry.msgstr_plural.values()]:
            rest = text[len(PLACEHOLDER) :].split()
            if not _is_marker(text) or any(arg not in entry.msgid for arg in rest):
                bad.append(f"{_label(po_path, entry)} -> {text!r}")
    assert not bad, "Malformed marker:\n  " + "\n  ".join(bad)


def _stale_compiled_catalogues():
    stale = []
    for po_path in _catalogues("de") + _catalogues("de_AT"):
        mo_path = po_path.with_suffix(".mo")
        if not mo_path.exists() or os.path.getmtime(mo_path) < os.path.getmtime(
            po_path
        ):
            stale.append(str(mo_path.relative_to(ROOT.parent)))
    return stale


def _served_text(entry):
    if entry.msgid_plural:
        if entry.msgctxt:
            return translation.npgettext(
                entry.msgctxt, entry.msgid, entry.msgid_plural, 1
            ), translation.npgettext(entry.msgctxt, entry.msgid, entry.msgid_plural, 2)
        return (
            translation.ngettext(entry.msgid, entry.msgid_plural, 1),
            translation.ngettext(entry.msgid, entry.msgid_plural, 2),
        )
    if entry.msgctxt:
        return (translation.pgettext(entry.msgctxt, entry.msgid),)
    return (translation.gettext(entry.msgid),)


@pytest.mark.parametrize("language", [code for code, _name in settings.LANGUAGES])
def test_marker_is_never_served(language):
    """What gettext really returns, through Django's merged catalogue.

    Needs compiled catalogues: CI runs compilemessages before the tests. A
    missing or outdated .mo fails rather than passes, because gettext would
    then fall back to the msgid and the check would prove nothing.
    """
    marked = _marked_entries()
    if not marked:
        pytest.skip(f"no '{PLACEHOLDER}' markers in any de catalogue")
    stale = _stale_compiled_catalogues()
    assert not stale, (
        "Compiled catalogues missing or older than their .po, run "
        "`python manage.py compilemessages -i node_modules -i .venv`:\n  "
        + "\n  ".join(stale)
    )

    with translation.override(language):
        served = [
            _label(po_path, entry)
            for po_path, entry in marked
            if any(_is_marker(text) for text in _served_text(entry))
        ]
    assert not served, (
        f"'{PLACEHOLDER}' would be shown to {language} visitors:\n  "
        + "\n  ".join(served)
    )
