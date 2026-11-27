# Staging container: deployment test against a copy of production

A second devcontainer for running `docs/runbooks/p7-deployment-test.md` (and
its successors) against a production dump on your own machine.

**The database is live data: real users, donors, IBANs, addresses.** The rule
from MERGE_PLAN P7.3 applies: no AI tooling touches it. This setup keeps the
data out of the dev container. That only works if you keep to the procedure
below.

## What is isolated, and what isn't

| | |
|---|---|
| **Dump file** | Stays in `~/fds-at-staging/dump/` on the host, outside the workspace. `check-host.sh` refuses to start otherwise. Only the `db` container mounts it, read-only. |
| **Database** | Its own compose project (`fds-at-staging`), its own network and volume. The dev container cannot resolve or reach it, and no port is published to the host. |
| **App files** | The workspace is mounted **read-only** at `/src`. The app runs from a clone in a container-local volume (`/srv/app`, venv `/srv/venv`, media, logs), so nothing staging writes lands in the shared workspace. |
| **Report** | `~/fds-at-staging/report/` on the host. Counts, types and migration names only, so you can share it. |
| **Outbound** | `settings/staging.py`: mail and faxes go to the console, payments use sandbox keys or none, Sentry is off. It refuses to start if production credentials are in the environment. |
| **AI extensions** | The Claude Code and Copilot extensions are removed in this container (`"-…"` in devcontainer.json). |
| **Not isolated: the web UI** | Port 8001 is forwarded by VS Code to `localhost` on the host. Other containers can reach host ports via `host.docker.internal`, and that includes the dev container. |

So the one rule that isolation cannot replace: **close any Claude Code session
(in the dev container or on the host) while the staging stack is running.**
Then delete the database when you are done.

## Use

1. **Make the dump** on production (or wherever you take it from) and copy
   it to the host:

   ```sh
   pg_dump -Fc --no-owner --no-acl <db> > fragdenstaat_at.dump
   mkdir -p ~/fds-at-staging/dump && mv fragdenstaat_at.dump ~/fds-at-staging/dump/
   ```

   Exactly one file. `.sql`, `.sql.gz` and custom format (`-Fc`) all work.
   Media files are not included, so existing attachments 404. PDFs generated
   on the fly (request PDFs, faxes) work.

2. **Close Claude Code**, then in VS Code: *Dev Containers: Reopen in
   Container* → **FragDenStaat AT staging (LIVE DATA)** (red title bar).
   The first start restores the dump. That takes a while; `docker compose -p
   fds-at-staging logs -f db` on the host shows progress. Then `setup.sh`
   installs the committed `HEAD` the way production does: `uv sync --locked
   --no-dev --extra production`, frozen pnpm install, production build,
   compilemessages. Uncommitted changes are not tested. To test another
   commit, set `STAGING_REF` in the container and rerun `setup.sh`.

   **Run every command from `/srv/app`**, not from the opened folder
   `/src/fragdenstaat_at`. There, `manage.py` would import the working tree
   and stop with `fragdenstaat_at.E001` (sibling checkouts found). New
   terminals start in `/srv/app`.

3. **Automated part** (runbook sections 0–3), in a container terminal:

   ```sh
   cd /srv/app && bash scripts/staging/p7-deploy-test.sh
   ```

   It records the pre-migration counts and runs `migrate`. It then compares
   donor counts and attribute shapes, checks the three lock-refresh
   migrations, `makemigrations --check`, sites/site settings and condition
   plugins. It also runs `collectstatic` with production's manifest storage and
   renders every CMS page. It ends with PASS or a list of STOPs. It is safe to
   rerun.

4. **Browse** (runbook section 4):

   ```sh
   bash /src/fragdenstaat_at/.devcontainer/staging/serve.sh   # NO_BEAT=1 to skip beat
   ```

   <http://localhost:8001>. The admin is at `/admin/`, and production accounts
   work with their production passwords. Mail and faxes show up in
   `/srv/logs/worker.log` and `/srv/logs/web.log`. Beat runs production's
   periodic tasks against the copy; that's harmless, nothing leaves. Search is
   empty until you run `python manage.py search_index --rebuild -f`
   (optional, slow).

5. **Clean up** on the host, once you have the report:

   ```sh
   docker compose -p fds-at-staging down -v      # deletes the restored database and /srv
   rm ~/fds-at-staging/dump/*
   ```

   To start over with the same dump, run just the first command and reopen the
   container.
   If compose reports no such project, `docker compose ls` shows the name the
   Dev Containers extension used.

## Not covered here

- **Feedback-ID / DKIM** needs real outbound mail. Check it after the
  production deploy instead.
- **Postgres version.** The staging db is `postgis/postgis:17-3.5`, because
  pg_dump 17 writes a format 16 cannot restore ("unsupported version (1.16)
  in file header"). If production's server is a different major version,
  set `STAGING_PG_IMAGE_TAG` in the host environment (e.g. `18-3.6`) and
  recreate the database with `down -v`.
