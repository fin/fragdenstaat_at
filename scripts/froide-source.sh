#!/usr/bin/env bash
# Switch the sibling froide checkout between upstream (okfde) and the fork (fin).
#
#   ./scripts/froide-source.sh status   # which source is active
#   ./scripts/froide-source.sh okfde    # upstream — the porting baseline
#   ./scripts/froide-source.sh fin      # the fork — fax transport / translation work
#
# froide is installed *editable* from ../froide, so switching the checkout is all
# that is required — no `uv sync`, no reinstall. Uncommitted local edits (e.g. the
# devcontainer DB/ES host tweaks in froide/settings.py) are carried across.
set -euo pipefail

FROIDE_DIR="${FROIDE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/froide}"
OKFDE_URL="https://github.com/okfde/froide.git"
FORK_BRANCH="${FROIDE_FORK_BRANCH:-2026-feat-messagekind-initial-message}"
OKFDE_BRANCH="okfde-main"

[ -d "$FROIDE_DIR/.git" ] || { echo "error: no froide checkout at $FROIDE_DIR" >&2; exit 1; }
cd "$FROIDE_DIR"

# Resolve remotes by URL, not by name — `origin` may be either fork or upstream
# depending on whether the checkout came from devsetup.sh or was repointed by hand.
remote_for() {  # $1 = substring to match in the remote URL
  git remote -v | awk -v pat="$1" '$3=="(fetch)" && index($2,pat){print $1; exit}'
}

ensure_okfde_remote() {
  local r; r=$(remote_for "okfde/froide")
  if [ -z "$r" ]; then git remote add okfde "$OKFDE_URL"; r=okfde; fi
  echo "$r"
}

fork_remote() {
  local r; r=$(remote_for "fin/froide")
  [ -n "$r" ] || { echo "error: no remote pointing at fin/froide; add one first" >&2; exit 1; }
  echo "$r"
}

dirty_note() {
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "  local uncommitted edits (carried across the switch):"
    git diff --stat HEAD | sed 's/^/    /'
  fi
}

case "${1:-status}" in
  status)
    up=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo "(none)")
    url=$(git remote get-url "${up%%/*}" 2>/dev/null || echo "?")
    case "$url" in
      *okfde/froide*) src="UPSTREAM (okfde)";;
      *fin/froide*)   src="FORK (fin)";;
      *)              src="unknown";;
    esac
    echo "froide source : $src"
    echo "checkout      : $FROIDE_DIR"
    echo "branch        : $(git branch --show-current)  ->  $up"
    echo "commit        : $(git log -1 --format='%h %s')"
    ok=$(remote_for "okfde/froide")
    if [ -n "$ok" ] && git rev-parse -q --verify "$ok/main" >/dev/null; then
      ahead=$(git rev-list --count "$ok/main..HEAD" 2>/dev/null || echo '?')
      echo "vs okfde/main : $ahead commit(s) ahead"
    fi
    dirty_note
    ;;

  okfde|upstream)
    r=$(ensure_okfde_remote)
    echo "fetching $r ..."; git fetch --quiet "$r" main
    if git rev-parse -q --verify "$OKFDE_BRANCH" >/dev/null; then
      git checkout --quiet "$OKFDE_BRANCH" && git merge --quiet --ff-only "$r/main"
    else
      git checkout --quiet -b "$OKFDE_BRANCH" --track "$r/main"
    fi
    echo "→ froide now on UPSTREAM ($r/main): $(git log -1 --format='%h %s')"
    dirty_note
    cat <<'NOTE'

  froide is installed editable — nothing to reinstall.

  ⚠️  Migration divergence: the fork adds foirequest/0076_alter_foimessage_kind,
      which does not exist upstream (upstream head is 0075). A database that was
      migrated against the fork therefore has an applied migration with no file.
      Use a FRESH scratch database for upstream verification runs:
        psql -h db -U fragdenstaat_at -d postgres -c "CREATE DATABASE fds_verify_okfde"
      See MERGE_PLAN.md §1b.
NOTE
    ;;

  fin|fork)
    r=$(fork_remote)
    echo "fetching $r ..."; git fetch --quiet "$r" "$FORK_BRANCH"
    git checkout --quiet "$FORK_BRANCH"
    echo "→ froide now on FORK ($r/$FORK_BRANCH): $(git log -1 --format='%h %s')"
    dirty_note
    echo
    echo "  froide is installed editable — nothing to reinstall."
    ;;

  *) sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1;;
esac
