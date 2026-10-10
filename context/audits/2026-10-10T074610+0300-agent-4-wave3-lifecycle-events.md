# Agent 4 · Wave 3 lifecycle/domain seam · 2026-10-10 07:46 +0300

## Цель

Закрыть обнаруженный в Wave 2 разрыв между T11 admin transitions и public SSE: event store и DB constraint принимали только `score.changed`, поэтому pause/resume/extend/technical result/rematch/replacement не могли попасть в публичный поток. Сверить изменения с T09–T11, кейсом и Wave 3 ROADMAP.

## Основание и границы

- База: `origin/develop` `7b23470535c15c1baa9cc0018796a3519a10aa7b`; ветка `feature/a4-wave3-domain-fixes`.
- ROADMAP v6 относит к A4 Wave 3 доменные стыки и T09–T11. Ledger T09/T10 и winner promotion уже интегрированы PR #76; score event producer связан транзакционно.
- Кейсовые требования администрирования и зрительского хода сохраняются: причина и actor остаются в закрытой admin receipt; публичный DTO не раскрывает их.
- Не менялись A3 `submissions`/queue/judge и A5 frontend. Accepted-submission event producer оставлен отдельным A3/A4 integration seam.

## Реализация

- Добавлен `match.admin_action` с точной схемой `{action, status, revision}`, строгой allowlist-валидацией и миграцией `events.0003_admin_action_events`.
- Admin transition записывает событие через существующий `append_event` внутри транзакции команды; receipt replay возвращает прежний результат до event append, поэтому exact retry не дублирует событие.
- API-документация обновлена по фактическим Wave 2 маршрутам: UUID bracket и per-match SSE; перечислены типы событий, доступные текущему хранилищу.
- ROADMAP и карточка A4 синхронизированы; общий STATE не менялся, так как эта работа ещё не слита в develop.

## Проверки

- `DJANGO_DEBUG=true SQLITE_PATH=/tmp/a4-wave3-events.sqlite3 uv run --locked python manage.py test backend.apps.events.tests --verbosity 1` — PASS, 16/16.
- `DJANGO_DEBUG=true SQLITE_PATH=/tmp/a4-wave3-admin.sqlite3 uv run --locked python manage.py test backend.apps.competition.tests.test_admin_runtime --verbosity 1` — PASS, 11/11.
- `DJANGO_DEBUG=true SQLITE_PATH=/tmp/a4-wave3-drift.sqlite3 uv run --locked python manage.py makemigrations --check --dry-run` — PASS, no changes detected.
- `DJANGO_DEBUG=true SQLITE_PATH=/tmp/a4-wave3-check.sqlite3 uv run --locked python manage.py check` — PASS; `git diff --check` — PASS.
- Наборы тестов запущены параллельно на отдельных SQLite путях; полный backend/frontend/M0 не запускался.

## Ограничения и следующий шаг

- `submission.accepted`/accepted-submission producer не подключён в этой ветке, так как его transactional source находится в зоне A3; это не объявляет T09 полностью принятым. Нужен короткий CONNECT с A3 на event hook и payload.
- `match.admin_action` сигнализирует изменение административного состояния; это не добавляет отдельные `match.started` или `bracket.advanced` события и не закрывает T16/T17/T20/M0.
- Следующий шаг: review миграции/diff, commit и PR в `develop`, exact-head CI; после merge обновить STATE и продолжить доступные Wave 3 A4 подпункты после свежего `origin/develop`.
