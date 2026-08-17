#!/usr/bin/env python
"""
Search froide's `de` .po file for entries whose msgid or msgstr contains any
of the given keywords, then add missing ones to the local de_AT override file
in fragdenstaat_at (leaving msgstr empty so they can be filled in manually).

Usage:
    python sync_froide_translations.py [--dry-run]
"""
import argparse
import os

import polib

# Matched case-insensitively, except CASE_SENSITIVE_KEYWORDS.
KEYWORDS = [
    "Open Knowledge",
    "FragDenStaat.de",
    "Frag Den Staat",
    "gelber Brief",
    "gelben Brief",
    "Spende",
    "IBAN",
]

# Matched as-is (case-sensitive substring).
CASE_SENSITIVE_KEYWORDS = [
    "DE",
]

FROIDE_PO = os.path.join(
    os.path.dirname(__file__),
    "../froide/froide/locale/de/LC_MESSAGES/django.po",
)

TARGET_PO = os.path.join(
    os.path.dirname(__file__),
    "fragdenstaat_at/locale/de_AT/LC_MESSAGES/django.po",
)

TARGET_HEADER = """\
# FragDenStaat.at override translations for froide (de_AT).
# Strings here take precedence over froide's own de / de_AT translations.
# Leave msgstr empty to fall back to froide's translation.
#
"""


def contains_keyword(text: str) -> bool:
    lower = text.lower()
    for kw in KEYWORDS:
        if kw.lower() in lower:
            return True
    for kw in CASE_SENSITIVE_KEYWORDS:
        if kw in text:
            return True
    return False


def entry_matches(entry: polib.POEntry) -> bool:
    if entry.obsolete:
        return False
    texts = [entry.msgid, entry.msgstr]
    if entry.msgid_plural:
        texts.append(entry.msgid_plural)
    texts.extend(entry.msgstr_plural.values())
    return any(contains_keyword(t) for t in texts)


def load_or_create_target() -> polib.POFile:
    if os.path.exists(TARGET_PO):
        return polib.pofile(TARGET_PO)

    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": "fragdenstaat_at",
        "Report-Msgid-Bugs-To": "",
        "POT-Creation-Date": "",
        "PO-Revision-Date": "",
        "Last-Translator": "",
        "Language-Team": "",
        "Language": "de_AT",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "Plural-Forms": "nplurals=2; plural=(n != 1);",
    }
    return po


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print matches, don't write")
    args = parser.parse_args()

    source = polib.pofile(FROIDE_PO)
    target = load_or_create_target()

    existing_msgids = {e.msgid for e in target}

    added = []
    for entry in source:
        if not entry_matches(entry):
            continue
        if entry.msgid in existing_msgids:
            continue

        new_entry = polib.POEntry(
            occurrences=entry.occurrences,
            comment=entry.comment,
            flags=entry.flags,
            msgid=entry.msgid,
            msgstr="",
        )
        if entry.msgid_plural:
            new_entry.msgid_plural = entry.msgid_plural
            new_entry.msgstr_plural = {k: "" for k in entry.msgstr_plural}

        added.append(new_entry)

    if not added:
        print("Nothing new to add.")
        return

    print(f"Found {len(added)} new entr{'y' if len(added) == 1 else 'ies'} to add:")
    for e in added:
        preview = e.msgid[:80].replace("\n", "\\n")
        print(f"  {preview!r}")

    if args.dry_run:
        print("Dry run — not writing.")
        return

    os.makedirs(os.path.dirname(TARGET_PO), exist_ok=True)

    for e in added:
        target.append(e)

    target.header = TARGET_HEADER.strip()
    target.save(TARGET_PO)
    print(f"\nSaved to {TARGET_PO}")
    print("Run `django-admin compilemessages --locale de_AT` to compile.")


if __name__ == "__main__":
    main()
