#!/usr/bin/env bash
# Re-install the sibling forks as editable, after a `uv sync` reverted them.
#
#   ./scripts/sync-editables.sh          # re-apply all three
#   ./scripts/sync-editables.sh --check  # report only, exit 1 if any are stale
#
# `uv sync` installs what pyproject.toml declares, and AT declares froide,
# froide-payment and django-filingcabinet as git pins -- production has no
# sibling checkouts and deploys with `uv sync --locked`. In dev those three
# should be editable installs of ../, so every `uv sync` silently undoes them
# and you end up testing upstream `main`. No uv setting avoids this: uv.lock
# holds one source per package, so it cannot describe both.
#
# Same flags devsetup.sh uses, so this is a subset of a full setup run, not a
# competing one. Safe to run at any time; it is idempotent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(dirname "$REPO_ROOT")"
PYTHON="$REPO_ROOT/.venv/bin/python"
REPOS=("froide" "froide-payment" "django-filingcabinet")

[ -x "$PYTHON" ] || { echo "error: no virtualenv at $REPO_ROOT/.venv" >&2; exit 1; }

# import name for each repo, to report where it currently resolves
module_for() {
  case "$1" in
    froide)               echo froide ;;
    froide-payment)       echo froide_payment ;;
    django-filingcabinet) echo filingcabinet ;;
  esac
}

resolves_to() {
  "$PYTHON" - "$1" <<'PY' 2>/dev/null || true
import importlib.util, sys
spec = importlib.util.find_spec(sys.argv[1])
print(spec.origin if spec and spec.origin else "")
PY
}

stale=()
for repo in "${REPOS[@]}"; do
  [ -d "$WORKSPACE/$repo" ] || { echo "skip $repo (no checkout at $WORKSPACE/$repo)"; continue; }
  where="$(resolves_to "$(module_for "$repo")")"
  case "$where" in
    "$WORKSPACE/$repo"/*) echo "ok   $repo -> editable" ;;
    *)                    echo "STALE $repo -> ${where:-not importable}"; stale+=("$repo") ;;
  esac
done

if [ ${#stale[@]} -eq 0 ]; then
  echo "all editable, nothing to do"
  exit 0
fi

if [ "${1:-}" = "--check" ]; then
  echo "run ./scripts/sync-editables.sh to fix" >&2
  exit 1
fi

for repo in "${stale[@]}"; do
  echo "reinstalling $repo as editable ..."
  uv pip install --python "$PYTHON" -e "$WORKSPACE/$repo" \
    --config-setting editable_mode=compat --no-deps --quiet
done
echo "done"
