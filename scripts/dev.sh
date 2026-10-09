#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ ! -f .env ]; then
    printf '%s\n' 'Создайте .env на основе .env.example перед запуском.' >&2
    exit 2
fi

uv run --env-file .env python manage.py ensure_sqlite_wal
uv run --env-file .env python manage.py migrate --noinput
exec uv run --env-file .env python manage.py runserver 127.0.0.1:8000
