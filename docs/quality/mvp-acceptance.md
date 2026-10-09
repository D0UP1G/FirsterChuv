# Приёмка MVP

Статус всех полных сценариев: **NOT_RUN**. Платформа/auth/roster/invites/CI integrated; новый integration feature содержит проверенные sandbox/pure clock/score/catalog. Совместно 105 Django tests, 36 domain/12 sandbox unit, 5 actual Docker smoke pass; это core checks, не полные T01–21. F01/F07 закрыты на 6950f10, #7/#15/#16 имеют новые/остающиеся blockers. Команды/границы — [повторная ревизия](../reviews/2026-10-09-integration-review.md). ROADMAP v3 сохраняет T01–21 и требует production/browser/official/recovery приёмку.

Готовность по кейсу требует блоки 1–3; команда также включает базовую визуализацию. Первый working slice — промежуточный результат, не повод пропускать обязательные строки.

| ID | Проверяемый сценарий / ожидаемый результат | Владелец | Требования |
|---|---|---|---|
| T01 | Чистый clone + env/package → одна документированная команда, миграции/seed/images/readiness, web/API/worker, повторный restart без data loss | A1 | D01, D03 |
| T02 | Register → participant; role=admin не повышает; anonymous/participant admin writes запрещены; inactive account запрещён | A1/A5 | TEAM01, S02 |
| T03 | Tournament CRUD: все поля, даты/cap/format/visibility validations; participant не может create/edit | A1/A5 | M01 |
| T04 | Expiring/limited/revoked invite; register+accept добавляет; repeat не тратит use; concurrent accept не превышает use/cap | A1/A5 | M02 |
| T05 | Assign/remove/list/seed, duplicate/cap, inactive/admin не назначаются игроками; history played entrants сохранена | A1/A2/A5 | M03 |
| T06 | Сетки 2/3/4/5 участников, byes и WAITING разнятся; manual pairs, no duplicate player, повторная генерация не создаёт копии | A2/A5 | M04 |
| T07 | Один immutable набор задач/правил обоим; server clock, reload не продлевает, hidden conditions до start | A2/A5 | M05, P03 |
| T08 | Manual start и auto both_ready; один ready не начинает, retry start не создаёт два run | A2/A5 | M06 |
| T09 | Received before deadline → delayed OK считается; after deadline/paused запрещено; timeout FINALIZING ждёт accepted queue | A2/A3/A5 | M05, J04 |
| T10 | Unique solved/penalty/last accepted/tie → rematch; duplicate result не добавляет балл, winner атомарно переходит; полуфинал → финал | A2 | M05, M07 |
| T11 | Pause/resume, extend, technical win, rematch, replacement; reasons/actor logged; old result не меняет new run, downstream started запрещает пересмотр | A2/A5 | M08 |
| T12 | Official package import не ручной copy; TeX/image/table/examples/limits; multiple-valid-output checker, invalid package отклонён | A3/A5 | P01, P02 |
| T13 | Editor highlight/indent/brackets/hotkey, task switch/statuses, templates и не менее реально заявленного language list; language работает в sandbox | A3/A5 | E01, E02, P03 |
| T14 | Реально получить OK/WA/TL/ML/RE/CE; CE author diagnostics, история и async update без reload; invalid checker infrastructure не WA | A3/A5 | J01, J02, E03 |
| T15 | Draft survives reload/task/language/reconnect; local+server revision, user namespace, конфликт не теряет обе версии | A3/A5 | E04 |
| T16 | Anonymous live bracket/map: leader, arbitrary solved tasks, attempts/verdict/time, projector readable; no login wall | A4/A2/A5 | V01, V02, V04, TEAM02 |
| T17 | SSE solve/overtake/win events; Last-Event-ID, snapshot resync, disconnect и duplicate frames не повторяют score/animations | A4/A2/A5 | V03 |
| T18 | Hostile runtime/compile: loop/memory/pids/net/host-read/secrets/output; limits/cleanup работают, следующий normal job successful | A3/A1 | J03, D06 |
| T19 | Worker kill/restart, lease recovery, same idempotency key, temporary Docker/SQLite error, bounded queue/retry и сохранность accepted source | A3/A2 | J04 |
| T20 | SQL/XSS/CSRF/command/SSRF/archive attacks, UUID/role bypass, secrets/source отсутствуют в public DTO/SSE/browser/logs/sandbox | Все | S01, S02, TEAM06 |
| T21 | Полный browser scenario раздельных sessions и anonymous spectator, реальные official tests, продвижение, video ≤5 min, repo/README/env/история/variant Б | Все; A1 координатор | D02–06 |

## Как проверять

Pull request CI (P1-02) разделён на независимые jobs: `contracts-and-common-imports` валидирует synthetic schemas и импорт общих портов без optional apps; `backend` запускает compileall, Django check, migration drift и backend suite; `domain` выполняет standalone bracket/clock/scoring suites по мере появления файлов; `sandbox-unit` запускает только sandbox unittest без Docker. `Real sandbox smoke` описан отдельным manual workflow с явным подтверждением и выполняет build + реальные Docker cases. GitHub разрешает dispatch только когда файл находится в default branch; сейчас это `main`, куда feature ещё не интегрирован, поэтому этот manual workflow пока не запускается на GitHub. Зелёный CI не является pass T18/T20/T21 и не заменяет hostile execution на интегрированной системе.

P1-01 покрывает backend-подпроверки T04: create/list/revoke, срок/лимит, hashed token, registration+login+accept, repeat, concurrency и отказ при full/frozen roster. Полный T04 остаётся открытым до подключения invite UI и browser-сценария на интегрированном SHA; одних backend-тестов недостаточно для PASS.

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

## Передача владельцев и новая ревизия 2026-10-10

Исторический первый абзац — снимок прошлой ревизии. Текущие combined checks: backend255/4skips, file-backed draft18/bracket24, frontend82/typecheck/build, domain68/sandbox15/schema9; это не полные T01–21. A5 отвечает за browser/UI в строках выше; A4 events/public HTTP/SSE и scripts/acceptance/evidence вместе с domain владельцами. T16/T17 — producer A4 + competition A2 + consumer A5. #53 snapshot blocker не закрыт. [Актуальный report](../reviews/2026-10-10-mvp-readiness.md), [план](../../ROADMAP.md). Evidence для полного сценария обязательно на actual integration SHA с раздельными sessions/real providers/official bundle.
