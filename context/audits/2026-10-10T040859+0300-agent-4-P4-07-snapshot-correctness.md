# Agent 4 · P4-07 snapshot correctness · implementation audit

Время: 2026-10-10 04:08:59 Europe/Moscow
Ветка: `feature/a4-p4-07-snapshot-correctness`
База: `origin/develop` / merge PR #77 `5f8e7d5a76e296e3cdc3bafe88782540c4168179`
Статус: реализация готова в feature; публикация, exact-head CI и интеграция ожидаются.

## Сверка задачи и кейса

- ROADMAP v5 P4-07 требует исправить concurrent first-create/update и равный cursor, проверить file-backed SQLite connections, сохранить event+snapshot outer rollback и добавить anonymous public match snapshot. SSE вынесен отдельно.
- `docs/requirements.md`: V01/V02 и T16; V03/T17 — realtime transport; T20 — публичная конфиденциальность.
- Кейс, страницы 6–7: зритель видит карту с прогрессом, попытками/вердиктами, лидером и временем без регистрации; зритель не получает код участника и не отправляет решения.
- M0 G06 на этой ветке получил первый public-only snapshot endpoint. Это ещё не browser CONNECT, не SSE и не полная приёмка кейса.

## Изменения

- Обычным merge `fbf0348355d1e4f225c0977406ee8e462916ef90` перенесён source PR #53 (`fd79038847a23b38bb8a444c028b87ce75ed9571`) только в эту feature. Исходная ветка не менялась. `settings.py` разрешён сохранением полного текущего списка приложений; карточка Agent 2 сохраняет текущую историю и получила короткую ссылку на перенесённый P2-06.2 audit.
- Snapshot service сначала выполняет no-op `UPDATE`, получая SQLite writer reservation до чтения; сохраняет новую строку или больший cursor, игнорирует меньший cursor. Равный cursor считается idempotent только при том же `run_id` и идентичном payload; конфликт выдаёт `PublicSnapshotConflict`.
- Для самостоятельной записи есть до трёх полных transaction попыток при SQLite BUSY/LOCKED. При вызове из внешнего transaction сервис передаёт `PublicSnapshotBusy` наружу; ledger повторяет всю result transaction и после исчерпания попыток возвращает `LedgerPersistenceBusy` со статусом 503.
- Result adapter сохраняет `score.changed` и соответствующий `MatchSnapshot` в той же транзакции. Outer rollback удаляет обе записи вместе.
- Добавлен `DjangoPublicAccess` для публичных турниров; unlisted закрыт до P1-03 hashed share-token реализации. Anonymous `GET /api/v1/public/matches/{id}` строится из приватной проекции через явный top-level/nested allowlist, использует сохранённый score snapshot только при точном совпадении run/cursor и отвечает `no-store`/`no-referrer`. Private code, email, checksums, compiler diagnostics и infrastructure details в DTO не попадают.
- Минимально подключён URL include events app. Обновлены API/realtime/runtime handoff/M0/requirements/ROADMAP и карточка A4. Frontend A5 и runtime/apps A3 не менялись.

## Проверки

- `DJANGO_SETTINGS_MODULE=backend.apps.events.test_settings DJANGO_DEBUG=1 DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py test backend.apps.events.test_snapshot_concurrency` — 5 PASS на file-backed SQLite. Тесты подтверждают разные connections, параллельный first create/update, игнорирование stale cursor, same-cursor conflict и exhausted busy retry.
- `DJANGO_DEBUG=1 DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py test backend.apps.events.test_public_match_api backend.apps.competition.tests.test_ledger_persistence --verbosity 2` — 16 PASS. Включены anonymous API, unlisted deny, not-ready response, JSON Schema v1, score event/snapshot consistency, внешняя атомарность и full-ledger retry при snapshot BUSY.
- Повторная общая проверка `DJANGO_DEBUG=1 DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py test backend.apps.events backend.apps.competition.tests.test_ledger_persistence` — 36 PASS, 5 concurrency cases пропущены, так как стандартный test runner создаёт in-memory SQLite. Все эти 5 сценариев отдельно прошли под file-backed `test_settings` выше.
- `uv run --locked python scripts/check_contracts.py` — 9 v1 fixtures PASS; `check_contract_imports.py` — PASS; `check_domain_suites.py` — PASS.
- `DJANGO_DEBUG=1 DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py check` — PASS; `makemigrations --check --dry-run` — изменений нет; `compileall` и `git diff --check` — PASS.
- Полный `DJANGO_DEBUG=1 DJANGO_REQUIRE_SECRET_KEY=0 uv run --locked python manage.py test` нашёл 336 тестов: 19 skipped, один error в A3 `backend.apps.submissions.tests.test_admission_concurrency.SubmissionAdmissionConcurrencyTests.test_concurrent_capacity_limit_rejects_excess_without_partial_reservation` (`database table is locked: submissions_queuecounter`). Изолированный повтор этой же проверки — 1 PASS. A3-owned код не изменялся; эта известная intermittent admission race остаётся открытой.

## Ограничения и следующий шаг

- Результат пока только в feature. Следующий шаг этой задачи: проверить diff, commit текущие изменения вместе с этим audit, создать PR в `develop` и записать CI-статус. По прямому уточнению пользователя после публикации PR остановить работу; новые A4 задачи не начинать.
- `frontend/src/spectator/transport.ts` пока fail-closed (`public_access_unavailable`); A5 должен подключить новый snapshot route и bracket. В feature проверен только backend HTTP.
- Unlisted share token с hash/expiry/revoke — READY P1-03. Public bracket endpoint, SSE heartbeat/Last-Event-ID/resync/backpressure и `submission.accepted`/прочие lifecycle typed producers ещё не реализованы.
- M0, V03/T17 и полные T01–21 не закрыты.
- P1-03 остаётся READY в ROADMAP, но не начата по прямому уточнению пользователя закончить работу после публикации PR.
