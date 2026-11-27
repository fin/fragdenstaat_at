#!/usr/bin/env bash
# Web server, Celery worker and beat for browsing the staging copy.
# Ctrl-C stops all three. Logs: /srv/logs/{web,worker,beat}.log (in the
# container only). Mail and faxes are printed to worker.log / web.log, never
# sent (settings/staging.py).
#
#   NO_BEAT=1 to leave the periodic tasks off.
set -euo pipefail
cd /srv/app
export PATH=/srv/venv/bin:$PATH

pids=()
trap 'kill "${pids[@]}" 2>/dev/null; wait' EXIT INT TERM

python manage.py runserver 0.0.0.0:8001 --insecure >/srv/logs/web.log 2>&1 &
pids+=($!)
celery -A froide.celery worker -l info >/srv/logs/worker.log 2>&1 &
pids+=($!)
if [ "${NO_BEAT:-}" != 1 ]; then
  celery -A froide.celery beat -l info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler >/srv/logs/beat.log 2>&1 &
  pids+=($!)
fi

echo "web http://localhost:8001 (admin: /admin/), worker, ${NO_BEAT:+no }beat running."
echo "tail -f /srv/logs/*.log in another terminal. Ctrl-C stops everything."
wait -n
echo "a process exited, stopping the rest; see /srv/logs/" >&2
