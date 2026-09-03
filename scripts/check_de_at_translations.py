#!/usr/bin/env python3
"""Can a package's ``de_AT`` catalogue be dropped without changing output?

AT is a single-language ``de-at`` site. gettext resolves each string
``de_AT`` -> ``de`` -> msgid, and ``fragdenstaat_at/locale`` (a LOCALE_PATHS
entry) wins over any package catalogue.

For every translated entry in the package's
``locale/de_AT/LC_MESSAGES/django.{po,mo}`` this works out what ``de-at`` would
render *after that catalogue is deleted* --

    fragdenstaat_at de_AT  ->  fragdenstaat_at de  ->  package de  ->  msgid

-- and classifies it:

  * shadowed  fragdenstaat_at already overrides it; the package entry is dead
  * duplicate it only repeats the package's own ``de``
  * mirrored  fragdenstaat_at reproduces exactly the same string
  * stale     nothing else yields it, BUT the package no longer uses the msgid
              (gone from / obsolete in its own ``de`` .po), so nothing renders
              it either -- harmless to drop
  * BLOCKER   nothing else yields it and the package still uses it; deleting
              the catalogue would change rendered output

Exit status is 0 only with no blockers. ``--grep`` additionally scans the
package source for each msgid literal (best-effort: blocktrans splits and
format strings can hide a real use).

    scripts/check_de_at_translations.py froide
    scripts/check_de_at_translations.py --grep --show all froide
    scripts/check_de_at_translations.py --emit-po froide   # blockers as a .po

Accepts an import name (``froide``, ``djangocms_frontend.contrib.card``) or a
path. Needs polib (a project dependency).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import polib

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT / "fragdenstaat_at"

Key = tuple[str, str]  # (msgid, msgctxt)
CATEGORIES = ("shadowed", "duplicate", "mirrored", "stale", "blocker")
SOURCE_SUFFIXES = (".py", ".html", ".txt", ".jinja", ".jinja2", ".j2")


def _key(entry) -> Key:
    return (entry.msgid, entry.msgctxt or "")


def _value(entry):
    if entry.msgstr_plural:
        return tuple(v for _, v in sorted(entry.msgstr_plural.items()))
    return entry.msgstr


def _is_translated(entry) -> bool:
    if entry.obsolete or "fuzzy" in entry.flags:
        return False
    if entry.msgstr_plural:
        return any(v.strip() for v in entry.msgstr_plural.values())
    return bool(entry.msgstr.strip())


def _catalogue_path(lc_messages_dir: Path) -> Path | None:
    for name in ("django.po", "django.mo"):
        path = lc_messages_dir / name
        if path.exists():
            return path
    return None


def _read(path: Path):
    return polib.pofile(str(path)) if path.suffix == ".po" else polib.mofile(str(path))


def _load(lc_messages_dir: Path) -> dict[Key, object]:
    """Translated entries of the django catalogue in a LC_MESSAGES dir."""
    path = _catalogue_path(lc_messages_dir)
    if path is None:
        return {}
    return {_key(e): _value(e) for e in _read(path) if _is_translated(e)}


def _index(lc_messages_dir: Path) -> tuple[set[Key], set[Key]]:
    """(live keys, obsolete keys) of the de catalogue -- what the package still
    extracts vs. what it dropped. A .mo carries no obsolete info."""
    path = _catalogue_path(lc_messages_dir)
    if path is None:
        return set(), set()
    live, gone = set(), set()
    if path.suffix == ".mo":
        return {_key(e) for e in _read(path)}, gone
    po = polib.pofile(str(path))
    for e in po:
        live.add(_key(e))
    for e in po.obsolete_entries():
        gone.add(_key(e))
    return live, gone


def _merge(target: dict, lc_messages_dir: Path) -> None:
    for k, v in _load(lc_messages_dir).items():
        target.setdefault(k, v)  # first (higher-precedence) catalogue wins


def load_project_catalogues(lang: str) -> dict[Key, object]:
    """`lang` catalogues under fragdenstaat_at; main locale/ takes precedence."""
    merged: dict[Key, object] = {}
    main = PROJECT_ROOT / "locale" / lang / "LC_MESSAGES"
    if main.is_dir():
        _merge(merged, main)
    for po in sorted(PROJECT_ROOT.glob(f"*/locale/{lang}/LC_MESSAGES/django.po")):
        _merge(merged, po.parent)
    return merged


def package_dir(name_or_path: str) -> Path:
    path = Path(name_or_path)
    if path.exists():
        return path
    try:
        spec = importlib.util.find_spec(name_or_path)
    except (ImportError, ValueError):
        spec = None
    if spec and spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations)))
    sys.exit(f"error: cannot locate package or path {name_or_path!r}")


def de_at_locale_dirs(pkg_dir: Path):
    """(sibling de dir | None, de_AT dir) for every de_AT catalogue found."""
    for de_at in sorted(pkg_dir.glob("**/locale/de_AT/LC_MESSAGES")):
        de = de_at.parent.parent / "de" / "LC_MESSAGES"
        yield (de if de.is_dir() else None), de_at


def load_source_blob(pkg_dir: Path) -> str:
    """Every source file concatenated once, for literal msgid lookups."""
    parts = []
    for path in pkg_dir.rglob("*"):
        if path.suffix in SOURCE_SUFFIXES and "/locale/" not in str(path):
            try:
                parts.append(path.read_text("utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(parts)


def source_has(msgid: str, blob: str) -> bool:
    if not msgid.strip():
        return False
    if "\n" not in msgid:
        return msgid in blob
    # blocktrans splits across lines; the longest line is the best probe.
    probe = max((ln.strip() for ln in msgid.splitlines()), key=len, default="")
    return len(probe) > 3 and probe in blob


def classify(key: Key, value, *, pkg_de: dict, proj_de_at: dict, proj_de: dict):
    """Category + the string de-at would show once the de_AT catalogue is gone."""
    if key in proj_de_at:
        after = proj_de_at[key]
        return ("mirrored" if after == value else "shadowed"), after
    if key in proj_de:
        after = proj_de[key]
        return ("mirrored" if after == value else "blocker"), after
    if key in pkg_de:
        after = pkg_de[key]
        return ("duplicate" if after == value else "blocker"), after
    return "blocker", key[0]  # nothing left: renders the msgid


def usage_note(key: Key, live: set[Key], gone: set[Key]) -> tuple[str, str]:
    """(category-override, human note) once a row is otherwise a blocker."""
    if key in gone:
        return "stale", "obsolete (#~) in the package's de .po"
    if key not in live:
        return "stale", "not in the package's de .po"
    return "blocker", "still extracted in the package's de .po"


def analyse(pkg_dir: Path, grep_blob: str | None):
    proj_de_at = load_project_catalogues("de_AT")
    proj_de = load_project_catalogues("de")

    rows = []
    n_catalogues = 0
    for de_dir, de_at_dir in de_at_locale_dirs(pkg_dir):
        n_catalogues += 1
        pkg_de = _load(de_dir) if de_dir else {}
        live, gone = _index(de_dir) if de_dir else (set(), set())
        for key, value in _load(de_at_dir).items():
            category, after = classify(
                key, value, pkg_de=pkg_de, proj_de_at=proj_de_at, proj_de=proj_de
            )
            note = ""
            if category == "blocker":
                category, note = usage_note(key, live, gone)
                if grep_blob is not None:
                    hit = source_has(key[0], grep_blob)
                    note += "; msgid %s in source" % ("found" if hit else "NOT found")
                    if not hit and category == "blocker":
                        category = "stale"
            rows.append((category, key, value, after, note))
    return rows, n_catalogues


def _fmt(value) -> str:
    text = " / ".join(value) if isinstance(value, tuple) else str(value)
    text = text.replace("\n", "\\n")
    return text if len(text) <= 70 else text[:67] + "..."


def _emit_po(rows, package):
    po = polib.POFile(wrapwidth=78)
    po.metadata = {"Content-Type": "text/plain; charset=UTF-8"}
    for _c, (msgid, ctxt), value, _after, _note in sorted(
        r for r in rows if r[0] == "blocker"
    ):
        entry = polib.POEntry(
            msgid=msgid, msgctxt=ctxt or None, comment="from " + package
        )
        if isinstance(value, tuple):
            entry.msgid_plural = msgid
            entry.msgstr_plural = dict(enumerate(value))
        else:
            entry.msgstr = value
        po.append(entry)
    print(str(po))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("package", help="import name or path")
    parser.add_argument(
        "--show",
        default="blocker",
        help="comma list of categories to print in full "
        f"({', '.join(CATEGORIES)}, or 'all'; default: blocker)",
    )
    parser.add_argument(
        "--grep",
        action="store_true",
        help="also scan the package source for each msgid literal; a blocker "
        "whose msgid is nowhere in the source is downgraded to stale",
    )
    parser.add_argument(
        "--emit-po",
        action="store_true",
        help="instead of a report, print the blocker entries as a .po fragment "
        "ready to paste into fragdenstaat_at/locale/de_AT",
    )
    args = parser.parse_args()

    show = {s.strip() for s in args.show.split(",") if s.strip()}
    if "all" in show:
        show = set(CATEGORIES)

    pkg_dir = package_dir(args.package)
    blob = load_source_blob(pkg_dir) if args.grep else None
    rows, n_catalogues = analyse(pkg_dir, blob)

    if n_catalogues == 0:
        print(f"{args.package}: no de_AT catalogue found - nothing to delete")
        return 0

    if args.emit_po:
        _emit_po(rows, args.package)
        return 0

    counts = dict.fromkeys(CATEGORIES, 0)
    for category, *_ in rows:
        counts[category] += 1

    plural = "s" if n_catalogues != 1 else ""
    print(
        f"{args.package}  ({n_catalogues} de_AT catalogue{plural}, {len(rows)} entries)"
    )
    for c in CATEGORIES:
        print(f"  {c:9} {counts[c]}")

    for category in CATEGORIES:
        if category not in show:
            continue
        listed = sorted(r for r in rows if r[0] == category)
        if not listed:
            continue
        print(f"\n{category} ({len(listed)}):")
        for _category, key, value, after, note in listed:
            msgid, ctxt = key
            print(f"  {msgid[:78]!r}" + (f"  [ctx: {ctxt}]" if ctxt else ""))
            print(f"      de_AT : {_fmt(value)}")
            if category != "mirrored":
                print(f"      after : {_fmt(after)}")
            if note:
                print(f"      used  : {note}")

    if counts["blocker"]:
        print(
            f"\n{counts['blocker']} blocker(s) - deleting {args.package}'s de_AT "
            "catalogue WOULD change rendered output. Port the ones worth keeping "
            "into fragdenstaat_at/locale/de_AT (see --emit-po); for the rest, "
            "check whether 'after' is in fact the better string."
        )
        return 1

    tail = (
        " (some entries are stale but nothing renders them)" if counts["stale"] else ""
    )
    print(
        f"\nsafe - {args.package}'s de_AT catalogue adds nothing over "
        f"fragdenstaat_at's catalogues and the package's own de{tail}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
