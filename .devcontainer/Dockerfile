FROM mcr.microsoft.com/devcontainers/python:3.13-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    binutils \
    libproj-dev \
    libpq-dev \
    gdal-bin \
    libgeos-dev \
    libgdal-dev \
    gettext \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN UV_TOOL_DIR=/usr/local/share/uv/tools UV_TOOL_BIN_DIR=/usr/local/bin uv tool install prek

RUN apt-get update && apt-get install -y ghostscript poppler-utils

# Stripe CLI — needed by fds_donation's Stripe tests, which use `stripe listen`
# to tunnel real test-mode webhooks to the local live_server. Not in apt, and
# the arch differs between Apple Silicon and CI, so resolve it at build time.
RUN set -eux; \
    case "$(uname -m)" in \
      aarch64) arch=linux_arm64 ;; \
      x86_64)  arch=linux_x86_64 ;; \
      *) echo "unsupported arch $(uname -m)" >&2; exit 1 ;; \
    esac; \
    ver="$(curl -fsSL https://api.github.com/repos/stripe/stripe-cli/releases/latest \
           | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p' | head -1)"; \
    curl -fsSL "https://github.com/stripe/stripe-cli/releases/download/v${ver}/stripe_${ver}_${arch}.tar.gz" \
      | tar -xz -C /usr/local/bin stripe; \
    chmod 0755 /usr/local/bin/stripe; \
    stripe --version

# Activate the project virtualenv in every interactive shell. The VS Code
# Python extension's terminal activation is racy (only works for terminals
# opened after the extension has activated), so do it deterministically here.
RUN printf '%s\n' '' \
    '# auto-activate fragdenstaat_at virtualenv' \
    'if [ -z "$VIRTUAL_ENV" ] && [ -f /workspaces/fds_at/fragdenstaat_at/.venv/bin/activate ]; then' \
    '    source /workspaces/fds_at/fragdenstaat_at/.venv/bin/activate' \
    'fi' >> /home/vscode/.bashrc
