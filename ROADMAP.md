# ROADMAP v5: три агента и первый рабочий матч

Прямое уточнение команды 2026-10-10: остались Agent 3, Agent 4 (прежний Agent 1, включая текущего координатора) и Agent 5. A2 больше не является активным исполнителем; его готовые ветки, P-ID и аудиты сохраняются, работу принимает A4. Весь frontend принадлежит A5. [Предыдущий план v4](docs/history/ROADMAP-2026-10-10-before-three-agent-plan.md), [STATE](context/STATE.md), [кейс](docs/source/Кейс_Платформа_соревнований.pdf), [приёмка первого матча](docs/quality/m0-demo.md).

## Что уже есть и что мешает запуску

В develop `475cdf7` интегрированы auth/roles, tournament CRUD/roster/invites, bracket ORM и manual pairings/reset HTTP, persisted-run configure/readiness, match GET/config/manual start, clock/score/readiness/ledger/admin cores, normalized catalog, queue/worker/outboxes, LocalJudge, draft CAS, React editor/map и frontend CI. #60/#61/#62 и Agent 4 PR #67/#69/#74 MERGED. #74 добавил P2-03.2 реальные private match endpoints; source refs сохранены. Это готовые части, их не нужно переписывать.

#63 уточняет static reference по кейсу, #64 переносит токены бренда в React, #65 добавляет минимальные mobile/focus правила и own audit. В текущей coordinator feature они сохранены обычными merge commits; доступны другим владельцам после подтверждённого MERGED её PR. Runtime этих PR не меняет backend/providers. Проверки и точные source SHA — [ревизия](docs/reviews/2026-10-10-mvp-readiness.md).

Реального сквозного MVP пока нет. P2-03.2 routes доступны в develop, но gateway/WorkspaceAccess, frozen participants, durable result+failure sinks, actual worker executor/readiness HTTP и production browser path ещё не собраны. #53/#58/#59 остаются открытыми; A4 начал собственную P2-04 feature от `475cdf7` и сохранит required ledger/frozen-roster source changes обычными merge commits, исправляя file-backed defects. #57 source code включён через #69.

Дополнительный первый приоритет A3: в attempt 1 CI #63 на неизменённом backend concurrent same-key admission дал uncaught SQLite lock в QueueCounter. Attempt 2 зелёный; ошибка записана, не считается исправленной повтором CI.

## Три зоны без пересечения файлов

| Владелец | Вся зона | Первое READY задание | Независимый резерв |
|---|---|---|---|
| A4, прежний A1/координатор | accounts/tournaments/competition/events, common contracts, API permissions/domain/providers | P2-04 ledger/failure/clock (текущая feature); затем frozen-run gateway/WorkspaceAccess | P1-03 access/security; P2-05 admin replay/downstream repair; P4-07 snapshots |
| A3 | problems/submissions/drafts/judge/sandbox, config/factories/Compose/start scripts/CI, system acceptance | P3-04.1 admission contention; P3-04.2 реальный LocalJudge executor/factory + programmatic smoke import | P3-02 import/assets/compiler probes; P1-04 one-command build; P3-05 private draft access; P4-08 acceptance harness |
| A5 | весь frontend: React/design/styles/typed clients/editor/map/UI/browser checks | P5-03 подключить готовые auth/invite/admin/bracket API; минимальный бренд из #64 | typed match/workspace clients, loading/error/empty states, draft isolation, keyboard/minimal responsive |

A4 владеет backend/apps/common/contracts.py и contract fixtures. A3 владеет backend/config, deploy/Compose, start scripts и общим CI. Каждый backend app owner сам добавляет свой AppConfig/URL include минимальным изменением shared settings/api_urls, сохраняя существующие регистрации. Не ждать отдельного согласования такого include. Общие provider settings/entrypoints согласовать коротким CONNECT, не менять соседние apps. A5 backend не правит; findings передаёт владельцу через own audit/contract request.

## M0: ближайший демонстрируемый результат

Это промежуточный работающий срез. Он не закрывает все обязательные функции блоков 1–3 кейса и не называется полной приёмкой хакатонного MVP.

1. Чистый clone → env/bootstrap → одна документированная команда поднимает frontend/API/worker/clock; normalized demo bundle импортируется программно. Один реально проверенный compiler достаточен для первого smoke; список языков нельзя имитировать.
2. Admin создаёт турнир/invite; два обычных participant входят по ссылке. Admin выбирает 1–2 normalized задачи, одинаковые immutable rules/duration/languages для обоих и запускает матч вручную.
3. Участники видят доступное условие, server timer, editor; каждый отправляет код. API сохраняет посылку и возвращает 202. Worker действительно изолированно компилирует/проверяет, отдаёт OK/WA/CE; UI без reload показывает собственную историю, author-only CE и score. Draft не теряется при reload/switch.
4. Server clock закрывает приём, FINALIZING ждёт ранее принятые посылки, durable ledger выбирает победителя по rules; одинаковый результат не удваивает балл. Если следующий матч есть, winner продвижение атомарно. Инфраструктурный сбой — понятная техническая ошибка/восстановление, не поражение игрока.
5. После этого подключить минимальный anonymous public snapshot и существующую карту. Polling допустим только как промежуточный CONNECT M0; требование V03/T17 закрывается настоящим SSE позднее. Private code/CE/tests не попадают зрителю.

Изоляция компиляции и запуска, resource limits, no network/host/secrets, role/object checks, CSRF, immutable accepted-run snapshot, durable queue и честные ошибки обязательны уже в M0. Их нельзя отложить ради первого demo. Official package/README блокирует только официальный importer/относящиеся проверки; normalized programmatic smoke не требует его и не выдаётся за official acceptance.

## Правило работы при зависимости

- Назначена вся дорожка: после одного PR продолжать следующий READY пункт. WAITING_CONNECT/WAITING_EXTERNAL относится только к конкретному adapter/endpoint.
- В карточке записать producer, consumer, DTO/port, path, свежие source SHA и следующий независимый пункт. В той же сессии перейти к этому пункту. Не заканчивать всю работу из-за ожидания review/STATE/соседа, пока есть READY задания. Явный стоп пользователя имеет приоритет.
- Pure/service/API tests используют injected typed ports только в tests; production без реального provider отказывает с readiness/integration error. Готовый backend endpoint и его UI consumer выпускаются отдельными небольшими PR.
- Синхронизироваться с fresh origin/develop после каждого нужного merge. Не ждать завершения всей backend дорожки и не повторять integrated core.
- feature/* от fresh develop, own isolated checkout, PR→develop, ordinary merge, без force push/удаления чужих веток. До edits own card с branch/base/paths, после сессии новый append-only audit. Документация не запускает чужую остановленную сессию.

## A4: API и логика соревнования

### P1-01 · invites · backend DONE, browser/concurrency acceptance PARTIAL

#12 integrated: hashed token/expiry/revoke/cap/repeat. Не повторять. Резерв P1-01.1: стабилизировать file/shared-cache SQLite acceptance без ослабления cap/assertions; не тратить use повторно. A5 проверяет real invite browser path. M02/T04.

### P1-02 · common contracts / CI · PARTIAL

#17 и #52 CI integrated. Первым коротким PR P1-02.5 материализовать frozen InfrastructureFailureReceipt/Sink и RunProblemSnapshot/Provider из принятых boundaries. Existing v1 SubmissionPermit/ResultReceipt/verdict enum не менять. Common imports без optional apps. A3/A5 уже могут писать consumers на структурно совместимых ports, ждать их ответа не нужно. Общая эксплуатация CI передана A3; P1-02 не делает его зависимым от A4.

### P1-03 · access/security · READY

PublicAccessV1 для anonymous public и отдельного hashed unlisted share token (expiry/revoke, не invite). Сначала public visibility, полный share далее. Global roles/default participant, IDOR/private source/CSRF/no-store/no-referrer/proxy/rate limits/log redaction. SQL filters/ordering allowlist; unsafe Markdown/URLs/assets не исполняются. S01/S02/TEAM01/02/06; T02/T20. Резерв без judge/frontend.

### P2-01 · bracket ORM · implementation/integration DONE, acceptance PARTIAL

#7/#44/#46 integrated, BYE/WAITING/frozen rank/history. M03/M04/T05/T06. Не писать core повторно.

### P2-02 · bracket pairings/reset · implementation/integration DONE, browser PARTIAL

#50 integrated через #60. Admin PUT full first-round pairs по User UUID, POST reset до первого start, reason/actor/Idempotency-Key/exact receipt. Roster/history не стирать. Подключать A5 сейчас. M04/T06.

### P2-03 · persisted run / clock / gateway · M0 critical, PARTIAL

1. DONE: source #57 сохранён обычным merge в feature; configure read→write SQLite race исправлен и прошёл file-backed regression/rollback suite. PR #69 MERGED в `f9da1dd`, CI 5/5; Agent 4 card/audit содержат evidence.
2. DONE: match `GET/config/manual-start` routes в PR #74, merge `475cdf7`, exact-head CI 5/5 SUCCESS. Первая backend попытка поймала A3-owned QueueCounter lock regression; same-head повторный backend job прошёл. Retry не исправляет/не закрывает admission race; владелец A3 и P3-04.1 остаются ответственными. Implementation/publication/merge evidence — Agent 4 card и аудиты.
3. Следующий P2-03 slice после P2-04: frozen participant snapshot из #59 и безопасный CompetitionGateway/WorkspaceAccess + `RunProblemSnapshot` producer: membership/actor/run/problem/time/actions, condition hidden до start. Не выдавать current mutable slot за исторический run participant. `both_ready` требует отдельного ready route, key→body receipts и browser M0 тоже открыты. M05/M06/P03; T07–09.

### P2-04 · ledger / result / failure / promotion · M0 critical, IN_PROGRESS

Текущая feature `feature/a4-p2-04-ledger-persistence` создана от `475cdf7`. Сохранить #58 (`dc884e6`) ledger/finalization/clock и required frozen participant fix из stacked #59 (`dcc9997`) обычными merge commits только в свою feature. `register_accepted/apply_result` не читают до write reservation; file-backed concurrent tests. Accepted/result/failure effects exactly-once в delivery transaction. Deadline → FINALIZING до завершения accepted queue; delayed accepted OK учитывается; infrastructure failure не WA/RE/поражение и не бесконечное молчание. Score, clock, winner/downstream/event атомарны; old run не меняет new score. Исправить все P2-04 blockers до PR. M05/M07/J04; T09/T10/T19.

### P2-05 · admin effects/API · обязательный следующий этап, READY резерв

#59 0ba3119 пока не mergeable: read-before-write same-key race и rematch оставляет старого winner в downstream. Revoke/reopen unstarted downstream атомарно; started downstream запрещает пересмотр. Pause/resume/extend/technical/rematch/replacement, actor/reason/exact receipt/conflicting key409, original run immutable. Готовые guards/command cores уже integrated; не переписывать. Реальные file-backed replay/downstream tests, затем HTTP/UI CONNECT. M08/T11/T20.

### P2-06 · public events/SSE · PARTIAL, owner A4

Event store #16 integrated. P2-06.2 snapshot исправить через P4-07, lifecycle/result/accepted typed producers в той же transaction. P2-06.3 PublicAccess-protected bracket/match snapshots, затем SSE heartbeat/Last-Event-ID/resync/caps/backpressure. Closed public DTO: никаких source/email/private test/CE. A5 отдельно consumer. V01–03/T16/T17/T20.

### P4-07 · snapshot correctness · READY резерв / следующий public CONNECT

#53 fd79038 сохранить ancestry/audits ordinary merge, исправить concurrent first save/update: latest cursor не теряется, equal cursor только identical run+payload идемпотентен, equal conflicting snapshot отклонён. Write-first/bounded whole retry, controlled busy, event+snapshot outer rollback целиком. File-backed first create/update/out-of-order/equal-cursor tests; 13 happy tests недостаточны. После minimal run/sinks подключить anonymous snapshot M0; SSE отдельным PR.

## A3: задачи, исполнение и запуск всей системы

### P3-01 · sandbox harness · core integrated, acceptance PARTIAL

F01/F07/task caps исправлены, исторические real Docker probes сохранены. Подтвердить compile/run/checker resource limits, no network/host/secrets, ML/OOM/output/pids/cleanup на текущем integration SHA. Контейнер на исполнение, компиляция внутри изоляции. M0 basic safety, полный hostile T18/T20/T21 далее.

### P3-02 · catalog/import/workspace · PARTIAL, READY

#14/#25/#26 integrated. P3-02.2: программный normalized demo import command, assets/statements/TeX/images/table/examples/limits, private split; не ручной copy в UI. Runtime compiler probes, не доверять manifest verified=true. Workspace/языки используют pinned run version/checksum и A4 access; public hidden artifacts запрещены. Import/probe работа не зависит от HTTP A4. P01/P02/E02; T12/T13/T20.

### P3-03 · LocalJudge deployment · real core integrated, M0 executor READY

#23 provider reuse. Production sandbox image/actual compiler, normalized immutable bundle → реальные OK/WA/CE и далее TL/ML/RE. Checker/protocol failure инфраструктурный; CE author-only. Собственный smoke без API/frontend доступен сразу; это не official acceptance. J01/J02/E03/T14/T18.

### P3-04 · queue/worker/providers · PARTIAL, M0 critical

P3-04.1 первым устранить observed intermittent admission lock: CI #63 attempt1 concurrent same-key failed QueueCounter. Не лечить простым rerun; bounded full transaction retry/write-first, shared-cache и file-backed cases, exact one submission/receipt/event, original received_at, no source loss, exhausted503. #15/#37 queue/leases/heartbeats/recovery/result+failure outboxes уже integrated.

P3-04.2 actual LocalJudge executor/factory, own owner/submission/claim-token/lease fencing; Docker authority только trusted worker, не API или solution. P3-04.3 real A4 gateway/sinks CONNECT по одному merged SHA. P3-04.4 сохранять trusted version/checksum при admission, immutable accepted run resolution; old run не latest catalog. Startup requires real snapshot/result/failure providers, не mock fallback. Пока A4 endpoint ждёт — import/compiler/cleanup/Compose/recovery. J04/E03/T09/T14/T19/T20.

### P3-05 · drafts/history · CAS integrated, CONNECT READY по provider

#21 исправлен и merged через #60: full bounded retry, 409/current winner, exhausted503, file-backed18 PASS. GET runId+languageId query, missing404, first expectedRevision0; private service source author-only. Real WorkspaceAccess provider A4 → A3 factory/views → A5 autosave/conflict/reload/task/language/logout. Нет provider →503, не allow-all. E04/S02/T15/T20.

### P1-04 · one-command runtime/config/Compose · M0 critical, owner A3

P1-04.1 frontend multi-stage build + API/worker/clock services, persistent SQLite/private storage, migrations/normalized import/bootstrap admin/env без secrets. P1-04.2 реальные factories/settings/readiness на точных provider SHA; минимум одна документированная команда запуска, до provider fail-closed. P1-04.3 worker restart/leases/source/drafts/results/own-container recovery. API без Docker socket, sandbox без mounts/secrets/network; не global prune. A4 apps публикует отдельно, A3 wires runtime короткими PR. D01/D03/T01/T19.

### P4-08 · system acceptance harness · READY независимый резерв, owner A3

Disposable DB/identities, available auth/invite/bracket APIs, compiler/isolation probes, queue recovery checks уже можно писать. M0 script normalized import→run→queue→actual Docker→durable result→score/winner; отмечать missing endpoint NOT_RUN, не fixture pass. A5 browser evidence, A4 API/domain fixes. scripts/acceptance и docs/quality/evidence принадлежат A3; чужую production DB не использовать.

### P4-09 · full case/demo evidence · PARTIAL checks сейчас, после M0

Все T01–21: три отдельные browser identities + anonymous spectator, полуфинал→финал, admin interventions/both_ready/draft, official package, real hostile/restart/private leaks, one command, demo/video≤5min. A3 координирует system evidence, A5 browser и A4 domain. Missing official package блокирует только official subset.

### P1-05 · release/demo · после acceptance, owner A3

README/env/архитектура/вариант Б, demo либо video≤5min, кейс и full checks. release/*→main+tag→develop только после подтверждённой приёмки/поручения выпуска. До того main bootstrap и доступные M0 tasks.

### P3-06 · official package adapter · WAITING_EXTERNAL только этот пункт

Нужны официальный package/README/checksum/права. Формат не выдумывать, private пакет не коммитить; scripts/checkers не выполнять на host. Повтор official T12/T14/T21 после получения. До этого P3-02/03/04/P1-04/P4-08 READY.

### P3-07 · Yandex import · DEFERRED

Только future import по официальным API/правам с SSRF guard, не внешний judge. Source-only bundle NOT_READY. TEAM04; не тормозит M0.

## A5: весь frontend

### P5-01 · минимальный бренд/shared components · implementation #64/#65 IN_REVIEW, M0 приоритет

BLITZ_ARENA tokens/header/admin/auth style, preserve CodeMirror/sanitization/scoped drafts и typed transport. #64 CSS/metadata+brand label прошёл source CI; после coordinator merge available. Не переносить mock actions/data из 13 static screens. Нет необходимости полировать все экраны до real submit.

### P5-02 · minimal responsive/accessibility · READY резерв

Keyboard/focus/error/loading/empty/retry, 320px basic layout, readable statuses/contrast/reduced motion/font fallback. Browser/visual acceptance на actual SHA, не только DOM tests. Full projector/map polish после M0. Не добавлять shop/chat/rating/profile features.

### P5-03 · real per-endpoint CONNECT · первое READY

Fresh merged endpoint→typed client→actual disposable browser scenario→own audit/PR. Auth/invite/admin/bracket #50 доступны сейчас; затем config/start/read match, problem/language/draft, submit/history/result, public snapshot, SSE. Missing endpoint WAITING_CONNECT (A4 или A3, точный route/port), в этой же сессии взять доступный endpoint/typed states/драфты/адаптивность.

### P4-01 · auth shell · integrated, browser acceptance PARTIAL, owner A5

#22 + #62 safe return-path regression, csrf/register/login/logout/me, default participant, read-only anonymous spectator, logout private namespace purge. T02.

### P4-02 · CRUD/roster/invite UI · integrated, acceptance PARTIAL, owner A5

Real admin create/edit/assign/invite/revoke; register/login with safe next→join, expiry/cap/freeze errors. Первое доступное demo начало. T03–05.

### P4-03 · bracket/admin match UI · integrated UI, CONNECT PARTIAL, owner A5

PUT pairings/reset #50 available; actual config/manual start/readiness/server state по merged endpoints, позже both_ready/admin actions. reason/idempotency не подменять local state. T06–11.

### P4-04 · participant workspace · integrated UI, M0 CONNECT critical, owner A5

Real condition/assets/languages/server clock/editor/submit202/history/verdict/score/winner; safe Markdown/TeX/plain CE. Author/user/run/problem/language drafts, conflicts сохраняют обе версии; reload/switch/logout. Async updates без reload; нельзя показывать неподтверждённый verdict. T07/T12–15/T20.

### P4-05 · spectator map · integrated UI, endpoint CONNECT WAITING, owner A5

Anonymous snapshot сначала, full SSE/reconnect/dedupe/resync/animations/projector после M0. Arbitrary task order, attempts/leader/time, no private source. V01–04/T16/T17.

### P4-06 · browser integration · PARTIAL, owner A5

84 frontend tests и прежний auth/invite subset не full browser acceptance. Минимальный M0 две participant sessions/admin, далее full case с A3 harness и A4 domain. При зависимости продолжать другой CONNECT/typed loading/errors, не заканчивать дорожку.

## Контрольные этапы

| Этап | Текущий статус | Что доказываем |
|---|---|---|
| R0, база | integrated отдельные cores/UI | imports/migrate/CI, original ancestry/audits сохранены |
| M0, первый матч (уточняет прежний R1) | NOT_ACCEPTED | одна команда; реальные два игрока→run→submit→isolated judge→own verdict→score/winner; normalized import |
| M1, обязательный MVP блоков 1–3 (прежний R2 без public полного покрытия) | NOT_ACCEPTED | manual pairs/byes/both_ready/admin interventions, rich conditions/editor, все verdicts/drafts/recovery/security |
| M2, полная защита/командный MVP (прежний R3) | NOT_ACCEPTED; official subset WAITING_EXTERNAL | public map/SSE/projector, official tasks/checkers, T01–21/hostile, demo/video/release |

Все 30 parent P-ID из v4, 37 требований и 21 acceptance scenario сохранены. Переназначение не закрывает задачи. Нет подтверждённого процента/срока до M0 smoke. Координатор проверяет короткие готовые PR; агенты не ждут завершения всей соседней дорожки.
