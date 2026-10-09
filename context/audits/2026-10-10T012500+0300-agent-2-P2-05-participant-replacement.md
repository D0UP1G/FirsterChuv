# Аудит: Agent 2 / P2-05 persisted participant replacement

- Автор/роль агента: Codex / Agent 2.
- Начало и окончание: `2026-10-10T01:18:00+03:00` — `2026-10-10T01:25:00+03:00` (Europe/Moscow).
- ID задач: P2-05 / M08 / T11.
- Ветка: `feature/a2-p2-05-pause-resume-extend`.
- Базовый SHA: `7465a9c3ca0110a93bb5f8e5a4c63aecf80b42b8`.
- Статус: `IN_REVIEW`.
- PR: [#59](https://github.com/D0UP1G/FirsterChuv/pull/59), stacked on #58 → #57 → #50; update awaits push in this audit.

## Цель и исходное состояние

Закончить независимый оставшийся эффект P2-05 — надёжную замену участника до начала матча и во время активного матча. Проверены AGENTS.md, карточка Agent 2, ROADMAP P2-05, M08 в матрице требований, pure `plan_replacement`, текущая ветка и открытый PR #59. До изменений replacement уже имела pure guards, но durable admin service её не принимал; `MatchRun` не хранил отдельный неизменяемый состав.

## Выполненные изменения

- `backend/apps/competition/admin_runtime.py`: добавлены fingerprint старого/нового пользователя, проверка активного participant account и durable `replace_participant`. До старта обновляются участник слота и snapshot READY run, снимается readiness выбывшего игрока. В WAITING без run сохраняется receipt с nullable FK на run. Для RUNNING/PAUSED старый run становится SUPERSEDED; создаётся чистый READY run с теми же закреплёнными настройками, новым составом и пустым счётом. Проверяется, что кандидат не занял другой слот той же сетки. Все эффекты и receipt входят в ту же транзакцию.
- `backend/apps/competition/models.py`, `runtime.py`, `ledger_persistence.py`, migration `0006_matchrun_participant_user_ids.py`: каждый run фиксирует user IDs при настройке, rematch копирует их, ledger использует frozen roster вместо изменяемых bracket slots. Это не позволяет замене задним числом изменить принадлежность исторических попыток.
- `backend/apps/competition/tests/test_admin_runtime.py`: тесты замены READY с exact retry, замены RUNNING с сохранением старого run snapshot и чистым новым run, и замены WAITING без настроенного run.
- `context/agents/agent-2.md`: добавлен текущий P2-05 checkpoint.
- PR #59 дополнен этим срезом и результатами проверок после публикации.

## Сверка с кейсом

M08: реализованы durable эффекты replacement для persisted service. Реализация интеграционная частичная: HTTP endpoint/trusted request adapter и полный сценарий FINALIZING/downstream/events остаются отдельными подключениями. Ветка не содержит production API wiring.

## Проверки

| Команда или сценарий | Результат | Ограничения |
|---|---|---|
| `DJANGO_DEBUG=1 .venv/bin/python manage.py test backend.apps.competition.tests.test_admin_runtime --verbosity 2` | 10 passed; system check clean | Локальный Django test DB |
| `DJANGO_DEBUG=true .venv/bin/python manage.py test backend.apps --verbosity 1` | 256 passed, 2 skipped | Не заменяет браузерную/end-to-end приёмку |
| `DJANGO_DEBUG=true .venv/bin/python manage.py check` | 0 issues | Локальная конфигурация |
| `DJANGO_DEBUG=true .venv/bin/python manage.py makemigrations --check --dry-run` | No changes detected | Проверка только зарегистрированных моделей |
| `.venv/bin/python scripts/check_domain_suites.py` | Все четыре standalone domain suites прошли | Pure-domain наборы |
| `.venv/bin/python -m compileall -q backend` | Код выхода 0 | Только syntax/bytecode compilation |
| `git diff --check` | Код выхода 0 | Проверяет whitespace |

## Решения и отклонения

Добавлен migration-owned `MatchRun.participant_user_ids`: без frozen roster result ledger читал текущие изменяемые slots и мог бы переотнести старые результаты после замены. В состав команды не добавлен endpoint: trusted PublicAccess adapter и API boundary не входят в этот persistence-only slice.

## Блокеры и риски

PR #59 основан на открытых #58, #57 и #50; требуется сохранить порядок интеграции. Полное M08/T11 acceptance остаётся открытым до trusted admin HTTP adapter и координации event/downstream/finalization effects. Candidate admission и replacement race beyond tested serialized transaction нуждаются в integration concurrency acceptance.

## Передача следующему агенту

После публикации этой ревизии взять следующую READY/независимую часть Agent 2, сверив свежие roadmap и PR. P2-06 public HTTP/SSE не открывать без PublicAccessV1 adapter; для P2-04 continuation сначала проверить свежую ветку/PR и не менять чужой head. Текущий результат доступен в feature PR #59 и не в `develop`.
