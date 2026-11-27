#!/usr/bin/env bash
# Sections 0-3 of docs/runbooks/p7-deployment-test.md, automated, for the
# staging container (.devcontainer/staging/). Section 4 (functional checks)
# stays manual: run serve.sh and browse.
#
# Prints and saves counts, types and migration names only, never values, so
# the report in ~/fds-at-staging/report/ (host) can be shared for review.
#
# Re-runnable: the pre-migration counts are saved on the first run and reused
# once the database is migrated. To start over, recreate the database (see
# .devcontainer/staging/README.md).
set -uo pipefail
cd /srv/app
export PATH=/srv/venv/bin:$PATH
export PGHOST=db PGUSER=fragdenstaat_at PGDATABASE=fragdenstaat_at PGPASSWORD=fragdenstaat_at

REPORT_DIR=/report
PRE="$REPORT_DIR/p7-pre-migration.txt"
REPORT="$REPORT_DIR/p7-report-$(date +%Y%m%d-%H%M%S).txt"
stops=()

q() { psql -X -q -A -t -F ' | ' -v ON_ERROR_STOP=1 -c "$1"; }
table() { psql -X -q -P footer=off -v ON_ERROR_STOP=1 -c "$1"; }
section() { printf '\n## %s\n\n' "$1"; }
stop() { stops+=("$1"); echo "STOP: $1"; }

exec > >(tee "$REPORT") 2>&1

echo "# P7 deployment test, $(date -Is)"
echo "commit: $(cat /srv/STAGING_COMMIT 2>/dev/null || git -c safe.directory='*' rev-parse HEAD)"

marker="$(q "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = current_database()")"
case "$marker" in
  "staging restore complete:"*) echo "database: restored (${marker#*: })" ;;
  *) echo "database: no restore marker, the dump did not restore completely."
     echo "Recreate the database (README.md) and check 'docker compose logs db'."
     exit 1 ;;
esac

migrated="$(q "SELECT count(*) FROM django_migrations WHERE app = 'fds_donation' AND name LIKE '0052%'")"

# --------------------------------------------------------------------------
section "0. Before migrating"
PRE_SQL="
SELECT
  (SELECT count(*) FROM fds_donation_donor),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes IS NOT NULL AND attributes <> ''::hstore),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'ibans'),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'old_data'),
  (SELECT count(*) FROM fds_donation_donation),
  (SELECT count(*) FROM froide_payment_payment),
  (SELECT count(*) FROM froide_payment_subscription),
  (SELECT count(*) FROM fds_mailing_conditioncmsplugin),
  (SELECT count(*) FROM django_site);"
COLS="donors donors_with_attributes donors_with_ibans donors_with_old_data donations payments subscriptions condition_plugins sites"

# The saved counts belong to one restore (the marker carries its timestamp).
# Never re-measure after a migrate has started, even a failed one: a partly
# migrated database would overwrite the baseline it is compared against.
if [ -f "$PRE" ] && [ "$(head -1 "$PRE")" = "$marker" ]; then
  pre="$(sed -n 2p "$PRE")"
  echo "(using the counts saved before the first migrate of this restore)"
elif [ "$migrated" = 0 ] && [ "$(q "SELECT count(*) FROM django_migrations WHERE app = 'fds_donation' AND name LIKE '0049%'")" = 0 ]; then
  pre="$(q "$PRE_SQL")" || { echo "pre-migration query failed"; exit 1; }
  printf '%s\n%s\n' "$marker" "$pre" > "$PRE"
  echo "(saved to ${PRE##*/})"
else
  echo "This restore is already (partly) migrated and its pre-migration counts were"
  echo "not saved. Recreate the database (README.md) and run this script first."
  exit 1
fi
read -r -a pre_vals <<<"$(echo "$pre" | tr -d '|')"
i=0; for c in $COLS; do printf '  %-24s %s\n' "$c" "${pre_vals[$i]}"; i=$((i+1)); done

echo
echo "Celery: tasks named in periodic tasks but unknown to the code (expect none):"
known="$(python - <<'EOF'
import configurations; configurations.setup()
from froide.celery import app
app.loader.import_default_modules()
print("\n".join(sorted(app.tasks)))
EOF
)"
q "SELECT DISTINCT task FROM django_celery_beat_periodictask WHERE enabled" | while read -r t; do
  grep -qxF "$t" <<<"$known" || echo "  unknown: $t"
done

# --------------------------------------------------------------------------
section "1. Migrate"
if [ "$migrated" = 0 ]; then
  echo "plan:"
  python manage.py migrate --plan | grep -E '^ *[a-z_]+\.[0-9]{4}' | sed 's/^ */  /'
  if python manage.py migrate --no-input >/srv/logs/migrate.log 2>&1; then
    echo "migrate: OK"
  else
    # Only the exception class: database error messages can quote row values.
    # Read /srv/logs/migrate.log yourself; do not paste it.
    exc="$(grep -oE '^[A-Za-z_.]+(Error|Exception)\b' /srv/logs/migrate.log | tail -1)"
    last="$(grep -oE 'Applying [a-z_]+\.[0-9]{4}[a-z0-9_]*' /srv/logs/migrate.log | tail -1)"
    stop "migrate failed: ${exc:-unknown error} during '${last#Applying }' (/srv/logs/migrate.log)"
  fi
else
  echo "already migrated (fds_donation 0052 applied), skipping"
fi

unapplied="$(python manage.py showmigrations 2>/dev/null | grep -c '\[ \]')"
echo "unapplied migrations: $unapplied"
[ "$unapplied" = 0 ] || stop "unapplied migrations remain"

pending="$(python manage.py makemigrations --check --dry-run 2>/dev/null \
  | sed -n "s/^Migrations for '\(.*\)':$/\1/p" | sort | tr '\n' ' ')"
echo "makemigrations --check lists: ${pending:-nothing} (expected: contractor sortabletable)"
for app in $pending; do
  case "$app" in contractor|sortabletable) ;; *) stop "unexpected model changes in $app" ;; esac
done

for m in "filer 0018" "djangocms_alias 0008" "djangocms_link 0020"; do
  set -- $m
  n="$(q "SELECT count(*) FROM django_migrations WHERE app = '$1' AND name LIKE '$2%'")"
  echo "lock-refresh migration $1 $2: $([ "$n" = 1 ] && echo applied || echo MISSING)"
  [ "$n" = 1 ] || stop "$1 $2 not applied"
done

# --------------------------------------------------------------------------
section "2. Donor attributes (hstore -> JSON)"
post="$(q "
SELECT
  (SELECT count(*) FROM fds_donation_donor),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes <> '{}'::jsonb),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'ibans'),
  (SELECT count(*) FROM fds_donation_donor WHERE attributes ? 'old_data');")"
read -r -a post_vals <<<"$(echo "$post" | tr -d '|')"
i=0
for c in donors donors_with_attributes donors_with_ibans donors_with_old_data; do
  verdict=OK; [ "${post_vals[$i]}" = "${pre_vals[$i]}" ] || { verdict=DIFFERS; stop "$c: ${pre_vals[$i]} before, ${post_vals[$i]} after"; }
  printf '  %-24s before %-8s after %-8s %s\n' "$c" "${pre_vals[$i]}" "${post_vals[$i]}" "$verdict"
  i=$((i+1))
done

echo
echo "shapes by key:"
table "SELECT key, jsonb_typeof(value) AS type, count(*)
       FROM fds_donation_donor, jsonb_each(attributes) GROUP BY 1, 2 ORDER BY 1, 2;"

bad_types="$(q "SELECT key || ':' || jsonb_typeof(value) FROM fds_donation_donor, jsonb_each(attributes)
  WHERE (key = 'ibans' AND jsonb_typeof(value) <> 'array')
     OR (key IN ('iban', 'banktransfer_reference') AND jsonb_typeof(value) <> 'string')
  GROUP BY 1")"
[ -z "$bad_types" ] || stop "unexpected attribute types: $(echo $bad_types)"

bad_ibans="$(q "SELECT count(*) FROM fds_donation_donor, jsonb_array_elements(attributes->'ibans') AS e
  WHERE jsonb_typeof(e) <> 'string' OR e #>> '{}' = '' OR e #>> '{}' LIKE '%;%' OR e #>> '{}' LIKE '[%'")"
echo "bad_iban_entries: $bad_ibans (expect 0)"
[ "$bad_ibans" = 0 ] || stop "bad_iban_entries is $bad_ibans"

# --------------------------------------------------------------------------
section "3. CMS and mailing data"
read -r sites site_settings <<<"$(q "SELECT (SELECT count(*) FROM django_site), (SELECT count(*) FROM fds_cms_sitesettings)" | tr -d '|')"
echo "sites: $sites, site_settings: $site_settings (expect equal)"
[ "$sites" = "$site_settings" ] || stop "sites and site_settings differ"

read -r cond empty <<<"$(q "SELECT count(*), count(*) FILTER (WHERE condition IN ('', 'False')) FROM fds_mailing_conditioncmsplugin" | tr -d '|')"
echo "condition_plugins: $cond (before: ${pre_vals[7]}), empty_conditions: $empty"
[ "$cond" = "${pre_vals[7]}" ] || stop "condition_plugins changed"
[ "$cond" = 0 ] || [ "$empty" = 0 ] || stop "empty conditions after the data migration"

echo
echo "collectstatic with production's ManifestStaticFilesStorage:"
if STAGING_MANIFEST=1 DJANGO_STATIC_ROOT=/srv/static-manifest \
   python manage.py collectstatic --no-input --clear >/srv/logs/collectstatic.log 2>&1; then
  echo "  OK"
else
  stop "collectstatic failed (/srv/logs/collectstatic.log)"; tail -3 /srv/logs/collectstatic.log | sed 's/^/  /'
fi

echo
echo "verify_render (every CMS page):"
python scripts/verify_render.py >/srv/logs/verify_render.log 2>&1
rc=$?
tail -3 /srv/logs/verify_render.log | sed 's/^/ /'
[ "$rc" = 0 ] || stop "verify_render reported failures (/srv/logs/verify_render.log)"

# --------------------------------------------------------------------------
section "Result"
if [ "${#stops[@]}" = 0 ]; then
  echo "Sections 0-3: PASS. Continue with section 4 of the runbook (serve.sh, then browse)."
else
  echo "Sections 0-3: ${#stops[@]} STOP(s):"
  printf '  - %s\n' "${stops[@]}"
fi
echo "report: ~/fds-at-staging/report/${REPORT##*/} on the host"
