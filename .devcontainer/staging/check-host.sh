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
