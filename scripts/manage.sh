#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ -f .env ]; then
    exec uv run --env-file .env python manage.py "$@"
fi
exec uv run python manage.py "$@"
