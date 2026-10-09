# Итог implementation/review: MVP и передача frontend

- Время: 2026-10-10T01:15:16+03:00, Europe/Moscow.
- Ветка: feature/mvp-readiness-handoff; база cc204e62a060eb2ceb16067a1b0693a2e083d9ab.
- Прямой запрос команды: новые исправленные PR, состояние/roadmap/кейс, новый frontend agent и перераспределение остальных.
- Результат review: #21/#50/#51/#52/#54/#55 ordinary merged в этой feature; #53 исключён с двумя воспроизведёнными blockers, first READY A4 fix. Remote merge ещё не заявляется завершённым.
- Собственные corrections: inert static auth fields/buttons #54, CI maxWorkers1. Единственный docs conflict A2 card разрешён сохранением обеих секций, original audit blobs неизменны.
- Полная ревизия, exact heads, checks и case boundaries: [report](../../docs/reviews/2026-10-10-mvp-readiness.md).
- Combined tests: backend255/4skips PASS first attempt, draft file18 PASS, bracket file24 PASS, domain68/sandbox15/schema9/imports/check/drift PASS, frontend82/typecheck/build PASS; lint5 прежних warnings/chunk warning не скрыты.
- #53 root probe: equal cursor допускает old run overwrite, concurrent first-save cursor9 lost с database is locked; outer rollback PASS. Runtime source53 не включён, API/SSE ещё не реализован.
- Owner handoff: A5 frontend/design; A4 events/SSE/system acceptance; A1 common/access/build; A2 competition/run/ledger; A3 judge/worker/workspace. New Codex thread01a122b2-27f9-7af0-ab77-dd282807d489 active, без override модели.
- Приняты additive boundaries/draft GET selector и per-claim fencing; готовность provider этим не объявлена. ROADMAP v4 сохраняет историческиеP-ID,37 требований,21 acceptance и добавляетP4-07–09/P5-01–03.
- Official package/README отсутствует, full R1/T01–21/hostile/demo/production deployment NOT_RUN. Main bootstrap, source checkouts/refs не изменены.
- Следующий шаг: verify source ancestry/audit/link/path integrity, publish own integration PR→develop,5 final CI jobs exact head, live refs gate, ordinary merge, remote verification; independent owners продолжают READY tasks после code merge.

## Независимый review #21 (evidence этой сессии)

# Review-only PR #21: исправление конкурентного сохранения черновиков

Дата: 2026-10-10, Europe/Moscow. Проверенный head: `620f58e67ba0ad310ba0c65b41aface1bc3eaea2`, feature/private-drafts-history. Fresh develop base: `cc204e62a060eb2ceb16067a1b0693a2e083d9ab`; этот SHA является merge-base и предком проверенного head.

Решение: **APPROVE AS PRIVATE DRAFT/CAS CORE SLICE**. Прежний P3-05.1 blocker uncaught SQLite CAS busy → HTTP 500 снят. Новых блокирующих замечаний в полном diff не обнаружено. Слияние не выполнялось; source/common checkout/ветки/remote/PR не изменялись. Тесты запускались только в git-archive export `/tmp/firster-review4-drafts` с disposable SQLite. Код решений не исполнялся.

## Сверка со старым blocker

Исторический exact head `1706ecfb8d16a693a462b3f3b7f379caeedc0060` имел один `transaction.atomic` и обработку IntegrityError, но не SQLite OperationalError. В coordinator audit `2026-10-09T224851+0300-coordinator-agent-3-unblock.md` два одновременных первых save в одном namespace дали успешную запись и необработанный `database is locked`/HTTP 500. Это сравнение исторического кода и сохранённого evidence; старый head повторно не запускался в данной ревизии.

Полностью прочитаны новые drafts files/diff, HEAD fix diff, разрешённые shared app/include additions, card/audit additions, новые sync/fix audits и относящиеся к задаче contracts/requirements/runtime handoffs. Работа не смешивает исторический core с полной runtime acceptance.

## Что проверено в исправлении

- `backend/apps/drafts/services.py:96`: только SQLite vendor; primary и extended SQLITE_BUSY/SQLITE_LOCKED распознаются по `code & 0xFF`. Если есть иной SQLite error code, message fallback не переклассифицирует его. Fallback ограничен стандартными lock messages. Disk I/O и произвольный OperationalError не маскируются как contention.
- `services.py:156`: максимум три попытки, два коротких delay 25/75 ms. `now` фиксируется до loop. Вся CAS transaction вынесена в `_save_once` (`:190`, atomic `:200`); OperationalError выходит из неё и rollback завершается до sleep/повтора. Новый transaction заново читает draft/revision, старый read snapshot не продолжается. Current HTTP settings не используют ATOMIC_REQUESTS.
- `services.py:207`: первый save требует expected_revision=0, создаёт ровно revision 1 и history в той же transaction. После победы другой транзакции retry попадает на `:227` и возвращает конфликт с actual winning server draft. Update условен по прежней revision (`:234`); история создаётся только после успешного CAS и откатывается вместе с source при сбое.
- `services.py:183`: exhausted budget → DraftStorageBusy. `views.py:32` и `:149` дают HTTP 503 `draft_busy` без DB exception text. Unrelated errors сохраняют исходный тип. Stale revision → HTTP 409 `revision_conflict`, `views.py:135`, с private currentDraft; winning source/revision/history не затираются.
- `tests/test_concurrency.py:20`: настоящее TransactionTestCase с file-backed SQLite, отдельные connections. Первый create barrier (`:100`) и update barrier (`:113`) стоят после обоих SELECT и перед обеими записями. Они проверяют один success/один conflict, exactly one draft, revision/history count, winning source, conflict snapshot и отсутствие source проигравшей вкладки в server history. В выполненном file-backed suite эти tests не skipped.
- Модели и initial migration ограничивают user/run/problem/language namespace и unique draft/revision. Source лимит 32 KiB UTF-8, source не интерполируется в SQL/команды, draft никак не запускает judge и не меняет score. Same source/current revision не создаёт дополнительной revision.

## Приватность, permission и контракт

- `views.py:49`: активный session participant; admin/inactive/чужой actor отвергаются. PUT CSRF guarded, unknown fields rejected; no-store/no-referrer сохраняются, включая конфликт/503. Permission tests PASS.
- `views.py:67`: реальный WorkspaceAccess вызывается до storage; context actor/run/problem сверяются с requested scope, required action проверяется. Storage `services.py:45` отдельно требует read_draft/write_draft/read_history, не использует browser UUID как доказательство доступа. Все queries имеют actor namespace.
- `factory.py:9`: WORKSPACE_ACCESS_FACTORY отсутствует/сломана/возвращает не-порт → WorkspaceUnavailable. FakeWorkspaceAccess существует только в tests. Текущая production конфигурация не задаёт factory; API fail-closed 503 `workspace_unavailable`.
- `ports.py` использует общий immutable WorkspaceContext/WorkspaceAction/WorkspacePurpose без локального несовместимого DTO. HTTP casing/UUID/time и draft snapshot совпадают с `contracts/mvp-v1/draft.json`; PUT body остаётся `{runId, source, expectedRevision}`, languageId query. Public schemas/DTO/events не расширены private source.
- GET runId query и missing-draft 404 всё ещё описаны в `context/contracts/agent-3-private-draft-get.md` как PROPOSED. Это ясное уточнение ещё не принятого HTTP selector, не скрытое изменение обязательных DTO. Требуется зафиксировать его с A2/A4 перед production/browser CONNECT; это не блокирует самостоятельный storage/CAS slice. Не считать full API/browser contract acceptance закрытой.
- Registration только DraftsConfig и drafts URL include; все ранее integrated apps/includes, CI, common v1/schema/scripts сохраняются. Новая feature содержит fresh develop ancestry, common contracts/CI/scripts не изменяет. Никаких кодовых конфликтов с данной базой.

## Команды и фактические результаты

Interpreter: `/home/light/Documents/ChatGPT/Блиц/FirsterChuv-coordination-review/.venv/bin/python`; cwd `/tmp/firster-review4-drafts`; `DJANGO_DEBUG=true` для Django команд.

| Команда / сценарий | Результат |
|---|---|
| `DRAFTS_SQLITE_TEST_PATH=/tmp/firster-review4-drafts/.data/review-drafts.sqlite3 python manage.py test backend.apps.drafts.tests --settings=backend.apps.drafts.test_settings --noinput --verbosity 2` | PASS: 18/18, 10.166s, без skips; first-create и update races выполнены |
| `python manage.py test backend.apps --noinput --verbosity 1` | PASS с первого запуска данной ревизии: 248 tests, skipped=4, 108.816s |
| `python manage.py check` | PASS: 0 issues |
| `python manage.py makemigrations --check --dry-run` | PASS: No changes detected |
| `python scripts/check_contracts.py` | PASS: 9 v1 fixtures; public schemas reject private source |
| `python scripts/check_contract_imports.py` | PASS: common v1 imports without optional domain apps |
| `python scripts/check_domain_suites.py` | PASS: все четыре доступные standalone suites, exit 0 |
| `git diff --check cc204e62...620f58e6` | PASS |
| Дополнительный HTTP probe с реальным удержанным BEGIN IMMEDIATE на отдельной file-backed SQLite, timeout=20 ms, valid session/CSRF и test-only WorkspaceAccess | PASS: HTTP 503 draft_busy, DB details leaked=False, Cache-Control=no-store, Draft/history counts=0/0 |

Последний probe использовал `/tmp/firster-review4-drafts/.data/review-held-lock.sqlite3`, штатный migrate и APIClient. В него не подставлялся mock OperationalError: ошибка возникла от реально удержанного SQLite write lock. Service class/error mapping работали как на reviewed HEAD; test-only workspace port разрешал только синтетический actor/match/run/problem. Lock снят в finally, code/source только хранится, не исполняется.

Четыре skips общего backend относятся к opt-in real Docker и file-backed-only suites; две draft concurrency checks выполнены отдельно выше. Docker/hostile code, actual demo deployment, browser autosave/reconnect, GitHub CI нового head и production workspace provider этой ревизией не проверялись. Author audit сообщает transient in-memory queue AdmissionBusy в его первом прогоне; в текущем полном прогоне такой failure не возник. Это не повод приписывать draft fix изменение queue app.

## Остаток до runtime MVP

Проверенный результат закрывает P3-05.1 implementation/CAS regression и часть P3-05 storage/privacy. Для полной T15/T20 остаются production A2 WorkspaceAccess с membership/history policy и правильными actions, согласование GET selector/404, A4 real server autosave/reconnect/task/language переключение и сохранение обеих локальной/серверной версий при 409, обработка retryable 503 и очистка private namespace при logout.

Для ближайшего R1 по runtime-handoffs всё ещё нужны persisted configured run/gateway/ledger/result/failure effects, run-pinned version/checksum, production worker/executor/providers и HTTP/SSE CONNECT. Cores/LocalJudge/worker primitives, уже integrated в develop, не переписывать. R2 добавляет обязательные admin actions/recovery/private drafts/public map; R3 требует official package/README, T01–21, hostile/runtime demo, one-command startup и release. Отсутствующий official package не блокирует проверенные cores и normalized smoke path; только соответствующая official acceptance остаётся внешней зависимостью.
