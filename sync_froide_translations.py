#!/usr/bin/env python
"""Collect German-specific strings from every installed app into AT's de_AT override.

Two jobs, both aimed at letting AT drop its forks of froide / froide-payment
(see MERGE_PLAN.md D4, D5, P6):

  scan    Search each app's `de` catalog for strings carrying Germany-specific
          wording ("Open Knowledge", "FragDenStaat.de", "gelber Brief", ...) and
          add the matches to AT's de_AT catalog with an *empty* msgstr, ready to
          be filled in by hand.

  adopt   Import de_AT catalogs that already exist -- in an app's own source
          tree, or on a fork branch such as `fin/main` -- carrying their msgstr
          across verbatim. This is how translations living in a fork get moved
          into fragdenstaat_at so the fork can be retired.

Apps are discovered from Django's INSTALLED_APPS rather than a hardcoded list,
so froide, froide-payment, filingcabinet, django-cms and anything added later
are all covered automatically, and apps AT does *not* install are never
scanned. Everything lands in one catalog, because AT's locale directory comes
first in LOCALE_PATHS and therefore overrides every app-level catalog.

Usage:
    python sync_froide_translations.py --dry-run
    python sync_froide_translations.py
    python sync_froide_translations.py --adopt
    python sync_froide_translations.py --adopt --ref froide-payment=fin/main
    python sync_froide_translations.py --app froide --app froide_payment
"""

import argparse
import os
import re
import subprocess
import sys

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
    "Presseanfrage",
]

# Matched as-is (case-sensitive substring). "DE" as a word would match far too
# much lowercased -- "wieder", "werden", "Absender" and so on.
CASE_SENSITIVE_KEYWORDS = [
    "DE",
]

HERE = os.path.dirname(os.path.abspath(__file__))

TARGET_PO = os.path.join(
    HERE, "fragdenstaat_at", "locale", "de_AT", "LC_MESSAGES", "django.po"
)

TARGET_HEADER = """\
# FragDenStaat.at override translations (de_AT).
#
# Generated and updated by sync_froide_translations.py. Strings here take
# precedence over every app's own de / de_AT catalog, because AT's locale
# directory comes first in LOCALE_PATHS.
#
# An empty msgstr falls back to the app's own translation, so entries added by
# `scan` are inert until somebody fills them in.
#
# Each entry records the app it came from in a comment. Re-running the script
# never overwrites a msgstr that already has content.
"""


# Patterns that mean "this names Germany". Broader than KEYWORDS, because these
# are matched against source text rather than translations: a German IBAN, BIC
# or Bankleitzahl in a template is not a wording problem, it is the wrong bank.
HARDCODED_PATTERNS = [
    (r"fragdenstaat\.de", "German domain"),
    (r"okfn\.de", "German domain"),
    (r"Open Knowledge Foundation Deutschland", "German legal entity"),
    (r"\bDE\d{2}[ ]?[0-9 ]{16,}", "German IBAN"),
    (r"\bGENODE[A-Z0-9]+", "German BIC"),
    (r"GLS Bank", "German bank"),
    (r"gelbe[rn]? Brief", "Deutsche Post product"),
    (r"Zuwendungsbest\w+", "German donation receipt"),
    (r"\bBLZ\b|Bankleitzahl", "German bank code (AT statements have none)"),
    # The label above only catches a *described* Bankleitzahl. DE's BLZ also
    # appeared bare, as data-copy-text="43060967" on a button whose label had
    # been removed -- a clipboard icon silently offering a German bank code with
    # nothing to indicate what it was. Both the spaced display form (430 609 67)
    # and the bare eight digits are matched.
    #
    # Bare 8-digit numbers are inherently ambiguous; across AT's own source there
    # is exactly one other (a byte limit), so the noise is one line. Austrian
    # statements have no BLZ at all, which is what makes any of these wrong here.
    (r"(?<!\d)\d{3}[ ]\d{3}[ ]\d{2}(?!\d)", "German bank code (spaced BLZ)"),
    (r"(?<!\d)\d{8}(?!\d)", "possible German bank code (bare BLZ)"),
]

# Where AT's own source lives. Third-party packages are not ours to fix.
SCAN_ROOTS = ("fragdenstaat_at",)
SCAN_SUFFIXES = (".html", ".txt", ".py")
SCAN_SKIP_DIRS = {"node_modules", ".venv", "locale", "migrations", "build", "static"}


def scan_hardcoded(root=HERE):
    """Report Germany-specific strings hardcoded in AT's own source.

    Translation tooling cannot see these: a hardcoded IBAN in a template is not
    a msgid, so no catalog will ever flag it. This is how
    banktransfer_instructions.html shipped Open Knowledge Foundation
    Deutschland's account details -- account holder, IBAN, BIC, Bankleitzahl and
    a SEPA QR code -- on an Austrian site.
    """
    compiled = [(re.compile(pat), why) for pat, why in HARDCODED_PATTERNS]
    hits = []
    for scan_root in SCAN_ROOTS:
        base = os.path.join(root, scan_root)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SCAN_SKIP_DIRS]
            for name in filenames:
                if not name.endswith(SCAN_SUFFIXES):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    text = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    for rx, why in compiled:
                        m = rx.search(line)
                        if m:
                            hits.append(
                                (os.path.relpath(path, root), lineno, why, m.group(0))
                            )
    return hits


def report_hardcoded(root=HERE):
    hits = scan_hardcoded(root)
    if not hits:
        print("\nNo Germany-specific strings hardcoded in AT's own source.")
        return 0
    print(
        f"\n⚠ {len(hits)} hardcoded Germany-specific string(s) in AT's own source."
        "\n  These are not translations -- no catalog can override them; the source"
        "\n  itself has to change.\n"
    )
    by_file = {}
    for path, lineno, why, match in hits:
        by_file.setdefault(path, []).append((lineno, why, match))
    for path in sorted(by_file):
        print(f"  {path}")
        for lineno, why, match in by_file[path]:
            print(f"      line {lineno:<5} {why:<38} {match[:40]!r}")
    return len(hits)


def contains_keyword(text):
    if not text:
        return False
    lower = text.lower()
    if any(kw.lower() in lower for kw in KEYWORDS):
        return True
    return any(kw in text for kw in CASE_SENSITIVE_KEYWORDS)


def entry_texts(entry):
    texts = [entry.msgid, entry.msgstr]
    if entry.msgid_plural:
        texts.append(entry.msgid_plural)
    texts.extend(entry.msgstr_plural.values())
    return texts


OWN_PATTERN = re.compile("|".join(pat for pat, _why in HARDCODED_PATTERNS), re.I)


def entry_matches(entry, own=False):
    """Does this entry need an Austrian override?

    Two different questions depending on whose catalog it is.

    For a third-party app, any Germany-flavoured wording is worth a look, so the
    broad KEYWORDS list applies -- "Spende" in froide's catalog is a hint that
    the string was written for a donation site.

    For AT's own catalogs it is the opposite: this is AT's own German, so
    "Spende" is simply the right word and flagging it produces 172 candidates,
    nearly all noise. Only unambiguously German things matter here -- the domain,
    the German entity, a German IBAN or BIC, Deutsche Post's gelber Brief.
    """
    if entry.obsolete:
        return False
    if own:
        return any(OWN_PATTERN.search(t) for t in entry_texts(entry) if t)
    return any(contains_keyword(t) for t in entry_texts(entry))


def key(entry):
    """Identity of a translation: msgctxt disambiguates identical msgids."""
    return (entry.msgctxt, entry.msgid)


def discover_sources(only=None, all_apps=False):
    """Yield (label, locale_dir, repo) for every catalog that can shadow AT's.

    Two kinds of source, because packages disagree about where locale lives:

    * entries in LOCALE_PATHS -- this is how froide ships its catalog, one
      directory for the whole package rather than one per app, which a pure
      INSTALLED_APPS walk would miss entirely;
    * app directories containing a `locale/`, which is how froide-payment,
      filingcabinet and most Django apps ship theirs.

    By default only apps that live in a git checkout are considered -- those are
    the ones AT could end up forking, and the ones whose German wording is worth
    overriding. Third-party wheels out of site-packages (django-cms,
    localflavor, ...) are skipped unless --all-apps is given: they match keywords
    like "IBAN" through generic validator messages, which is noise.

    AT's own apps are included too. The strategy is to keep AT's `de` catalogs a
    close mirror of DE's, so future syncs stay cheap, and to express every
    Austrian deviation as a `de_AT` override -- the same relationship AT already
    has with froide. So AT's own German is a legitimate scan target: anything in
    it that names Germany needs an override here.
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fragdenstaat_at.settings.test")
    os.environ.setdefault("DJANGO_CONFIGURATION", "Test")
    sys.path.insert(0, HERE)

    import configurations

    configurations.setup()
    from django.apps import apps
    from django.conf import settings

    seen_dirs = set()

    def emit(label, locale_dir):
        # Note we do not skip AT's own locale directory: we read `de/` from it
        # and write `de_AT/` into it, which are different catalogs.
        locale_dir = os.path.realpath(locale_dir)
        if locale_dir in seen_dirs:
            return None
        if only and label not in only:
            return None
        seen_dirs.add(locale_dir)
        own = locale_dir.startswith(
            os.path.realpath(os.path.join(HERE, "fragdenstaat_at"))
        )
        return (label, locale_dir, find_repo(locale_dir), own)

    for locale_dir in map(os.fspath, settings.LOCALE_PATHS):
        repo = find_repo(locale_dir)
        label = (
            os.path.basename(repo)
            if repo
            else os.path.basename(os.path.dirname(locale_dir))
        )
        got = emit(label, locale_dir)
        if got:
            yield got

    for config in apps.get_app_configs():
        locale_dir = os.path.join(config.path, "locale")
        if not os.path.isdir(locale_dir):
            continue
        if not all_apps and find_repo(config.path) is None:
            continue
        got = emit(config.label, locale_dir)
        if got:
            yield got


def po_from_git(repo, ref, relpath):
    """Read a .po from a git ref without checking it out."""
    try:
        blob = subprocess.run(
            ["git", "-C", repo, "show", f"{ref}:{relpath}"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except subprocess.CalledProcessError:
        return None
    return polib.pofile(blob)


def find_repo(app_path):
    """Walk up from an app directory to its git checkout, if any.

    Returns None for anything installed into site-packages. Without that guard,
    walking up from `.venv/lib/python3.x/site-packages/cms` eventually reaches
    fragdenstaat_at's own `.git` and every third-party wheel looks like a
    checkout we control.
    """
    # LOCALE_PATHS entries may be Path objects, app paths are always str.
    app_path = os.fspath(app_path)
    if "site-packages" in app_path.split(os.sep):
        return None
    path = app_path
    while path != os.path.dirname(path):
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        path = os.path.dirname(path)
    return None


def load_or_create_target():
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


def make_entry(entry, label, msgstr):
    new = polib.POEntry(
        msgid=entry.msgid,
        msgstr=msgstr,
        msgctxt=entry.msgctxt,
        occurrences=entry.occurrences,
        flags=[f for f in entry.flags if f != "fuzzy"],
        comment=f"from {label}" + (f"\n{entry.comment}" if entry.comment else ""),
    )
    if entry.msgid_plural:
        new.msgid_plural = entry.msgid_plural
        if msgstr:
            new.msgstr_plural = dict(entry.msgstr_plural)
        else:
            new.msgstr_plural = dict.fromkeys(entry.msgstr_plural, "")
        new.msgstr = ""
    return new


DE_MARKER = "de: "


def annotate(target, de_text):
    """Record each entry's German alongside it, as an extracted comment.

    Purely informative: it lets a reviewer see what an override actually
    changes, and for an empty stub it shows the text that is being fallen back
    to. Refreshed on every run, including for entries that already existed, so
    it tracks upstream rewording. Never touches msgstr.
    """
    for entry in target:
        german = de_text.get(key(entry))
        if not german:
            continue
        # Everything from the first marker line onward is ours to rewrite;
        # anything above it is provenance or a hand-written note, so keep it.
        lines = (entry.comment or "").splitlines()
        for i, line in enumerate(lines):
            if line.startswith(DE_MARKER):
                lines = lines[:i]
                break
        lines.append(DE_MARKER + " ".join(german.split()))
        entry.comment = "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="also import existing de_AT catalogs, keeping their msgstr",
    )
    parser.add_argument(
        "--ref",
        action="append",
        default=[],
        metavar="REPO=REF",
        help="adopt de_AT from a git ref instead of the working tree, e.g. "
        "froide-payment=fin/main. Repeatable. Implies --adopt.",
    )
    parser.add_argument(
        "--app",
        action="append",
        default=[],
        metavar="LABEL",
        help="restrict to these source labels. Repeatable.",
    )
    parser.add_argument(
        "--all-apps",
        action="store_true",
        help="also scan third-party apps installed from wheels, not just git "
        "checkouts (noisy: generic IBAN/validator strings match)",
    )
    parser.add_argument(
        "--no-hardcoded-check",
        action="store_true",
        help="skip the final scan for Germany-specific strings hardcoded in "
        "AT's own templates and code",
    )
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="skip the keyword scan; adopt only",
    )
    args = parser.parse_args()

    refs = {}
    for spec in args.ref:
        if "=" not in spec:
            parser.error(f"--ref expects REPO=REF, got {spec!r}")
        repo, ref = spec.split("=", 1)
        refs[repo] = ref
    adopt = args.adopt or bool(refs)

    # msgid -> the app's own German, recorded as a comment on each entry so a
    # reviewer can see what the override differs from without opening two files.
    de_text = {}

    target = load_or_create_target()
    # Never clobber work already done by hand.
    translated = {key(e) for e in target if e.msgstr or any(e.msgstr_plural.values())}
    seen = {key(e) for e in target}

    added, adopted, skipped_ref = [], [], []
    skipped_obsolete = []
    redundant = []

    for label, locale_dir, repo, is_own in discover_sources(
        set(args.app) or None, all_apps=args.all_apps
    ):
        repo_name = os.path.basename(repo) if repo else None

        if adopt:
            source = None
            if repo_name in refs:
                relpath = os.path.relpath(
                    os.path.join(locale_dir, "de_AT", "LC_MESSAGES", "django.po"), repo
                )
                source = po_from_git(repo, refs[repo_name], relpath)
                if source is None:
                    skipped_ref.append(f"{label} ({repo_name}@{refs[repo_name]})")
            else:
                path = os.path.join(locale_dir, "de_AT", "LC_MESSAGES", "django.po")
                if os.path.exists(path):
                    source = polib.pofile(path)

            # msgids the app still actually uses. Adopting from an old fork
            # otherwise resurrects strings whose English source has since
            # changed: froide-payment's SEPA mandate lost an "and/or PPRO"
            # clause after the 2023 fork, so the fork's entry and the current
            # one are different msgids and both landed in the catalog -- one
            # carrying the translation, one an empty stub that silently won at
            # runtime.
            live_msgids = None
            de_entries = {}
            de_path = os.path.join(locale_dir, "de", "LC_MESSAGES", "django.po")
            if os.path.exists(de_path):
                de_entries = {key(e): e for e in polib.pofile(de_path)}
                live_msgids = set(de_entries)
                for k, v in de_entries.items():
                    if v.msgstr:
                        de_text.setdefault(k, v.msgstr)

            for entry in source or []:
                if entry.obsolete or not entry.msgid:
                    continue
                has_text = entry.msgstr or any(entry.msgstr_plural.values())
                if not has_text or key(entry) in seen:
                    continue
                if live_msgids is not None and key(entry) not in live_msgids:
                    skipped_obsolete.append((label, entry.msgid))
                    continue

                # Keep this an *override* catalog. de-at falls back to de, so an
                # entry whose text matches the de translation renders identically
                # whether it is here or not -- it is pure duplication that has to
                # be re-synced by hand every time upstream rewords something.
                # Only carry entries that actually say something different.
                de_entry = de_entries.get(key(entry))
                if (
                    de_entry is not None
                    and de_entry.msgstr == entry.msgstr
                    and de_entry.msgstr_plural == entry.msgstr_plural
                ):
                    redundant.append((label, entry.msgid))
                    continue
                adopted.append((label, make_entry(entry, label, entry.msgstr)))
                seen.add(key(entry))

        if args.no_scan:
            continue

        de_po = os.path.join(locale_dir, "de", "LC_MESSAGES", "django.po")
        if not os.path.exists(de_po):
            continue
        for entry in polib.pofile(de_po):
            if entry.msgstr:
                de_text.setdefault(key(entry), entry.msgstr)
            if not entry_matches(entry, own=is_own) or key(entry) in seen:
                continue
            # An entry already carrying a hand-written override needs no stub.
            if key(entry) in translated:
                continue
            added.append((label, make_entry(entry, label, "")))
            seen.add(key(entry))

    def breakdown(pairs):
        counts = {}
        for label, _e in pairs:
            counts[label] = counts.get(label, 0) + 1
        return "".join(f"\n  {label}: {n}" for label, n in sorted(counts.items()))

    if adopted:
        print(f"Adopting {len(adopted)} existing de_AT translation(s):", end="")
        print(breakdown(adopted))
        for label, e in adopted:
            print(f"  [{label}] {e.msgid[:70]!r} -> {e.msgstr[:50]!r}")
    if redundant:
        by = {}
        for label, _m in redundant:
            by[label] = by.get(label, 0) + 1
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(by.items()))
        print(
            f"\nSkipped {len(redundant)} entr(y/ies) identical to the de "
            f"translation ({detail}) -- de-at falls back to de, so they would "
            "render the same either way."
        )
    if skipped_obsolete:
        print(
            f"\nSkipped {len(skipped_obsolete)} adopted entr(y/ies) whose msgid no "
            "longer exists in the app's current catalog:"
        )
        for label, mid in skipped_obsolete:
            print(f"  [{label}] {mid[:70]!r}")
    if skipped_ref:
        print("No de_AT catalog at the requested ref for: " + ", ".join(skipped_ref))
    if added:
        print(f"\nFound {len(added)} untranslated candidate(s):", end="")
        print(breakdown(added))
        for label, e in added:
            print(f"  [{label}] {e.msgid[:80]!r}".replace("\\n", " "))

    if not adopted and not added:
        # Not a reason to stop: the German-source comments are refreshed on
        # every run, so there is still work to write out.
        print("No new entries; refreshing the recorded German source text.")

    if args.dry_run:
        print("\nDry run -- not writing.")
        if not args.no_hardcoded_check:
            report_hardcoded()
        return

    os.makedirs(os.path.dirname(TARGET_PO), exist_ok=True)
    for _label, e in adopted + added:
        target.append(e)

    annotate(target, de_text)
    target.header = TARGET_HEADER.strip()
    target.save(TARGET_PO)
    print(f"\nSaved {len(target)} entries to {TARGET_PO}")
    print("Run `django-admin compilemessages --locale de_AT` to compile.")

    if not args.no_hardcoded_check:
        report_hardcoded()


if __name__ == "__main__":
    main()
