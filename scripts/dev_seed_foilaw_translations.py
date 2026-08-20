#!/usr/bin/env python
"""Seed placeholder de-at FoiLaw translations in a dev database.

STOPGAP. Only needed for dumps produced before export_dev_db.py was fixed.

`export_dev_db.py` exported the FoiLaw master rows but named the parler
translation table `publicbody_foilawtranslation`, while froide overrides
`db_table` to `publicbody_foilaw_translation`. The mismatch was a silent skip, so
dumps up to and including test_export_2026-06-14.sql carry 12 laws with **no
translations at all**. Every human-readable field of a FoiLaw -- name,
description, letter_start, letter_end, legal_text -- lives in that table, so
/anfrage-stellen/ dies with:

    parler.models.DoesNotExist: ... does not have a translation for the current
    language! ... ID #13, language=de-at (tried fallbacks de-at)

The real text exists only on production. This inserts obviously-fake placeholders
so the request flow can be exercised locally. Re-export with the fixed script to
get the real content; these rows are then redundant and can be deleted with:

    DELETE FROM publicbody_foilaw_translation WHERE name LIKE '%[DEV-PLATZHALTER]%';

Idempotent: skips any (law, language) that already has a row.

Usage:
    DATABASE_URL=... DJANGO_SETTINGS_MODULE=fragdenstaat_at.settings.development \\
      DJANGO_CONFIGURATION=Dev python scripts/dev_seed_foilaw_translations.py
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fragdenstaat_at.settings.development")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")

import configurations  # noqa: E402

configurations.setup()
django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402

MARK = "[DEV-PLATZHALTER]"

LETTER_START = (
    "Sehr geehrte Damen und Herren,\n\n"
    "hiermit stelle ich nach dem Informationsfreiheitsgesetz folgenden Antrag "
    "auf Zugang zu Informationen.\n\n"
    f"{MARK} Dieser Einleitungstext stammt nicht aus der Produktionsdatenbank."
)
LETTER_END = (
    "Ich bitte um Empfangsbestätigung und danke für Ihre Mühe.\n\n"
    "Mit freundlichen Grüßen\n\n"
    f"{MARK} Dieser Schlusstext stammt nicht aus der Produktionsdatenbank."
)


def main():
    lang = settings.LANGUAGE_CODE  # "de-at"
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT l.id, COALESCE(NULLIF(l.law_type, ''), '')
              FROM publicbody_foilaw l
             WHERE NOT EXISTS (
                   SELECT 1 FROM publicbody_foilaw_translation t
                    WHERE t.master_id = l.id AND t.language_code = %s)
             ORDER BY l.id
            """,
            [lang],
        )
        missing = cur.fetchall()

        if not missing:
            print(f"Nothing to do: every FoiLaw already has a {lang} translation.")
            return

        for law_id, law_type in missing:
            label = law_type or f"Gesetz #{law_id}"
            cur.execute(
                """
                INSERT INTO publicbody_foilaw_translation
                    (language_code, master_id, name, slug, description,
                     long_description, request_note, letter_start, letter_end,
                     refusal_reasons, legal_text, overdue_reply)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    lang,
                    law_id,
                    f"{label} {MARK}",
                    f"dev-platzhalter-{law_id}",
                    f"{MARK} Platzhalter-Beschreibung für {label}.",
                    f"{MARK} Platzhalter-Langbeschreibung für {label}.",
                    "",
                    LETTER_START,
                    LETTER_END,
                    "",
                    f"{MARK} Kein Gesetzestext in der Entwicklungsdatenbank.",
                    "",
                ],
            )
            print(f"  seeded law #{law_id} ({label})")

    print(f"\nSeeded {len(missing)} placeholder translation(s) for {lang}.")
    print("Re-export with the fixed export_dev_db.py to replace them with real text.")


main()
