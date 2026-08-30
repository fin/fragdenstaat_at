"""The guard from fragdenstaat_at/theme/checks.py.

Worth testing both branches, because the failure it exists to catch is silent:
if the check itself quietly stopped firing, nothing else would notice.
"""

from pathlib import Path

import pytest

from fragdenstaat_at.theme import checks

# The check only fires when the sibling checkouts are on disk (a dev container).
# CI installs everything from the git pins and has no siblings, so
# check_editable_forks() short-circuits to [] and the two tests that assert on
# its behaviour cannot run there.
_has_siblings = (checks._workspace_root() / "froide").is_dir()
needs_siblings = pytest.mark.skipif(
    not _has_siblings, reason="needs the sibling checkouts a dev container has"
)


@needs_siblings
def test_no_error_when_everything_is_editable():
    assert checks.check_editable_forks(None) == []


@needs_siblings
def test_error_when_a_fork_is_installed_from_git(monkeypatch):
    root = checks._workspace_root()
    real = checks._module_path

    def fake(name):
        if name == "froide":
            return Path("/some/.venv/lib/python3.13/site-packages/froide/__init__.py")
        return real(name)

    monkeypatch.setattr(checks, "_module_path", fake)
    errors = checks.check_editable_forks(None)
    assert len(errors) == 1
    assert errors[0].id == "fragdenstaat_at.E001"
    assert "froide" in errors[0].msg
    assert "sync-editables.sh" in errors[0].msg
    # the two that are still editable must not be reported
    assert "froide_payment" not in errors[0].msg
    assert (root / "froide").is_dir()


def test_silent_when_there_is_no_sibling_checkout(monkeypatch, tmp_path):
    """Production: no siblings on disk, so the git pins are correct."""
    monkeypatch.setattr(checks, "_workspace_root", lambda: tmp_path)
    assert checks.check_editable_forks(None) == []
