#!/usr/bin/env bash
# Run by the postgis entrypoint on the first start of an empty pg-data volume.
# Restores the one dump in /dump into $POSTGRES_DB.
set -euo pipefail

shopt -s nullglob
dumps=(/dump/*)
if [ "${#dumps[@]}" -ne 1 ]; then
  echo "expected exactly one file in /dump, found ${#dumps[@]}" >&2
  exit 1
fi
dump="${dumps[0]}"
db=(--username "$POSTGRES_USER" --dbname "$POSTGRES_DB")

# hstore is what the pre-migration donor queries need; the dump normally
# creates it (and postgis) itself, IF NOT EXISTS makes that harmless.
psql -v ON_ERROR_STOP=1 "${db[@]}" -c 'CREATE EXTENSION IF NOT EXISTS hstore'

echo "restoring ${dump##*/} ..."
case "$dump" in
  *.sql)    psql -v ON_ERROR_STOP=1 -q "${db[@]}" -f "$dump" ;;
  *.sql.gz) gunzip -c "$dump" | psql -v ON_ERROR_STOP=1 -q "${db[@]}" ;;
  *)        pg_restore --no-owner --no-acl --exit-on-error "${db[@]}" "$dump" ;;
esac

# If a restore fails half-way, the entrypoint stops, but pg-data is already
# initialised and the next start skips this script: the deploy-test script
# refuses to run without this marker.
psql -v ON_ERROR_STOP=1 "${db[@]}" -c \
  "COMMENT ON DATABASE \"$POSTGRES_DB\" IS 'staging restore complete: ${dump##*/} at $(date -u +%FT%TZ)'"
echo "restore done"
