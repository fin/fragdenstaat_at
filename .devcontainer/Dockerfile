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

RUN apt-get install ghostscript poppler-utils

# Activate the project virtualenv in every interactive shell. The VS Code
# Python extension's terminal activation is racy (only works for terminals
# opened after the extension has activated), so do it deterministically here.
RUN printf '%s\n' '' \
    '# auto-activate fragdenstaat_at virtualenv' \
    'if [ -z "$VIRTUAL_ENV" ] && [ -f /workspaces/fds_at/fragdenstaat_at/.venv/bin/activate ]; then' \
    '    source /workspaces/fds_at/fragdenstaat_at/.venv/bin/activate' \
    'fi' >> /home/vscode/.bashrc
