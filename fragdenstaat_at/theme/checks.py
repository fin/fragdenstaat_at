"""Refuse to start when the sibling forks are installed from git instead of ../.

`uv sync` installs exactly what `pyproject.toml` declares, and AT declares
froide, froide-payment and django-filingcabinet as git pins -- that is what
production needs, since production has no sibling checkouts and deploys with
`uv sync --locked`. In the devcontainer those three are meant to be *editable*
installs of the sibling checkouts devsetup.sh creates, so local edits take
effect without a reinstall.

Any `uv sync` therefore silently reverts them to the pinned git revisions. The
failure is invisible: everything imports, the suite runs, and you are testing
upstream `main` instead of your own checkout. There is no uv setting that fixes
this -- `uv.lock` holds one source per package, and `--locked` asserts the lock
matches `pyproject.toml`, so a lockfile cannot describe the git pin for
production and the local path for dev at the same time.

So detect it instead. The check scopes itself: it only fires when the sibling
directory actually exists, which is true in the devcontainer and false in
production, where it is a silent no-op.
"""

import sys
from pathlib import Path

from django.core.checks import Error, register

# Import name -> sibling repo directory name. django-filingcabinet uses a src/
# layout, so compare against the repo root rather than the package directory.
EDITABLE_FORKS = {
    "froide": "froide",
    "froide_payment": "froide-payment",
    "filingcabinet": "django-filingcabinet",
}


def _workspace_root():
    """The directory holding fragdenstaat_at/ and its siblings."""
    # .../fds_at/fragdenstaat_at/fragdenstaat_at/theme/checks.py
    return Path(__file__).resolve().parents[3]


def _module_path(name):
    module = sys.modules.get(name)
    if module is None:
        import importlib

        try:
            module = importlib.import_module(name)
        except ImportError:
            return None
    origin = getattr(module, "__file__", None)
    return Path(origin).resolve() if origin else None


def check_editable_forks(app_configs, **kwargs):
    root = _workspace_root()
    stale = []

    for module_name, repo_dir in sorted(EDITABLE_FORKS.items()):
        sibling = root / repo_dir
        if not sibling.is_dir():
            # No sibling checkout: production, or a partial dev setup. Either
            # way the git pin is the only thing available and is correct.
            continue
        installed = _module_path(module_name)
        if installed is None or not installed.is_relative_to(sibling):
            stale.append((module_name, repo_dir, installed))

    if not stale:
        return []

    detail = "\n".join(
        f"    {name} -> {path if path else '(not importable)'}"
        for name, _repo, path in stale
    )
    repos = " ".join(repo for _name, repo, _path in stale)
    return [
        Error(
            "Sibling checkouts exist but these packages are installed from "
            "elsewhere (almost certainly the git pins, after a `uv sync`):\n"
            f"{detail}\n"
            "  You would be running upstream code, not your local checkout.\n"
            "  Fix: ./scripts/sync-editables.sh"
            + (f"   # affected: {repos}" if len(stale) < len(EDITABLE_FORKS) else ""),
            hint=(
                "`uv sync` reinstalls froide, froide-payment and "
                "django-filingcabinet from the git revisions pinned in "
                "pyproject.toml, replacing the editable installs. This is "
                "expected -- production needs those pins -- so re-apply the "
                "editable installs afterwards."
            ),
            id="fragdenstaat_at.E001",
        )
    ]


def register_checks():
    register(check_editable_forks)
