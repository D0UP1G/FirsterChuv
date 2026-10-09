# Аудит: агент 2 / P2-06.1 SOLVED и последняя попытка

- Автор/роль: Codex, агент 2 — сетка и live backend.
- Рабочая сессия: 2026-10-09, Europe/Moscow.
- Задача: corrective slice P2-06.1 по Agent 2 card и ROADMAP v3.
- Ветка: `feature/public-events-sse`, существующий [PR #16](https://github.com/D0UP1G/FirsterChuv/pull/16), base `develop`.
- База: свежий `origin/develop` `ed14416fee0d1cccbd0b9a202e563d49f062572a`, интегрирован merge commit `a26df6d`.
- Статус: correction опубликована в существующий PR #16; CI успешен, merge не выполнялся.
- Implementation commit: `2f6cac1be920fdb563d354479ea56f2a21386589`.

## Цель и требования

Scoring core считает задачу `SOLVED` после первого `OK`, но продолжает принимать попытки и отражает наиболее поздний verdict в `last_verdict`. Event validator ошибочно требовал `lastVerdict == OK`, поэтому не пропускал корректное score-состояние после `OK → WA/CE`.

Сверены `ROADMAP.md` P2-06.1, `docs/requirements.md` V01–03/S02/T16/T17/T20, `docs/architecture/realtime.md`, `docs/architecture/parallel-contracts.md`, `contracts/mvp-v1/score-event.json`, `contracts/mvp-v1/public-match.json`, `contracts/mvp-v1/schemas.json`, кейс PDF и предыдущий audit event store. Схема `taskState` задаёт status/verdict allowlists и nullable verdict shape, но не требует `OK` для `SOLVED`; менять fixture/schema не требуется.

## Изменения

- `backend/apps/events/public_payloads.py`: `SOLVED` по-прежнему требует `attempts > 0` и ненулевой нормализованный verdict. Вердикт валидируется тем же закрытым allowlist `OK/WA/TL/ML/RE/CE`; дополнительные ключи и privacy validation не менялись.
- `backend/apps/events/tests.py`: добавлен DB roundtrip из реального `calculate_match_score` в `append_event` и обратно через `read_events_after`. В одном payload первая задача имеет `WA → OK → WA`, вторая `OK → CE`; обе остаются `SOLVED`, `solvedCount`, winner, penalty и время последнего первого OK сохраняются.
- Добавлены негативные проверки на неизвестный verdict и `SOLVED` с отсутствующим verdict.
- При merge свежего develop разрешены только конфликты Agent 2-owned карточки и `INSTALLED_APPS`: сохранены обе регистрации `EventsConfig` и `ProblemsConfig`; чужие файлы из develop не редактировались.
- Не менялись `contracts/mvp-v1/schemas.json`, fixtures, score core, producers, HTTP/SSE, snapshots и access adapter.

## Проверки

- `uv run --locked --env-file .env.example python manage.py test backend.apps.events -v 2` — 11 passed.
- `uv run --locked --env-file .env.example python manage.py test backend.apps -v 1` — 117 passed; Django system check без ошибок.
- `uv run --locked python scripts/check_domain_suites.py` — 36 passed (clock, scoring, admin guards).
- `uv run --locked python scripts/check_contracts.py` — 9 v1 fixtures validated; public schemas reject private source fields.
- `uv run --locked --env-file .env.example python manage.py makemigrations --check --dry-run` — no changes detected.
- `git diff --check` — clean.

## Границы и следующий шаг

Этот slice чинит сериализацию authoritative score event, но сам по себе не подтверждает V01–03/S02/T16/T17/T20 полностью. Producers, `PublicAccessV1`, coherent snapshots, anonymous HTTP/SSE transport, replay/resync/backpressure и browser acceptance остаются отдельными задачами P2-06.

Следующий шаг: зафиксировать correction вместе с этим audit, запушить существующую ветку через настроенный GitHub CLI credentials, обновить описание PR #16 и проверить GitHub status checks. Не создавать второй PR и не вливать PR без отдельного решения.

## Публикация

PR #16 обновлён через GitHub CLI и указывает новую семантику, tests и audit. На implementation head `2f6cac1` все четыре GitHub checks прошли. После последующего docs-only commit `6eac91f` первый backend run упал в чужом `InviteAcceptanceConcurrencyTests.test_simultaneous_accept_never_exceeds_roster_capacity`: параллельная регистрация получила два `database_busy` и только один `accepted`. Это `backend/apps/tournaments/tests.py` (P1 invite work), не менялось агентом 2. Выполнен `gh run rerun 37983950477 --failed`; повторный `backend` прошёл за 43s, вместе с `contracts-and-common-imports`, `domain` и `sandbox-unit`. Текущее состояние PR #16: OPEN, merge state `CLEAN`, все четыре checks pass на head `6eac91f`. PR оставлен открытым для review. Следующий шаг Agent 2 — ждать/обрабатывать review по #16, затем идти к P2-03 persisted MatchRun по порядку.
