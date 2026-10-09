# Приёмка MVP

Статус всех полных сценариев: **NOT_RUN**. Backend/auth/roster срезы Agent 1 уже integrated PR #2/#5/#8; 37 tests повторены ревизией на develop 146b2cb. Алгоритм PR #7 и sandbox PR #3 ещё не integrated. Harness имеет F01/F07; 4 diagnostic smoke cases после временного исправления не являются PASS исходного PR, official package или T18. Полные T02/T03/T05/T20 требуют domain/browser/history/security проверки. Команды, среда и SHA — в [ревизии](../reviews/2026-10-09-repository-audit.md). Новый план задач P1–P4 — ROADMAP v2; acceptance ID T01–21 сохранены.

Готовность по кейсу требует блоки 1–3; команда также включает базовую визуализацию. Первый working slice — промежуточный результат, не повод пропускать обязательные строки.

| ID | Проверяемый сценарий / ожидаемый результат | Владелец | Требования |
|---|---|---|---|
| T01 | Чистый clone + env/package → одна документированная команда, миграции/seed/images/readiness, web/API/worker, повторный restart без data loss | A1 | D01, D03 |
| T02 | Register → participant; role=admin не повышает; anonymous/participant admin writes запрещены; inactive account запрещён | A1/A4 | TEAM01, S02 |
| T03 | Tournament CRUD: все поля, даты/cap/format/visibility validations; participant не может create/edit | A1/A4 | M01 |
| T04 | Expiring/limited/revoked invite; register+accept добавляет; repeat не тратит use; concurrent accept не превышает use/cap | A1/A4 | M02 |
| T05 | Assign/remove/list/seed, duplicate/cap, inactive/admin не назначаются игроками; history played entrants сохранена | A1/A2/A4 | M03 |
| T06 | Сетки 2/3/4/5 участников, byes и WAITING разнятся; manual pairs, no duplicate player, повторная генерация не создаёт копии | A2/A4 | M04 |
| T07 | Один immutable набор задач/правил обоим; server clock, reload не продлевает, hidden conditions до start | A2/A4 | M05, P03 |
| T08 | Manual start и auto both_ready; один ready не начинает, retry start не создаёт два run | A2/A4 | M06 |
| T09 | Received before deadline → delayed OK считается; after deadline/paused запрещено; timeout FINALIZING ждёт accepted queue | A2/A3/A4 | M05, J04 |
| T10 | Unique solved/penalty/last accepted/tie → rematch; duplicate result не добавляет балл, winner атомарно переходит; полуфинал → финал | A2 | M05, M07 |
| T11 | Pause/resume, extend, technical win, rematch, replacement; reasons/actor logged; old result не меняет new run, downstream started запрещает пересмотр | A2/A4 | M08 |
| T12 | Official package import не ручной copy; TeX/image/table/examples/limits; multiple-valid-output checker, invalid package отклонён | A3/A4 | P01, P02 |
| T13 | Editor highlight/indent/brackets/hotkey, task switch/statuses, templates и не менее реально заявленного language list; language работает в sandbox | A3/A4 | E01, E02, P03 |
| T14 | Реально получить OK/WA/TL/ML/RE/CE; CE author diagnostics, история и async update без reload; invalid checker infrastructure не WA | A3/A4 | J01, J02, E03 |
| T15 | Draft survives reload/task/language/reconnect; local+server revision, user namespace, конфликт не теряет обе версии | A3/A4 | E04 |
| T16 | Anonymous live bracket/map: leader, arbitrary solved tasks, attempts/verdict/time, projector readable; no login wall | A2/A4 | V01, V02, V04, TEAM02 |
| T17 | SSE solve/overtake/win events; Last-Event-ID, snapshot resync, disconnect и duplicate frames не повторяют score/animations | A2/A4 | V03 |
| T18 | Hostile runtime/compile: loop/memory/pids/net/host-read/secrets/output; limits/cleanup работают, следующий normal job successful | A3/A1 | J03, D06 |
| T19 | Worker kill/restart, lease recovery, same idempotency key, temporary Docker/SQLite error, bounded queue/retry и сохранность accepted source | A3/A2 | J04 |
| T20 | SQL/XSS/CSRF/command/SSRF/archive attacks, UUID/role bypass, secrets/source отсутствуют в public DTO/SSE/browser/logs/sandbox | Все | S01, S02, TEAM06 |
| T21 | Полный browser scenario раздельных sessions и anonymous spectator, реальные official tests, продвижение, video ≤5 min, repo/README/env/история/variant Б | Все; A1 координатор | D02–06 |

## Как проверять

Unit/domain checks для score/tie/bracket/clock/guards. API integration checks для role/object permissions, invite cap/idempotency/drafts/transactional events. Real executor integration для compile/run/checker/limits. Browser checks для conditions/editor/autosave/SSE/projector. Изолированные mocks допустимы в unit tests, но не являются доказательством J01/J03/T14/T18.

Без official package T12/T14/T21 не считать полностью пройденными. Smoke-задача подтверждает только работоспособность механизма. Пропуск real Docker check из-за отсутствия engine фиксировать как NOT_RUN, не как successful suite.

## Подробности security checks

- SQL: специальные символы и SQL-подобная строка в search/email/filter не меняют query/доступ; сортировка принимает только allowlist.
- XSS: raw HTML/event handlers/опасные URL в Markdown/name/reason/compile stderr не исполняются в browser, сохраняется корректное отображение обычных formulas/images.
- CSRF: изменение без token и cross-origin browser request отклоняется; register/login проверяются отдельно.
- Command: client language/image/argv/path не влияют на host command; metacharacters в filename/source не выполняют отдельную команду.
- SSRF: import не принимает arbitrary URL; localhost/private IPv4/IPv6/metadata/redirect/rebinding paths отклоняются.
- Archive: `..`, absolute paths, symlink/hardlink, oversized files/bomb не пишут вне import root и не запускают manifest commands.
- IDOR: participant A не получает B source/draft/history и не submit в B match; admin не получает private source по умолчанию; public endpoint никогда не возвращает secrets.
- Sandbox: safe canary вне sandbox не читается; network failure и resource bounds подтверждены. Не включать реальные secrets в evidence.

Сценарии враждебного кода выполняются только с isolation и bounded caps. Тест не должен вредить остальным контейнерам/пользователям host. Worker cleanup ограничивается labels проекта.

## Release gate

T01–21 выполнены на integration/release SHA, ошибки исправлены, audit evidence сохранён. README описывает фактическую одну команду и вариант Б, `.env.example` без secrets, demo/video доступно зрителю, state соответствует remote refs. Не считать готовностью один unit test, UI fixture, документ или зелёный pipeline без реального sandbox. При изменениях после проверки повторить затронутые сценарии, а не весь набор без причины.
