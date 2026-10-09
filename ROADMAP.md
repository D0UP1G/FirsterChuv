# ROADMAP v4: пять владельцев до рабочего MVP

Перепланировано координатором 2026-10-10 по прямому запросу команды. Новый Agent 5 полностью принимает frontend и дизайн. Agent 4 принимает public events/SSE и сквозную приёмку. Исторические P-ID сохранены: P4-01–06 остаются UI-задачами, их новый владелец A5. Выполненные cores не переписывать. [План до передачи](docs/history/ROADMAP-2026-10-10-before-frontend-handoff.md), [STATE](context/STATE.md), [ревизия PR](docs/reviews/2026-10-10-mvp-readiness.md), [кейc](docs/source/Кейс_Платформа_соревнований.pdf).

## Фактический этап

R0 — интеграционная база и проверенные отдельные модули. R1 — полный рабочий путь — ещё не принят. Auth/roles/CRUD/roster/invites, bracket ORM, clock/score/readiness/ledger/admin cores, queue/worker/outboxes, LocalJudge и React UI в develop. Нормализованный catalog имеется; compiler registry ещё не подтверждён runtime readiness. Брендбук — static reference, не готовая React интеграция.

Новая coordinator feature включает проверенные #21 (CAS исправлен), #50 (pairings/reset HTTP), #51 (коррекция SHA), #52 (frontend CI), #54 (дизайн с inert auth preview correction), #55 (publication docs), #56 (Markdown brandbook). До MERGED integration PR — IN_REVIEW; после подтверждённого MERGED/ancestry доступны из fresh develop без отдельного STATE PR. #53 fd79038 не включён: concurrent snapshot write может потерять cursor/дать database is locked; equal cursor допускает другой run/payload. Исправление — первое самостоятельное задание A4. #57–59 проверены, но не включены: SQLite read→write races, old-run participants не frozen (#58), feature-base вместо develop. Их исправление — первый READY A2; 16 happy-path tests не закрывают эти дефекты.

## Ближайший результат, который показываем

Админ создаёт турнир → два участника входят по invite → назначен immutable набор задач и оба ready/ручной start → участник видит условие и редактор → API принимает посылку → worker реально компилирует и проверяет её в Docker → durable result меняет score → победитель проходит дальше. Анонимный зритель получает public snapshot/SSE без исходников. Для первого smoke данные задачи импортируются программно в собственном normalized формате, вердикт вычисляется реально. Это R1, не финальная приёмка официального пакета.

## Пять параллельных дорожек

| Владелец | Первое READY действие | Следующее независимое действие | Пути |
|---|---|---|---|
| A1 | P1-02.5 failure DTO + run problem snapshot port, маленький совместимый PR | P1-03 PublicAccess/share/security; P1-04 build/Compose/readiness | common/config/accounts/tournaments/deploy/Compose/start scripts/CI |
| A2 | Исправить #57–59: full SQLite retry/immutable run participants/GitFlow base | P2-03 get/config/start/ready + gateways; P2-04 failure sink/finalization; P2-05 API | competition и свои migrations |
| A3 | P3-04.2 real LocalJudge worker executor/factory и smoke импорт без HTTP | P3-02.2 import management/workspace; P3-05 real provider CONNECT; cleanup fencing | problems/submissions/drafts/judge/sandbox |
| A4 | P4-07 snapshot correctness fix #53 на file-backed SQLite | P2-06.2/3 typed producers/public HTTP/SSE; P4-08 system acceptance harness | events и свои migrations/tests; scripts/acceptance; docs/quality/evidence |
| A5, новый | P5-01 tokens/layouts из frontend/design + реальный auth/invite/bracket UI | P4-03–06 CONNECT по одному готовому API; P5-02 responsive/accessibility | весь frontend/src/styles/client/editor/map/frontend tests |

PublicAccess producer A1 → A4 public transport; A2 run/gateway/result → A3 queue/workspace; A3 real judge → A2 score; A4 public HTTP/SSE → A5 UI. Совместимые typed ports/test fixtures позволяют писать свою часть сейчас. Provider absence в production — integration/readiness error, никогда mock verdict.

## Правило непрерывной работы

1. Не завершать назначенную дорожку после одного PR, пока есть READY работа.
2. Для конкретного CONNECT записать producer/consumer/DTO/path/SHA и WAITING_CONNECT; в этой же сессии выбрать следующий READY пункт таблицы. Ожидание review/общего STATE не блокирует весь агент.
3. Внутренние unit/API/DB tests используют typed test ports; demo использует реальные providers. Новый endpoint публикуется отдельно, UI подключается отдельно.
4. Свои AppConfig/URL includes разрешены владельцу app без ожидания A1, сохранять остальные регистрации. Shared contracts/config/Compose — A1 короткими PR.
5. Только отдельные checkout, feature/* от fresh develop, обычный merge при sync, PR→develop, без force push/branch deletion. До изменения own card: задача/branch/base/paths. На сессию новый append-only audit.
6. При отсутствии всех READY задач записать конкретные блокеры; явный стоп пользователя имеет приоритет. Назначение в Git не меняет незакоммиченный checkout соседнего автора.
7. Фиксировать implementation / integration / acceptance отдельно. Зелёные unit/CI или статичный экран не закрывают полный кейс.

## A1: платформа, безопасность, сборка

### P1-01 · invites · DONE backend, acceptance PARTIAL

#12 уже integrated: hashed token/expiry/revoke/use/cap/idempotency. Не повторять. P1-01.1 READY: стабилизировать конкурентные acceptance/retry на file-backed и shared-cache SQLite без ослабления capacity/assertions; прежние intermittent database_busy записаны. M02/S02; T04.

### P1-02 · common contracts / CI · PARTIAL

Исходный #17 integrated. P1-02.6 #52 добавляет locked npm/typecheck/lint/tests/build; coordinator ограничивает workers=1. После integration MERGED этот implementation DONE. Остаток P1-02.5 READY: frozen InfrastructureFailureReceipt/Sink и отдельный RunProblemSnapshot/Provider без изменения обязательных SubmissionPermit/ResultReceipt/verdicts. [Принятые границы](context/contracts/2026-10-10-mvp-boundaries.md). Common imports без optional apps. Опубликовать этот небольшой PR первым; остальные владельцы до него используют структурно совместимые локальные ports, не останавливаются.

### P1-03 · PublicAccess / share / security · READY

Public tournament anonymous read; unlisted — отдельный hashed read-only share token с expiry/revoke, не invite. Admin create/revoke link, private inaccessible. PublicAccessV1 context без source/email/secret. Proxy direct/one-hop/X-Forwarded-For spoof/rate limits; log redaction invite/share, CSRF/cookies/HTTPS и no-store/no-referrer. SQL/role/UUID/IDOR tests. CONNECT A4 SSE; пока ждёт — P1-04. S01/S02/TEAM06; T02/T20.

### P1-04 · one-command build/Compose/runtime · READY по срезам

P1-04.1 frontend multi-stage build + persistent SQLite/WAL/private storage, migrations/readiness/bootstrap, actual sandbox image build. P1-04.2 отдельные clock/worker providers/factories на точных merged SHA. Docker authority только trusted worker; API/solution её не получают. Не запускать фиктивные runtime profiles: до provider понятная readiness error. P1-04.3 restart DB/source/drafts/results и own-container fencing. D01/D03; T01/T19. A4 пишет acceptance harness, не редактирует Compose.

### P1-05 · release/demo · после R1/R2

Полная T01–21 совместно A4, official package и hostile проверки, README/env, demo либо видео ≤5 минут. release/* → main + tag → develop только после приёмки; main bootstrap. До этого выполнять P1-02.5/03/04/01.1. D04–06/T21.

## A2: настоящий матч и результат

### P2-01 · bracket ORM/registration · DONE implementation/integration, acceptance PARTIAL

#7 integrated через #44/#46; BYE/WAITING/frozen rank, generate/private read. Не писать заново. M03/M04; T05/T06.

### P2-02 · bracket lifecycle/pairings/reset · PARTIAL acceptance

P2-02.1 lifecycle correction integrated. P2-02.2 #50 — admin PUT full pairs по User UUID→frozen entrant, POST reset, reason/actor/Idempotency-Key/409/SQLite first-write. После integration MERGED implementation/integration DONE; browser/T06 ещё проверяет A5/A4. История played runs не удаляется, roster не размораживается.

### P2-03 · persisted run / clock / gateway · первое READY, R1 critical

P2-03.1 сначала fix #57 0073fbd: catalog ORM read внутри atomic до первого write даёт конкурентный lock error. Короткая безопасная transaction/retry, file-backed first config/update и rollback tests; PR→develop. Config/readiness persistence уже написана, не повторять. Затем configured MatchRun/current_run/immutable run participants/problem versions+checksum+rules; проверенные compiler только для READY/start. Реальные GET match/config/start/ready; manual/both_ready, two distinct players, idempotency, transaction/race, server active elapsed/deadline equality/paused semantics. Нужен durable run_match_clock/restart. Использовать готовые clock/readiness cores.

P2-03.2 CompetitionGateway authorize_submission/authorize_workspace и отдельный run-scoped snapshot resolver; trusted actor/membership/run/problem/time/actions/condition_available. Adapter вызывается внутри admission transaction; старая посылка использует свой run, не current/latest. Публиковать минимальный start+gateway срез сразу, не ждать admin actions или judge/UI. При CONNECT ожидании — P2-04/05. M05/M06/P03; T07–09.

### P2-04 · durable ledger/finalization/promotion · READY, R1 critical

Первое fix #58 1f3fae5: accepted/result reads до write claim дают lock errors; участники historical run восстанавливаются из mutable slots. Freeze participants на run и сохранять late historical results после replacement; full bounded transaction retry + file-backed admission/result/duplicate tests. Persistence slice уже написан, не повторять. Не повторять pure immutable ledger #38 и score #13. Unique accepted submission_id, original received/elapsed/rules; result/failure sink в DB, dup/out-of-order/SUPERSEDED. FINALIZING ждёт все принятые pending; infrastructure failure не становится WA/автопоражением. Winner/downstream/current score атомарны; full tie→новый run без переноса score. EventWriter producer A4 можно inject в tests. Typed receipt DB tests не требуют Docker/UI. M05/M07/J04; T09/T10/T19.

### P2-05 · durable admin effects/API · READY после/параллельно R1 persistence

Fix #59 7465a9c: same-key concurrency даёт uncaught lock error до exact replay; source base retarget develop. Pause/resume/extend/technical/rematch persistence уже написана, но не merged; test downstream guards/old-run history/replay на файле, затем API и replacement. Core guards #20 и receipts #41 integrated. Persist pause/resume/extend/technical/rematch/replacement, reason/actor/history, repeat exact command возвращает исходный receipt, changed intent 409, old run immutable, downstream started запрещает пересмотр. Runtime/API tests на trusted snapshots доступны без judge. M08/T11/T20.

### P2-06 · public events/SSE · TRANSFERRED → A4

P2-06.1 #16 integrated, OK→WA/CE сохраняет SOLVED+lastVerdict, closed public whitelist. P2-06.2 #53 требует исправления A4 P4-07; не считать integrated. P2-06.3 A4 public transport, heartbeat/cursor/resync/caps/slow client. A2 только вызывает adopted EventWriter из own transition transaction после CONNECT; не редактирует events параллельно A4. V01–03/T16–17/T20.

## A3: задачи, реальные вердикты, durable worker/workspace

### P3-01 · sandbox harness · integrated, full hostile acceptance PARTIAL

Исправленные F01/F07 и task limits уже integrated; prior actual Docker bounded probes сохранены. Не писать harness повторно. Остаток: доказанные ML/OOM/checker/privacy/cleanup/restart и official hostile T18/T20/T21. Все исполнения только bounded isolated container, compilation также внутри него.

### P3-02 · catalog/import/workspace · PARTIAL, READY

Normalized immutable catalog/private split #14, validation #25/admin GET #26 integrated. P3-02.2 normalized import management/upload/status без host extraction/scripts — доступен сейчас. Реальный compiler readiness probe, не manifest verified=true. Workspace statement/assets/languages — run-pinned version/checksum + real A2 access provider, закрытые artifacts не HTTP. Programmatic smoke import можно реализовать независимо от match/frontend. Official adapter отдельно P3-06. P01/P02/E02/T12/T13/T20.

### P3-03 · LocalJudge real deployment · core integrated, READY executor

#23 provider уже integrated; собственный compile/test/checker и task caps. Собрать актуальный sandbox image, подтвердить фактический compiler в trusted worker, immutable synthetic bundle → реальные OK/WA/TL/ML/RE/CE. Версия только original accepted run. CE/diagnostics author-only, checker/protocol errors — infrastructure. Этот real smoke не требует A2 HTTP/UI и не заменяет official acceptance. J01/J02/E03/T14/T18.

### P3-04 · queue/worker/providers · PARTIAL, READY, R1 critical

#15 queue admission retry и #37 heartbeat/leases/recovery/result+failure outboxes/adapters integrated. P3-04.2 production executor/factory с LocalJudge и owner/submission/claim-token fencing; runtime startup требует реальные result+failure sinks и trusted snapshot. P3-04.3 real A2 gateway/sinks CONNECT по одному merged SHA. P3-04.4 сохранить immutable version/checksum при admission из RunProblemSnapshot, после rematch worker не обращается к active latest; infra failure outbox durable/retry. [Границы приняты](context/contracts/2026-10-10-mvp-boundaries.md); WAITING теперь implementation/provider, не обсуждение формы. Пока ждёт A2 adapter — real executor/import/cleanup tests. J04/E03/T09/T14/T19/T20.

### P3-05 · private drafts/history · CAS исправлен, runtime PARTIAL

#21 620f58e: bounded retry whole CAS transaction BUSY/LOCKED, re-read revision, 409 winning draft, exhausted503; file-backed first create/update 18/18 прошли. После integration MERGED P3-05.1 implementation/integration DONE. GET selector принят: runId+languageId query; missing draft404, initial expectedRevision0, PUT runId body unchanged. Real WorkspaceAccess factory+IDOR/CSRF/no-store and actual autosave/reconnect/conflict/logout CONNECT A2/A5; без provider503. E04/S02/T15/T20.

### P3-06 · official package adapter · WAITING_EXTERNAL только этот пункт

Нужны package/README/checksum/права от организаторов; точный формат не выдумывать. Import statements/TeX/assets/tests/limits/checker/validator/reference программно, scripts на host не исполнять, private package не коммитить. Official T12/T14/T21 повтор после получения. До этого P3-02/03/04/05 READY.

### P3-07 · Yandex import · DEFERRED после обязательного MVP

Только импорт по проверенным официальным API/правам и SSRF guard, не проверка через Контест. Source-only bundle NOT_READY. TEAM04.

## A4: public backend и сквозная приёмка

Исторические P4-01–06 реализованы как UI slices и переданы A5; их исходные audit/card сохранены. Не редактировать frontend/src/tests. Events app теперь единолично A4, competition A2.

### P4-07 · snapshot fix / events handoff · первое READY

Сначала сохранить ancestry/audits #53 fd79038 обычным merge в собственной feature от fresh develop, разрешить registration/doc конфликты без потери apps, исправить snapshot concurrency и equal-cursor consistency. File-backed first-create/update и out-of-order interleavings: latest cursor не теряется, same cursor+same run+payload идемпотентны, same cursor с другим run/payload не перезаписывает состояние. Write-first/ограниченный полный retry, понятная transient storage policy; внешний event+snapshot transaction откатывается целиком. После review/CI merge. Не считать green13 existing tests достаточной concurrency приёмкой.

Далее P2-06.2 typed producers/snapshot/coherent cursor, P2-06.3 PublicAccess-protected public bracket/match snapshot+SSE, heartbeat/Last-Event-ID/resync/connection caps, strict closed DTO, никаких source/email/CE diagnostics. Runtime без A1 provider закрыт; tests/transport можно писать независимо. V01–03/S02/T16/T17/T20.

### P4-08 · system acceptance harness · READY независимый резерв

scripts/acceptance и docs/quality/evidence: disposable DB/identities, API auth/CRUD/invite/bracket object/CSRF checks доступных endpoint на exact SHA; независимые registry probes, snapshot/stream sequence tests; никаких запросов к пользовательской production DB. R1 script после каждого provider CONNECT: actual normalized import→run→queue→Docker→receipt→score→promotion. Отсутствие endpoint отмечать NOT_RUN/WAITING, не fake pass. При отсутствии Docker — API/tests/evidence работа продолжается.

### P4-09 · полный кейс / demo evidence · после R1, резерв PARTIAL checks сейчас

Вести T01–21 runtime/browser/official/restart/hostile evidence с A1/A2/A3/A5. Реальные две participant sessions/admin/anonymous; полуфинал→финал; безопасность/injections/private leaks; demo или видео≤5мин. Не менять production соседних apps для тестов без передачи найденного дефекта владельцу. Официальный пакет блокирует только относящиеся official checks.

## A5: весь frontend, брендбук и UX

Новая задача Codex: «Агент 5 — frontend и дизайн BLITZ_ARENA». Own isolated clone, own card/audits; [источник дизайна](frontend/design/README.md). Статичные HTML демонстрируют вид, все runtime данные приходят из API.

### P5-01 · brand tokens/shared components · первое READY

Перенести palette/fonts/spacing/layout/status tags из blitz.css в существующий React; header BLITZ_ARENA, accessible focus/errors/loading/empty/retry, статические mock actions не переносить. Сохранить CodeMirror, sanitization, draft scopes и typed transport. Tokens/components/auth/CRUD/invites/bracket готовы независимо от отсутствующего run/SSE provider. Никакого rewrite приложения.

### P5-02 · responsive/projector/accessibility · READY резерв

Desktop/mobile spectator, keyboard/focus/contrast/reduced-motion, projector и status readability; offline font fallback, plain text diagnostics, safe URL/Markdown. Не расширять scope профилем/чатом/магазином/рейтингом/ачивками. UI tests/typecheck/lint/build с bounded workers. Visual/browser checks в disposable sessions.

### P5-03 · real per-endpoint CONNECT · READY по доступным API

Fresh merged endpoint SHA→typed HTTP client→реальный browser сценарий→new audit/PR. Сначала auth/invite/admin/bracket #50 и ready catalog; затем match/config/start/ready, problem/language/draft, submission/history/result, public snapshot/SSE. Один WAITING endpoint переключает на P5-01/02/другой CONNECT, не завершает роль. Production без provider показывает конкретную ошибку, не mock data.

### P4-01 · auth shell · UI integrated, owner A5, acceptance PARTIAL

#22 и regression slices сохранены. Real csrf/register/login/logout/me, participant default/admin only, public spectator без login redirect, logout private namespace purge; T02.

### P4-02 · CRUD/roster/invite UI · integrated, owner A5, acceptance PARTIAL

#24 и prior real disposable browser auth/invite subset сохранены. Full browser CRUD/create/revoke/expiry/cap/register/accept/freeze errors; T03–05. Подключать доступный API сейчас.

### P4-03 · bracket/admin match UI · integrated, owner A5, CONNECT PARTIAL

#27 и каталог integrated; #50 pairings/reset после merge доступны. Ручные пары и admin reason/idempotency, then actual config/start/ready/actions по мере endpoint merge; T06–11. Missing endpoint error остаётся видимой.

### P4-04 · participant workspace/editor · integrated UI, owner A5, CONNECT PARTIAL

#28/editor hotkeys/indent/brackets/language/server validation/private recovery tests integrated. Real condition/time/tasks/submit/verdict/CE/history; user/run/problem/language local+server drafts, both conflict versions, reload/task/language/reconnect/logout. Condition скрыта до start; safe Markdown/TeX/images/examples и plain text diagnostics. T07/T12–15/T20.

### P4-05 · spectator map · integrated UI, owner A5, CONNECT WAITING по endpoint

#29 map/projector/reducer/fixtures готовы. Real A4 HTTP/SSE, анонимный просмотр без login, arbitrary solved task не блокируется A/B sequence, attempt/verdict/time/leader/penalty, dedupe/resync/reconnect/animation once. Private fields никогда не загружаются. T16/T17/T20.

### P4-06 · browser integration · owner A5, implementation PARTIAL

Prior auth/invite browser и 82 UI tests — частичные доказательства. Новый owner продолжает по одному actual endpoint; full R1/R2/R3 с A4 harness. При отсутствии серверного endpoint берёт P5-01/02/другой доступный CONNECT.

## Milestones и критерий остановки

| Этап | Статус | Критерий |
|---|---|---|
| R0 | Проверенные cores; новые slices до merge IN_REVIEW | imports/migrations/tests/CI совместно, original ancestry/audits сохранены |
| R1 | NOT_ACCEPTED | Реальная цепочка UI→API/run→queue→isolated judge→durable ledger→promotion; synthetic programmatic bundle, без mock verdict |
| R2 | NOT_ACCEPTED | Обязательные manual pairs/both_ready/admin actions/code persistence/recovery/privacy + базовая public map/SSE |
| R3 | WAITING official subset; остальные checks READY | Official package/checkers, полные T01–21, hostile, one command, demo/video, release/tag |

Резерв не отменяет приоритет R1: выпускать короткие реальные provider/API срезы. Нельзя бесконечно расширять pure core/test fixtures и избегать CONNECT. Нет достоверного процента или срока полной готовности до запуска сквозной цепочки. Все [37 требований](docs/requirements.md) и [21 сценарий](docs/quality/mvp-acceptance.md) сохранены.
