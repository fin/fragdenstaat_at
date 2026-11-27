#!/usr/bin/env bash
# postCreateCommand of the staging container. Installs the committed code the
# way production does: a clean clone, `uv sync --locked` with the production
# extra and no dev tools, a frozen pnpm install, a production frontend build.
# Does NOT migrate: the deploy test needs the pre-migration state first.
#
#   STAGING_REF=<commit|branch> to test something other than the source's HEAD.
set -euo pipefail

SRC=/src/fragdenstaat_at
APP=/srv/app
git_src() { git -c safe.directory='*' -C "$SRC" "$@"; }

sudo chown vscode: /srv /home/vscode/.local/share/uv /home/vscode/.local/share/pnpm
mkdir -p /srv/media /srv/static /srv/logs

pnpm_version="$(sed -n 's/.*"packageManager": *"pnpm@\([^"]*\)".*/\1/p' "$SRC/package.json")"
npm install -g "pnpm@${pnpm_version}"

ref="$(git_src rev-parse "${STAGING_REF:-HEAD}")"
if [ ! -d "$APP/.git" ]; then
  git -c safe.directory='*' clone --quiet "$SRC" "$APP"
fi
cd "$APP"
git -c safe.directory='*' fetch --quiet origin
git -c safe.directory='*' checkout --quiet --detach "$ref"
if [ -n "$(git_src status --porcelain --untracked-files=no)" ]; then
  echo "note: $SRC has uncommitted changes; staging tests the commit $ref only."
fi
echo "$ref" > /srv/STAGING_COMMIT

export UV_PYTHON=3.13
uv sync --locked --no-dev --extra production

pnpm install --frozen-lockfile
pnpm run build

/srv/venv/bin/python manage.py compilemessages -i node_modules -i .venv >/dev/null

cat <<EOF

Staging is installed at $APP ($(git -c safe.directory='*' log -1 --format='%h %s')).
Next, in a terminal here:
  cd $APP && bash scripts/staging/p7-deploy-test.sh   # sections 0-3 of the runbook
  bash $SRC/.devcontainer/staging/serve.sh            # then browse http://localhost:8002
EOF
