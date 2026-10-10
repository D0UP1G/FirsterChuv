#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ ! -f .env ]; then
    printf '%s\n' 'Создайте .env из .env.example и задайте приватный DJANGO_SECRET_KEY.' >&2
    exit 1
fi
if grep -Eq '^DJANGO_SECRET_KEY=(|replace-before-sharing)$' .env; then
    printf '%s\n' 'Задайте приватный DJANGO_SECRET_KEY в .env до запуска.' >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Для запуска нужен Docker CLI.' >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    printf '%s\n' 'Docker Engine недоступен текущему пользователю.' >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    printf '%s\n' 'Для запуска нужен Docker Compose plugin.' >&2
    exit 1
fi
if [ ! -S /var/run/docker.sock ]; then
    printf '%s\n' 'Не найден Linux Docker socket /var/run/docker.sock.' >&2
    exit 1
fi

docker_socket_gid=$(stat -c '%g' /var/run/docker.sock)
case "$docker_socket_gid" in
    ''|*[!0-9]*)
        printf '%s\n' 'Не удалось определить группу Docker socket.' >&2
        exit 1
        ;;
esac
export DOCKER_SOCKET_GID="$docker_socket_gid"

docker build \
    --platform=linux/amd64 \
    --tag firsterchuv/sandbox-cpp:0.1.0 \
    sandbox
docker compose up --build
