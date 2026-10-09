#!/usr/bin/env sh
set -eu

uv run --no-sync python manage.py ensure_sqlite_wal
uv run --no-sync python manage.py migrate --noinput
exec uv run --no-sync uvicorn backend.config.asgi:application --host 0.0.0.0 --port 8000
