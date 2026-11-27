#!/usr/bin/env bash
# Runs on the HOST (devcontainer initializeCommand), before any container
# starts. Makes sure the production dump lives outside the workspace, where
# the dev container (and anything running in it) cannot read it.
set -euo pipefail

base="$HOME/fds-at-staging"
mkdir -p "$base/dump" "$base/report"

shopt -s nullglob
dumps=("$base"/dump/*)
if [ "${#dumps[@]}" -ne 1 ]; then
  echo "Put exactly one production dump into $base/dump/ (found ${#dumps[@]})." >&2
  echo "Make it with: pg_dump -Fc --no-owner --no-acl <db> > fragdenstaat_at.dump" >&2
  exit 1
fi

workspace="$(cd "$(dirname "$0")/../../.." && pwd -P)"
dump_real="$(cd "$base/dump" && pwd -P)"
case "$dump_real/" in
  "$workspace"/*)
    echo "$base/dump resolves into the workspace ($workspace). Move it out." >&2
    exit 1 ;;
esac

echo "Staging dump: ${dumps[0]##*/}"

# Reuse the dev container's package caches (downloads only, no data). Compose
# prefixes volume names with its project name, so look the real names up and
# hand them to compose.yaml via .env (compose reads it from this directory).
# Without a dev cache, staging gets its own, created here.
pick_volume() {
  local all found
  all="$(docker volume ls -q)"
  for pattern in "^$1\$" "devcontainer_$1\$" "_$1\$"; do
    found="$(grep -E "$pattern" <<<"$all" | grep -v '^fds-at-staging_' | head -1 || true)"
    [ -n "$found" ] && { echo "$found"; return; }
  done
  docker volume create "fds-at-staging_$1" >/dev/null
  echo "fds-at-staging_$1"
}
uv_vol="$(pick_volume uv_cache)"
pnpm_vol="$(pick_volume pnpm_cache)"
printf 'STAGING_UV_CACHE=%s\nSTAGING_PNPM_CACHE=%s\n' "$uv_vol" "$pnpm_vol" \
  > "$(dirname "$0")/.env"
echo "Package caches: $uv_vol, $pnpm_vol"
