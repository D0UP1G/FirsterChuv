# Исторический ROADMAP v2 перед повторной интеграционной ревизией

Не является текущим назначением. Активный план — [ROADMAP](../../ROADMAP.md). Сохранён координатором 2026-10-09 без изменения текста исходного плана ниже.

# MVP: параллельный план четырёх агентов

Версия 2, 2026-10-09. База проверки: `develop` на `146b2cb`; DRF + React + SQLite3, собственный judge, вариант Б. [Ревизия PR и аудитов](docs/reviews/2026-10-09-repository-audit.md), [STATE](context/STATE.md), [контракты v1](docs/architecture/parallel-contracts.md), [кейс](docs/source/Кейс_Платформа_соревнований.pdf).

## Уже сделано

PR #1: документация и PDF. PR #2/#5/#8: backend, аккаунты/CSRF/роли, CRUD турнира и roster с freeze. PR #4/#6/#9: состояние. Всё это в develop. PR #7 обновился во время ревизии до a89b8fc: алгоритм + ORM/persistence + service reset/pairings, draft; 58 tests с временной app registration прошли. Clock/score и штатное подключение ещё отсутствуют. PR #3: Docker harness и 8 unit-тестов; реальный запуск выявил ошибку `--pid=private`. Frontend, полноценный judge/worker, официальные задачи и сквозное demo отсутствуют в интегрированной версии. Полные T01–21 не закрыты.

Старые A-задачи остаются историческими ссылками аудитов. [Предыдущий план](docs/history/ROADMAP-2026-10-09-before-review.md) сохранён; активные задания имеют новые P-ID. Не начинать bootstrap заново.

## Правила без простоя

Каждая дорожка реализуется без ожидания **несмерженного кода другого агента**, по контракту v1. Последовательность внутри своей дорожки допустима. Подключение настоящих модулей и финальная приёмка требуют реализаций; это отдельные короткие CONNECT-шаги, которые не останавливают другую разработку.

1. Перед работой fetch, проверить GitHub PR и код. Не объявлять блокер по старой карточке/STATE/комментарию.
2. Один PR — проверяемый срез: алгоритм, persistence, clock, queue, экран. Не держать готовый алгоритм в draft до реализации всего матча.
3. Порты/DTO фиксирует v1. Test doubles допустимы в изолированных tests, UI fixtures — в dev entrypoint. Runtime/demo получает реальные данные; отсутствующий адаптер закрывает действие понятной ошибкой.
4. Если ждёт CONNECT/review, блокируется только подпункт; взять следующую независимую задачу своей дорожки. Не ждать весь A1/A2/A3.
5. Свои apps/миграции/тесты. FK только к уже интегрированной базе User/Tournament/roster; внешние domain references через UUID/version + проверку портом. UUID сам по себе не даёт права и не подтверждает существование объекта.
6. Владелец новой app может в том же PR добавить свой AppConfig и URL include в общие settings/API root по готовому рецепту (ограниченная передача владения). Код app включается этим же PR, поэтому import не опережает его. Остальные shared config/Compose/wiring — маленькие P1-02/P1-04. До регистрации допустимы собственные test settings.
7. Совместимый v1 не требует повторного разрешения соседнего автора. Несовместимое изменение оформить отдельным запросом контракта и продолжать незатронутые части.
8. Audit + своя карточка + PR → develop. STATE обновляет координатор интеграции, которым может быть другой назначенный агент. Ожидание STATE PR не блокирует следующую задачу: фактический merge уже подтверждается Git и аудитом.

## Первые задания — можно начать одновременно

| Агент | Сейчас | Пока ждёт review/CONNECT | Кого ждать для реализации |
|---|---|---|---|
| 1 | P1-01: приглашения на готовом roster | CI, proxy/access, Compose | Никого |
| 2 | P2-01: подключить готовый PR #7 и проверить новый HEAD | Pure clock/scoring/event store | Никого: A1-03 уже merged |
| 3 | P3-01: починить PR #3 и real execution | Storage/import safety, queue, drafts | Никого; пакет нужен только P3-06 |
| 4 | P4-01: React и реальный auth | Все UI экраны по fixtures v1 | Никого |

## Владение

| Агент | Собственные пути | Примеры contracts/mvp-v1 |
|---|---|---|
| 1 | backend/config, common, accounts, tournaments, root tooling, CI, Compose, proxy | roster.json, invite.json; общая регистрация портов |
| 2 | backend/apps/competition, backend/apps/events | bracket.json, match.json, public-match.json, score-event.json |
| 3 | problems, submissions, drafts, judge, sandbox | problem.json, submission.json, draft.json |
| 4 | frontend, UI/browser проверки | Потребляет fixtures; свои dev-сценарии |

Каждый владеет своими миграциями и tests. Агент 1 обслуживает короткие подключения, но не обязан быть автором каждого review/STATE/audit. Существующие PR #3/#7 продолжает владелец. Новые задачи — отдельные feature/* от актуального develop, merge commits, без force push и изменения чужих активных веток.

## Агент 1 — платформа и запуск

### P1-01 · feature/tournament-invites · MERGED (#12)

Продолжить уже занятый агентом 1 checkout, если он есть. Create/list/revoke, public preview и participant accept. Random token хранится как hash, raw token выдаётся при создании. Expiry/maxUses/cap/repeat/concurrent accept атомарны с roster; freeze и active-role gate не обходятся. Register всегда participant.

Готово: API tests expired/revoked/limited/repeat/race; одно вступление расходует один use, retry не расходует. **Независимо:** готовая app tournaments, без сетки/judge/UI. **CONNECT:** invite browser flow P4-02. M02/S02; T04 backend.

### P1-02 · feature/platform-ci-contracts · MERGED (#17)

PR CI: текущая backend suite/check/migration drift, новые domain suites, package imports, fixture schema. Sandbox unit checks отдельно от real Docker smoke. Минимальную app/URL регистрацию делает владелец вместе с модулем в своём PR; P1-02 проверяет эти shared добавления и подключает остальные порты короткими срезами. Материализовать расширения common/contracts коротким срезом; до этого домен может определить локальный typing Protocol по v1. Подготовить branch protection рекомендации; не выдавать их за включённые правила.

Готово: CI выполняет заявленные команды, consumer проверяется отдельно, отсутствующая app не ломает backend. **Не ждать:** всю дорожку соседей. D02/S01/S02; T20 частично.

### P1-03 · feature/platform-security-access · READY

Proxy topology/rate limit: API также доступен на localhost:8000, NUM_PROXIES=1 не должен позволять обход подставленным X-Forwarded-For. Dev HTTP/demo HTTPS, cookies/CSRF. Hashed read-only share token для unlisted в tournaments, отдельно от invite; PublicAccessPort для A2. SQL-подобный search/role/UUID/CSRF проверки.

Готово: anonymous/participant не меняют турниры; заявленный proxy path защищён; unlisted без share token закрыт. **Независимо:** от judge/UI. S01/S02/TEAM06; T02/T20 backend.

### P1-04 · feature/mvp-compose-wiring · READY для инфраструктуры

Одна команда старта, persistent SQLite WAL, migrations/readiness, frontend build, bootstrap admin, clock/worker/storage config. Docker authority только trusted worker, не API/solution. Отсутствующие management commands не объявлять runnable.

**CONNECT отдельно:** apps/URLs → clock → catalog → queue/result sink → frontend, каждый со своим SHA/проверкой. Если адаптер отсутствует — fail closed/readiness error. Готово: restart без data loss, README совпадает с реальными командами. D01/D03; T01/T19. Инфраструктуру писать сейчас, подключения делать по мере готовности одного модуля.

### P1-05 · feature/demo-readiness → release/0.1.0 · финальная приёмка

T01–21 с владельцами, официальный пакет, полуфинал → финал, hostile execution, видео ≤5 минут. Release → main + tag → обратно develop только после обязательной приёмки. Эта задача требует готовой системы; её ожидание не блокирует остальные P1 задачи. D04–06; T21.

## Агент 2 — сетка и live backend

### P2-01 · продолжить feature/bracket-runtime / PR #7 · READY

Последний проверенный HEAD PR #7 a89b8fc уже содержит transient rank adapter, ORM и persistence. Merge актуального origin/develop, сохранить эту работу. В рамках явно разрешённой минимальной передачи добавить свой CompetitionConfig и URL include в общие settings/API root в этой же ветке; не ждать отдельный ответ A1. Обычная suite без временных settings и migration check должны пройти.

Package import уже исправлен в a89b8fc; повторить проверку в штатной конфигурации. Обновить stale PR body по фактическому scope. Принять algorithm/persistence срез отдельно от clock/judge/browser. **Не ждать A1/A3:** регистрация явно разрешена, remaining pairing DTO указан в v1. M03/M04; T06 backend, full scenario открыт.

### P2-02 · feature/bracket-persistence · READY

Match/Slot/Run, atomic freeze/save, repeat/reset и full first-round pairing service уже реализованы в a89b8fc — сохранить, не писать повторно. Осталось: HTTP reset/full pairing по v1, command idempotency/reason audit и lifecycle guards. Ревизия F08 воспроизвела reset ARCHIVED tournament: добавить guard и regression. BYE без played run, WAITING ждёт upstream, history защищена.

Готово: DB/API tests 2/3/4/5, nullable seed, rollback/repeat/reset/pair edit. **Независимо:** не нужны judge, importer, UI. Для настоящего start нужен READY catalog через порт; отсутствие каталога запрещает start. M03/M04; T05/T06 backend.

### P2-03 · feature/match-clock-start · READY

Pure clock/state machine, persisted READY/RUNNING/PAUSED/FINALIZING, immutable tasks/rules, manual/both_ready, run_match_clock/restart. Active elapsed без пауз; deadline equality закрыта. MatchPort проверяет participant/current run/membership/problem/time внутри общей submission transaction.

Готово: deterministic time/state/DB tests с test catalog, без агента 3. Runtime требует настоящий каталог. **CONNECT:** P3-04 admission, P3-06 реальные tasks. M05/M06/P03; T07–09.

### P2-04 · feature/match-scoring-results · READY

Сначала pure score/tie: unique first OK, penalty, last accepted, full tie → rematch. Затем accepted-attempt ledger/ResultSink: duplicate/out-of-order/lease retry/delayed OK/SUPERSEDED/technical finish. FINALIZING ждёт все принятые pending submissions, infra failure не является поражением. Winner/downstream/event атомарны.

Готово: pure и DB tests на typed test receipts, без живого sandbox. **CONNECT:** P3-04 сохраняет accepted ledger и real result. M05/M07/J04; T09/T10/T19.

### P2-05 · feature/match-admin-actions · READY

Pause/resume/extend, technical result, rematch/new run, replacement. Reason/actor/command idempotency, запрет пересмотра при started downstream, старый score не переносится, история не удаляется. Pure guards писать независимо от persistence, затем свои models/services.

Готово: все вмешательства кейса, повтор без дубля, role/UUID/state guards. M08; T11/T20.

### P2-06 · feature/public-events-sse · READY

Durable allowlisted events/public snapshots v1, async SSE/heartbeat/cursor/resync/connection caps. PublicAccessPort для public/unlisted; consistent snapshot/cursor. Начать с event store/projector и собственных domain events, затем подключить producers. Source/email/CE logs не попадают в public DTO.

Готово: dedupe/reconnect/slow client/whitelist tests без frontend. **CONNECT:** producers P2-03/04/P3-04, transport P4-05. V01–03/S02; T16/T17/T20.

## Агент 3 — sandbox, задачи, посылки

### P3-01 · продолжить feature/sandbox-proof / PR #3 · READY, P1-дефект

Убрать неподдерживаемый --pid=private, подтвердить стандартное отдельное PID namespace inspect/runtime; --pid=host запрещён. Real build/smoke и проверка валидности Docker options. На исходном PR #3 запуск NOT_VERIFIED; диагностическая копия без флага прошла 4 smoke cases, это не исправление PR.

Затем bounded loop/output/memory/PID/network/host canary/secrets/cleanup + normal job после отказа. ML только по подтверждённым OOM данным; compiler также изолирован. Готово: исправление владельца committed, real checks/audit/PR обновлены. **Независимо:** от A1/A2 и official package. J01/J03/S01; T18 частично/T20.

Устранить F07 ревизии: solution сейчас может писать в supervisor stdout через /proc/1/fd/1; host PIPE собирается целиком до проверки cap. Защитить управляющий канал и ограничивать host capture во время чтения. Bounded regression, overflow/cleanup и следующий normal job, без опасного flood на host.

### P3-02 · feature/problem-storage-import-core · READY

Problem versions/checksum/READY; public statement/assets/examples/limits отдельно от private tests/checker/validator/reference. Реальный compiler registry. Archive safety: traversal/absolute/symlink/hardlink/bomb/size/content-type caps, no host scripts. Internal normalized ProblemBundleV1 + synthetic fixtures явно помечены.

Готово: storage/catalog DTO/parser safety tests. **Не ждать README:** только внешний mapping вынесен P3-06, официальный формат не угадывать. P01/P02/E02/S01; T12 частично/T13/T20.

### P3-03 · feature/local-judge · READY по normalized bundle

JudgeProvider с trusted Job: compile/test/checker изолированно. На своей imported smoke-задаче real OK/WA/TL/ML/RE/CE, CE только автору, multiple-valid-output checker, infra failure отдельно. Лимиты берутся из задачи: fixed 512 MiB/2s harness не заменяет package limits. Official повтор в P3-06.

Готово: реальный execution/cleanup/broken checker handling, без fake verdict. **Независимо:** от match engine/UI; ядро разрабатывать по bundle до готовности importer mapping. J01/J02/E03; T14/T18 частично.

### P3-04 · feature/submission-queue · READY

Core с injected ports: source до 202, idempotency/hash, claim/lease/retry/backoff/recovery, bounded queue, один worker. Core tests с fake ports только в tests. HTTP: одна SQLite transaction MatchPort → requested run check → submission/source + accepted ledger + event. Без настоящего порта/provider runtime не принимает решение и не выдаёт fake verdict.

Worker сохраняет durable result и передаёт ResultSink receipt; дубликат не удваивает score, задержка не меняет received time. **CONNECT:** P2-03/04 коротким wiring; до merge продолжать core/recovery/P3-05. J04/E03; T09/T14/T19/T20.

### P3-05 · feature/private-drafts-history · READY

Draft user/run/problem/language/revision, приватные source/history. Storage проверяется с authorized test context; реальные views используют AccessContext port. Author-only source/CE даже для admin, UUID IDOR/active-user/CSRF/no-store. Draft не ждёт live judge и не влияет на score.

Готово: revision conflict сохраняет обе версии, чужие данные закрыты. **CONNECT:** autosave/history P4-04. E04/S02; T15/T20.

### P3-06 · feature/official-package-adapter · WAITING_EXTERNAL только этот пункт

Получить package/README, checksum/реальный формат → mapping в ProblemBundleV1. Программный import TeX/assets/tests/limits/checker/validator/reference; no host scripts. T12/T14/T21 на официальных задачах. Пока материалов нет — P3-01–05; synthetic не выдаётся за official. Внешняя зависимость — организаторы, не агент 1.

### P3-07 · feature/yandex-problem-import · после обязательного MVP

Проверить официальные read/export API/права; import statement/metadata/assets, SSRF guards, mapping к local tests. Source-only NOT_READY, решения в Яндекс не отправляются. Отсутствие API не блокирует local judge/MVP. TEAM04; T12/T20 в части адаптера.

## Агент 4 — React и пользовательские сценарии

### P4-01 · feature/frontend-shell-auth · READY

React/lockfile/build/routes, session API client/CSRF rotation, реальные register/login/logout/me. Participant/admin navigation, public без redirect, loading/error/retry/empty. Public/private types раздельны; fixtures только dev/test entrypoint.

Готово: build/auth на существующем backend, регистрация без выбора admin, logout очищает private cache/user namespace. **Независимо:** от новых backend apps. TEAM01/02/S02; T02.

### P4-02 · feature/admin-roster-invites-ui · READY

CRUD/directory/roster/seed/cap на уже слитом API. Invite create/copy/expiry/maxUses/revoke/accept/register flow по API v1 в dev transport, до P1-01. Frozen/errors понятны; финальный сценарий без SQL/manual requests.

Готово: компоненты и real CRUD; **CONNECT:** real invite browser flow после одного API. M01–03; T03–05.

### P4-03 · feature/admin-match-ui · READY

Bracket/BYE/WAITING/manual pairs, tasks/rules/start mode; start/ready/pause/resume/extend/rematch/technical/replacement, reason/idempotency/state guards. Сейчас typed dev fixtures, затем замена transport без переписывания UI. **Не ждать:** всю A2 дорожку. M04–08; T06–11 UI часть.

### P4-04 · feature/participant-workspace · READY

Editor highlight/indent/brackets/hotkeys; safe Markdown/TeX/images/tables/examples, languages/templates/tasks/timer, async submit/history/CE. Local draft namespace user/run/problem/language, flush перед task switch/reload, server revision conflict без потери обеих версий. До start условия закрыты; paused/finalizing/infra retry видны.

По match/problem/submission/draft v1 fixtures; XSS/опасные URL/diagnostics как text. **CONNECT:** endpoints по одному, fixtures не в demo. P01–03/E01–04; T07/T12–15/T20.

### P4-05 · feature/spectator-map · READY

Anonymous bracket/match map, две дорожки и все task statuses, solved/penalty/leader/time/attempts/verdict, projector. Решение C без A/B отображается правильно. Snapshot/event reducer/dedupe/resync/reconnect/анимации по v1, score authoritative.

Готово: dev сценарии solve/overtake/tie/win/new run/disconnect; private data не загружается. **CONNECT:** real HTTP/SSE P2-06. V01–04; T16/T17/T20.

### P4-06 · feature/browser-api-integration · CONNECT по мере готовности

Каждый готовый API сразу проверять коротким browser scenario на SHA; не копить всё до «backend готов». Раздельные admin/participant sessions, anonymous spectator, refresh/task switch/reconnect/projector, полный полуфинал → финал с real official submissions, видео ≤5 минут. Missing API показывает ошибку, runtime fixtures исключены. T01–21 UI часть; финальный T21 требует всю систему.

## Завершение и история ID

READY — начать сейчас; IN_PROGRESS — исполнитель начал; IN_REVIEW — опубликован проверяемый срез; DONE — срез integrated и проверен. Полная приёмка требования отдельно: merge алгоритма не закрывает весь матч. WAITING_EXTERNAL/WAITING_CONNECT — только конкретный подпункт при наличии другой готовой работы.

PR содержит P-ID/requirements, v1/version, paths/migrations, команды/среду/SHA, audit/card, CONNECT и владельца. No secrets/public source/runtime fake verdict. Release gate T01–21 с official package и real hostile execution, working slice не отменяет обязательные функции.

| Старые задачи | Где продолжать |
|---|---|
| A1-01/02/03 | Backend срезы уже integrated; оставшаяся security/UI/history приёмка P1-02/03, P2-02, P4-01/02/06 |
| A1-04/05/06 | P1-01 / P1-04 + CONNECT владельцев / P1-05 |
| A2-01/02/03/04/05 | P2-01/02 / P2-03 / P2-04 / P2-05 / P2-06 |
| A3-01/02/03/04/05/06/07 | P3-01 / P3-02/06 / P3-03 / P3-04 / P3-01 / P3-05 / P3-07 |
| A4-01/02/03/04/05 | P4-01 / P4-02/03 / P4-04 / P4-05 / P4-06 |
