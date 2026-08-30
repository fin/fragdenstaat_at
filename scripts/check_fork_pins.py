#!/usr/bin/env python3
"""Assert the frontend and backend fork pins name the same tree.

froide and froide-payment are pinned twice:

  * as a Python git dependency in pyproject.toml (-> uv.lock), and
  * as an npm git dependency in package.json (-> pnpm-lock.yaml),

because the Vue/TS sources are built from the npm copy. Nothing keeps the two
in step. When the backend pin moved ahead to a fork branch while package.json
still said ``github:okfde/froide``, CI built ``request-page.vue`` from the wrong
tree and the make-request page broke at runtime -- with no build error.

Dev does not hit this: devsetup.sh links both to the sibling checkout. So the
guard belongs in CI, not in scripts/sync-editables.sh. Run from the lint job
via .pre-commit-config.yaml.

Compares owner + ref (branch/tag/sha) per GitHub repo. An unspecified npm ref
means "default branch", which is accepted only when the backend ref also looks
like a default branch (main/master). The resolved commits in the two lockfiles
are deliberately not compared -- npm and uv resolve a branch independently, and
that is fine as long as it is the same branch.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRANCHES = {"main", "master", None}

# GitHub repo name -> (pyproject dependency name, package.json key). Only repos
# listed here are checked, and only when they appear on both sides.
TRACKED = {
    "froide": ("froide", "froide"),
    "froide-payment": ("froide-payment", "froide_payment"),
    "django-filingcabinet": ("django-filingcabinet", "@okfde/filingcabinet"),
}

_BACKEND_RE = re.compile(
    r"git\+https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/@.]+)(?:\.git)?"
    r"(?:@(?P<ref>.+))?$"
)
_FRONTEND_RE = re.compile(
    r"^(?:github:|git\+https://github\.com/)(?P<owner>[^/]+)/(?P<repo>[^#/]+?)"
    r"(?:\.git)?(?:#(?P<ref>.+))?$"
)


def _backend_pins(root: Path = REPO_ROOT) -> dict[str, tuple[str, str | None]]:
    data = tomllib.loads((root / "pyproject.toml").read_text())
    out: dict[str, tuple[str, str | None]] = {}
    for spec in data.get("project", {}).get("dependencies", []):
        # "name @ git+https://github.com/owner/repo.git@ref"
        if "git+https://github.com/" not in spec:
            continue
        url = spec.split("@", 1)[1].strip() if " @ " in spec else spec
        m = _BACKEND_RE.search(url)
        if m:
            out[m["repo"]] = (m["owner"], m["ref"])
    return out


def _frontend_pins(root: Path = REPO_ROOT) -> dict[str, tuple[str, str | None]]:
    data = json.loads((root / "package.json").read_text())
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    out: dict[str, tuple[str, str | None]] = {}
    for value in deps.values():
        if not isinstance(value, str):
            continue
        m = _FRONTEND_RE.match(value)
        if m:
            out[m["repo"]] = (m["owner"], m["ref"])
    return out


def mismatches(root: Path = REPO_ROOT) -> list[str]:
    """Human-readable lines, one per disagreeing repo; empty when all agree."""
    backend = _backend_pins(root)
    frontend = _frontend_pins(root)

    problems: list[str] = []
    for repo in TRACKED:
        b = backend.get(repo)
        f = frontend.get(repo)
        if b is None or f is None:
            continue
        b_owner, b_ref = b
        f_owner, f_ref = f
        if b_owner != f_owner:
            problems.append(
                f"{repo}: backend owner {b_owner!r} != frontend owner {f_owner!r}"
            )
            continue
        refs_agree = b_ref == f_ref or (f_ref is None and b_ref in DEFAULT_BRANCHES)
        if not refs_agree:
            problems.append(
                f"{repo}: backend ref {b_ref!r} != frontend ref {f_ref!r} "
                f"(pyproject.toml vs package.json)"
            )
    return problems


def main() -> int:
    problems = mismatches()
    if problems:
        print("fork pin mismatch -- frontend builds a different tree than the backend:")
        for line in problems:
            print(f"  {line}")
        print(
            "\nfix: edit package.json (and re-run `pnpm install --lockfile-only`) "
            "so the github: ref matches pyproject.toml, or vice versa."
        )
        return 1

    both = sorted(_backend_pins().keys() & _frontend_pins().keys() & TRACKED.keys())
    print(f"fork pins agree ({', '.join(both) or 'nothing tracked on both sides'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
