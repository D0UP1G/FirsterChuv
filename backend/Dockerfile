FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=uv /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY manage.py ./manage.py
COPY backend ./backend
COPY scripts ./scripts
RUN uv sync --frozen --no-dev \
    && useradd --system --uid 10001 --create-home app \
    && mkdir -p /app/.data \
    && chown -R app:app /app

USER 10001:10001
EXPOSE 8000
CMD ["/app/scripts/start-api.sh"]
