#!/usr/bin/env bash
# Re-link the sibling forks into this checkout, after `uv sync` / `pnpm install`
# reverted them to the pinned revisions.
#
#   ./scripts/sync-editables.sh          # re-apply everything (Python + frontend)
#   ./scripts/sync-editables.sh --check  # report only, exit 1 if anything is stale
#
# Two independent link sets, same failure mode:
#
#  * Python -- pyproject.toml declares froide, froide-payment, froide-fax and
#    django-filingcabinet as git pins, because production has no sibling
#    checkouts and deploys with `uv sync --locked`. In dev those four should be
#    `uv pip install -e ../<repo>`, and every `uv sync` silently reverts them,
#    so you end up testing the pinned revision instead of your checkout.
#
#  * Frontend -- package.json pins froide, froide_payment and
#    @okfde/filingcabinet as `github:` deps so CI can build the Vue/TS sources.
#    In dev those three should be `pnpm link --global` to ../<repo> (a global
#    link, because a local one rewrites pnpm-lock.yaml). Every bare
#    `pnpm install` reverts them, after which `pnpm run build` compiles the
#    pinned revision instead of your checkout.
#
# What this does NOT touch: the committed pins themselves. Keeping package.json's
# fork ref in step with pyproject.toml's is a separate, CI-side concern --
# scripts/check_fork_pins.py, wired into .pre-commit-config.yaml.
#
# Same operations devsetup.sh runs, so this is a subset of a full setup run, not
# a competing one. Idempotent; safe to run at any time.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$(dirname "$REPO_ROOT")"
PYTHON="$REPO_ROOT/.venv/bin/python"

CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

[ -x "$PYTHON" ] || { echo "error: no virtualenv at $REPO_ROOT/.venv" >&2; exit 1; }

# ---------------------------------------------------------------- Python installs

PY_REPOS=("froide" "froide-payment" "froide-fax" "django-filingcabinet")

module_for() {  # repo dir -> import name
  case "$1" in
    froide)               echo froide ;;
    froide-payment)       echo froide_payment ;;
    froide-fax)           echo froide_fax ;;
    django-filingcabinet) echo filingcabinet ;;
  esac
}

py_resolves_to() {
  "$PYTHON" - "$1" <<'PY' 2>/dev/null || true
import importlib.util, sys
spec = importlib.util.find_spec(sys.argv[1])
print(spec.origin if spec and spec.origin else "")
PY
}

py_stale=()
for repo in "${PY_REPOS[@]}"; do
  [ -d "$WORKSPACE/$repo" ] || { echo "skip  $repo (no checkout at $WORKSPACE/$repo)"; continue; }
  where="$(py_resolves_to "$(module_for "$repo")")"
  case "$where" in
    "$WORKSPACE/$repo"/*) echo "ok    $repo (py) -> editable" ;;
    *)                    echo "STALE $repo (py) -> ${where:-not importable}"; py_stale+=("$repo") ;;
  esac
done

# --------------------------------------------------------------- Frontend links

# npm package name : sibling repo dir  (index-aligned)
FE_NAMES=("froide" "froide_payment" "@okfde/filingcabinet")
FE_DIRS=( "froide" "froide-payment" "django-filingcabinet")

have_pnpm=true
command -v pnpm >/dev/null 2>&1 || have_pnpm=false

fe_stale_names=()
fe_stale_dirs=()
if $have_pnpm && [ -f "$REPO_ROOT/package.json" ]; then
  for i in "${!FE_NAMES[@]}"; do
    name="${FE_NAMES[$i]}"; dir="${FE_DIRS[$i]}"
    [ -d "$WORKSPACE/$dir" ] || { echo "skip  $dir (no checkout at $WORKSPACE/$dir)"; continue; }
    target="$(readlink -f "$REPO_ROOT/node_modules/$name" 2>/dev/null || true)"
    case "$target" in
      "$WORKSPACE/$dir" | "$WORKSPACE/$dir"/*)
        echo "ok    $dir (js) -> linked" ;;
      *)
        echo "STALE $dir (js) -> ${target:-not installed}"
        fe_stale_names+=("$name"); fe_stale_dirs+=("$dir") ;;
    esac
  done
elif ! $have_pnpm; then
  echo "skip  frontend links (pnpm not found)"
fi

# -------------------------------------------------------------- result / repair

if [ ${#py_stale[@]} -eq 0 ] && [ ${#fe_stale_names[@]} -eq 0 ]; then
  echo "all linked, nothing to do"
  exit 0
fi

if $CHECK_ONLY; then
  echo "run ./scripts/sync-editables.sh to fix" >&2
  exit 1
fi

for repo in "${py_stale[@]}"; do
  echo "reinstalling $repo as editable ..."
  uv pip install --python "$PYTHON" -e "$WORKSPACE/$repo" \
    --config-setting editable_mode=compat --no-deps --quiet
done

for i in "${!fe_stale_names[@]}"; do
  name="${fe_stale_names[$i]}"; dir="${fe_stale_dirs[$i]}"
  echo "re-linking $dir (pnpm global link) ..."
  if ! ( cd "$WORKSPACE/$dir" && pnpm link --global ) >/dev/null 2>&1 \
     || ! ( cd "$REPO_ROOT" && pnpm link --global "$name" ) >/dev/null 2>&1; then
    echo "  warning: pnpm link failed for $dir -- run ./devsetup.sh frontend" >&2
  fi
done

echo "done"
