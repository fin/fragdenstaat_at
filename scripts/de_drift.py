#!/usr/bin/env python3
"""Measure how far fragdenstaat_at has drifted from fragdenstaat_de.

Compares this repo's ``fragdenstaat_at/`` package against a fragdenstaat_de
checkout, applying the ``fragdenstaat_de`` -> ``fragdenstaat_at`` rename first so
that the package name is not counted as a difference.

Every file lands in exactly one bucket:

  identical  byte-for-byte equal after the rename -- inherited, costs nothing
  modified   present in both, differs             -- the real merge surface
  at-only    ours                                 -- AT features, keep
  de-only    theirs                               -- declined or not yet adopted

Usage:
    python scripts/de_drift.py                       # summary
    python scripts/de_drift.py --list modified       # paths in one bucket
    python scripts/de_drift.py --ref abe0781d        # against a specific DE commit
    python scripts/de_drift.py --json                # machine-readable
    python scripts/de_drift.py --check-max-modified 60   # CI gate

The numbers in MERGE_PLAN.md came from this comparison; keep them honest by
re-running it rather than editing them by hand.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DEFAULT_DE = HERE.parent / "fragdenstaat_de"
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "build", ".venv"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".mo"}


def walk(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        out[str(path.relative_to(root))] = path
    return out


def read_de(path: Path) -> bytes:
    """DE's bytes with the package renamed, so only real differences count."""
    return path.read_bytes().replace(b"fragdenstaat_de", b"fragdenstaat_at")


def de_package_at(
    de_repo: Path, ref: str | None
) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    """Return the DE package dir, checking out ``ref`` into a temp worktree if given."""
    if ref is None:
        return de_repo / "fragdenstaat_de", None
    tmp = tempfile.TemporaryDirectory(prefix="de_drift_")
    subprocess.run(
        ["git", "-C", str(de_repo), "worktree", "add", "--detach", tmp.name, ref],
        check=True,
        capture_output=True,
    )
    return Path(tmp.name) / "fragdenstaat_de", tmp


def classify(at_root: Path, de_root: Path) -> dict[str, list[str]]:
    ours, theirs = walk(at_root), walk(de_root)
    buckets: dict[str, list[str]] = {
        "identical": [],
        "modified": [],
        "at-only": [],
        "de-only": [],
    }
    for rel, path in sorted(ours.items()):
        other = theirs.get(rel)
        if other is None:
            buckets["at-only"].append(rel)
        elif path.read_bytes() == read_de(other):
            buckets["identical"].append(rel)
        else:
            buckets["modified"].append(rel)
    buckets["de-only"] = sorted(set(theirs) - set(ours))
    return buckets


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--de-repo", type=Path, default=DEFAULT_DE)
    ap.add_argument(
        "--ref", help="DE git ref to compare against (default: working tree)"
    )
    ap.add_argument(
        "--list", dest="bucket", choices=["identical", "modified", "at-only", "de-only"]
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--check-max-modified",
        type=int,
        metavar="N",
        help="exit 1 if more than N files differ (CI drift gate)",
    )
    args = ap.parse_args()

    if not args.de_repo.is_dir():
        print(f"error: no fragdenstaat_de checkout at {args.de_repo}", file=sys.stderr)
        return 2

    de_root, tmp = de_package_at(args.de_repo, args.ref)
    try:
        buckets = classify(HERE / "fragdenstaat_at", de_root)
    finally:
        if tmp is not None:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(args.de_repo),
                    "worktree",
                    "remove",
                    "--force",
                    tmp.name,
                ],
                capture_output=True,
            )
            tmp._finalizer.detach()  # already removed by git

    if args.json:
        print(json.dumps({k: sorted(v) for k, v in buckets.items()}, indent=2))
    elif args.bucket:
        print("\n".join(buckets[args.bucket]))
    else:
        total = sum(len(v) for v in buckets.values())
        print(f"fragdenstaat_at vs fragdenstaat_de @ {args.ref or 'working tree'}\n")
        for name in ("identical", "modified", "at-only", "de-only"):
            n = len(buckets[name])
            print(f"  {name:10s} {n:5d}   {n / total * 100:5.1f}%")
        print(f"  {'total':10s} {total:5d}")
        print("\n  'modified' is the merge surface: the files a sync must reconcile.")

    if args.check_max_modified is not None:
        n = len(buckets["modified"])
        if n > args.check_max_modified:
            print(
                f"\nFAIL: {n} modified files exceeds limit {args.check_max_modified}",
                file=sys.stderr,
            )
            return 1
        print(f"\nOK: {n} modified files within limit {args.check_max_modified}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
