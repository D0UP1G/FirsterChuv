# P2-04 — публикация ledger core

- Автор/роль: agent 2.
- Момент публикации: `2026-10-09T23:32:57+03:00` (Europe/Moscow).
- ID задач: P2-04 accepted ledger/result pure domain slice; M05/M07/J04, T09/T10/T19 partial.
- Ветка: `feature/match-ledger-results`.
- Базовый SHA: `56c20eb3323c892d7f2fa9aadc6beb905548f677`.
- PR: [#38](https://github.com/D0UP1G/FirsterChuv/pull/38), base `develop`, head `669890cf556a2690264684789d7300c05adabc28`.
- Статус: `IN_REVIEW`, открыт, не слит.

## Checks при создании PR

GitHub actions run `37987697173` запустил четыре CI jobs; на момент чтения все ещё `QUEUED`:

- `contracts-and-common-imports` — QUEUED.
- `backend` — QUEUED.
- `domain` — QUEUED.
- `sandbox-unit` — QUEUED.

Локально после синхронизации с базой `56c20eb` `scripts/check_domain_suites.py` завершился успешно: 45 passed. Полное описание проверок — в [основном P2-04 аудите](2026-10-09T232844+0300-agent-2-P2-04-ledger-core.md).

## GitHub контекст и передача

- P2-03 readiness PR #34 на head `730edd827236a42d98b3efe85551f6277a1d5d97` — OPEN/CLEAN, все четыре checks SUCCESS; merge не выполнялся.
- P2-03 persistence зависит от PR #7 (`1a2b54a`, OPEN/DIRTY); failure sink ждёт общего P1-02.5 порта A1.
- P2-04 здесь покрывает только pure ledger core. После review перейти к persistence/failure/outbox CONNECT, когда появятся зависимости.
- Пока P2-04 CONNECT ожидает MatchRun/failure port, следующий независимый пункт Agent 2 — P2-05 command/effects core в отдельной feature-ветке.
