"""scripts/check_fork_pins.py -- the guard that froide's frontend and backend
pins name the same tree.

The check is regex-parsing two hand-written files. If a regex silently stopped
matching, `mismatches()` would just return `[]` and the guard would pass while
guarding nothing -- so the synthetic cases below feed it known-bad pin sets and
assert it still objects.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_fork_pins", _ROOT / "scripts" / "check_fork_pins.py"
)
check_fork_pins = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_fork_pins)


def test_the_repos_own_pins_agree():
    """The real pyproject.toml / package.json must stay in step."""
    assert check_fork_pins.mismatches(_ROOT) == []


def _write(root: Path, backend_specs: list[str], frontend_deps: dict[str, str]):
    (root / "pyproject.toml").write_text(
        "[project]\ndependencies = [\n"
        + "".join(f'  "{s}",\n' for s in backend_specs)
        + "]\n"
    )
    (root / "package.json").write_text(json.dumps({"dependencies": frontend_deps}))


def test_agreement_on_a_branch(tmp_path):
    _write(
        tmp_path,
        ["froide @ git+https://github.com/fin/froide.git@some-branch"],
        {"froide": "github:fin/froide#some-branch"},
    )
    assert check_fork_pins.mismatches(tmp_path) == []


def test_flags_a_different_owner(tmp_path):
    _write(
        tmp_path,
        ["froide @ git+https://github.com/fin/froide.git@some-branch"],
        {"froide": "github:okfde/froide"},
    )
    problems = check_fork_pins.mismatches(tmp_path)
    assert len(problems) == 1
    assert "froide" in problems[0] and "owner" in problems[0]


def test_flags_a_different_branch(tmp_path):
    _write(
        tmp_path,
        ["froide-payment @ git+https://github.com/fin/froide-payment.git@branch-a"],
        {"froide_payment": "github:fin/froide-payment#branch-b"},
    )
    problems = check_fork_pins.mismatches(tmp_path)
    assert len(problems) == 1
    assert "froide-payment" in problems[0] and "ref" in problems[0]


def test_unspecified_npm_ref_accepted_only_against_a_default_branch(tmp_path):
    """`github:owner/repo` (no #ref) means the default branch."""
    _write(
        tmp_path,
        [
            "django-filingcabinet @ git+https://github.com/okfde/django-filingcabinet.git@main"
        ],
        {"@okfde/filingcabinet": "github:okfde/django-filingcabinet"},
    )
    assert check_fork_pins.mismatches(tmp_path) == []

    _write(
        tmp_path,
        ["froide @ git+https://github.com/okfde/froide.git@feature-x"],
        {"froide": "github:okfde/froide"},
    )
    problems = check_fork_pins.mismatches(tmp_path)
    assert len(problems) == 1
    assert "ref" in problems[0]


def test_untracked_repo_is_ignored(tmp_path):
    _write(
        tmp_path,
        ["froide-fax @ git+https://github.com/fin/froide-fax.git@main"],
        {"froide-fax": "github:someone-else/froide-fax#other"},
    )
    assert check_fork_pins.mismatches(tmp_path) == []


@pytest.mark.parametrize(
    "spec,expected",
    [
        (
            "froide @ git+https://github.com/fin/froide.git@2026-feat-x",
            ("fin", "2026-feat-x"),
        ),
        (
            "froide @ git+https://github.com/okfde/froide.git",
            ("okfde", None),
        ),
    ],
)
def test_backend_ref_parsing(tmp_path, spec, expected):
    _write(tmp_path, [spec], {})
    assert check_fork_pins._backend_pins(tmp_path)["froide"] == expected
