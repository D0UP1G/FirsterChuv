# ROADMAP v3: четыре агента до рабочего MVP

Перепланировано координатором 2026-10-09 по новому поручению команды. Основание — [повторная ревизия](docs/reviews/2026-10-09-integration-review.md), исходный код/PR и 53 уникальных исторических аудита. Кейс/подтверждённые роли/DRF + React + SQLite/own sandbox не изменены. P-ID v2 сохранены; выполненные cores не писать заново. [Предыдущий план](docs/history/ROADMAP-2026-10-09-before-integration-review.md).

## На каком этапе проект

Есть платформа/auth/роли/CRUD/roster/invites и CI. В feature/mvp-integration-review-2 объединены проверенные #3 sandbox, #11 pure clock, #13 pure score, #14 normalized catalog; они доступны всем только после MERGED интеграционного PR. Состояние merge — GitHub и [STATE](context/STATE.md), до merge не подменять его словом DONE.

Пока это набор backend-компонентов, не работающий сквозной MVP: frontend не опубликован, матч не имеет рабочего runtime/API, нет LocalJudge/worker/drafts/SSE. #7/#15/#16 требуют исправлений, перечисленных ниже. Official package/README не получены. Процент готовности по количеству helper-файлов не рассчитывается.

## Как работать без остановки на зависимости

1. Начать первое READY задание своей дорожки и выпустить небольшой проверяемый PR. При назначении всей дорожки завершение одного PR не означает завершение поручения: брать следующую доступную задачу.
2. Если конкретный CONNECT ждёт соседний adapter, записать `WAITING_CONNECT` у него, требуемый port/DTO/SHA и принимающего владельца. В той же сессии перейти к резервной очереди ниже. Не заканчивать работу сообщением «жду агента» при наличии READY задачи.
3. Писать tests/domain/UI по immutable common ports и fixtures; отсутствующие providers не мешают этой работе. Runtime без настоящего access/catalog/judge/ledger adapter отказывает; dev/test fixtures не попадают в demo.
4. Минимальную AppConfig/URL регистрацию владелец app делает в своём PR. Общие настройки, Compose и тонкое wiring — короткие CONNECT-срезы; STATE sync не prerequisite.
5. Перед блокером fetch и проверить code/PR. Не переписывать чужие активные ветки; обычный merge develop в собственной ветке, сохранить все app registrations, CI и аудиты.
6. Остановиться при явном стопе пользователя либо когда все доступные подпункты своей зоны имеют конкретный внешний блокер. Ранее выданный стоп отдельной сессии не отменяется документом автоматически; эта роадмапа задаёт задания для следующего запуска четырёх агентов.

Каждый audit/card/PR содержит implementation, integration и acceptance отдельно, следующий READY шаг, выполненные команды и фактический SHA. Ветки feature/*, PR → develop, merge commits, без force push. План обновляется после реального результата, а не после обещания.

## Следующий параллельный запуск

| Агент | Первое действие | Пока CONNECT/review ждёт | Владение |
|---|---|---|---|
| 1 | P1-03 public/share access + proxy/logging | P1-04 Compose/readiness; P1-02 additive failure port | accounts/tournaments/common/config/deploy/scripts |
| 2 | P2-02.1 fix #7; P2-06.1 fix #16 | P2-03 persisted run/API; P2-04 ledger; P2-05 guards PR | competition/events, свои migrations |
| 3 | P3-04.1 fix #15; P3-03 real LocalJudge | P3-05 drafts; P3-02 import/workspace assets/registry | sandbox/problems/submissions/drafts/judge |
| 4 | P4-01 React + реальный auth | P4-02 real CRUD/invites, editor/local drafts, map reducer | frontend и browser tests |

Контракты: [v1](docs/architecture/parallel-contracts.md), [runtime handoffs](docs/architecture/runtime-handoffs.md). Реальные register/login/CRUD/invites доступны уже сейчас. A4 не ждёт A2/A3. A2 не ждёт judge для clock/ledger/HTTP и tests. A3 не ждёт clock для реального исполнения bundle. A1 не ждёт UI для access/proxy/infrastructure.

## Агент 1: платформа, безопасность, запуск

### P1-01 · invitations · DONE backend, browser CONNECT открыт

PR #12 merged: create/list/revoke/preview/accept, hashed token/use/cap/freeze/idempotency. Не повторять backend. P4-02 проверяет register/invite browser flow, A1 помогает исправлять конкретные API дефекты. M02/S02; full T04 открыт.

### P1-02 · CI/common contracts · DONE исходный срез, READY additive handoff

PR #17 и docs #18/#19 merged; 4 GitHub jobs, strict schemas/common ports/import isolation. Не повторять bootstrap CI. **P1-02.5:** материализовать отдельные additive InfrastructureFailureReceipt/Sink по runtime-handoffs, не менять существующий ResultReceipt/verdicts. У A2/A3 до merge допустимы локальные compatible Protocol в tests/core. После P2-05 PR добавить admin guard suite в CI, если она ещё не integrated. Branch protection recommendation не объявлять включённой: сейчас правил нет. D02/S01/S02; T20 partial.

### P1-03 · feature/platform-security-access · READY

PublicAccessV1: public read без login, unlisted только hashed read-only share token, revoke/expiry, отдельно от invite. Admin endpoint для выдачи ссылки и anonymous read adapter. Proxy topology: прямой localhost:8000 и NUM_PROXIES=1, X-Forwarded-For spoof/rate limit tests; один trusted proxy либо корректная direct policy. Access logs не содержат invite/share tokens; HttpOnly/session/CSRF/HTTPS settings согласованы с README. SQL-подобный search, role injection, UUID IDOR, no-store/no-referrer.

Готово: backend/tests и порт, без judge/UI. CONNECT A2 public HTTP/SSE; пока он ждёт — инфраструктура P1-04. S01/S02/TEAM06; T02/T20 частично.

### P1-04 · feature/mvp-compose-wiring · READY, подключения по одному

Сейчас Compose запускает только API; web dist/clock/worker отсутствуют. Настроить persistent SQLite/WAL, readiness/migrations, frontend build, startup bootstrap, private storage и sandbox image build, trusted worker Docker authority. Docker socket не монтируется API или solution. Секреты не выводить в logs/README/audit.

P1-04.1 инфраструктура и script/config validation доступны сейчас. P1-04.2 подключить настоящий run_match_clock A2, run_judge_worker A3 и frontend A4 отдельно по готовому SHA. Пока command/provider отсутствует — readiness/integration error, не объявлять profile runnable. P1-04.3 restart сохраняет DB/source/drafts/results и убирает только свои orphan containers. Одна documented команда должна поднимать весь готовый сценарий. D01/D03; T01/T19.

### P1-05 · feature/demo-readiness → release/0.1.0 · финальная системная приёмка

После рабочего среза провести T01–21 с владельцами, official package и hostile expert-style checks, полуфинал → финал, demo либо видео ≤5 минут. Release → main + tag → develop только после обязательной приёмки; main сейчас bootstrap. До этого выполнять P1-03/04/02.5, не ждать «весь backend». D04–06; T21.

## Агент 2: сетка, настоящий матч, результат, public stream

### P2-01 · bracket registration · IN_REVIEW, #7 требует P2-02.1

HEAD #7 1952244 уже имеет ORM/ordinary AppConfig/URL registration, BYE/WAITING/canonical rank и private generate/read. Старые seed/import/registration blockers закрыты. Не писать повторно и не ждать A1. После lifecycle fix обновить свою ветку из develop, сохранить clock/score/catalog registrations и CI, повторить suite/check/migration drift, опубликовать тот же PR. M03/M04; T05/T06 partial.

### P2-02 · feature/bracket-persistence · READY

**P2-02.1 приоритет:** #7 services generate/reset/full pairings допускают archived/running/completed. Единый guard draft/scheduled внутри transaction до existing-return/freeze, SQLite conditional write до reads для сериализации с archive/start. Regression всех трёх mutators и HTTP generate; отказ сохраняет matches/freeze/roster. После проверки merge #7.

P2-02.2 full first-round PUT pairings по v1 User UUID → frozen entrant UUID, POST reset, reason/actor/Idempotency-Key/409 rules. Сервисы уже написаны, добавить HTTP/idempotency/lifecycle/race tests. Не размораживать roster, BYE без played run, начавшаяся история не удаляется. Ничего не требует живого judge/UI. M03/M04; T05/T06.

### P2-03 · feature/match-clock-start-runtime · READY

Pure clock #11 проверен и включён в интеграционный срез; не писать заново. Сделать persisted current MatchRun/state/config, immutable problem versions/checksum/rules, READY/RUNNING/PAUSED/FINALIZING, manual/both_ready, реальные get/config/ready/start API и run_match_clock/restart. Catalog в #14 — готовый порт; verified compiler нужен только для настоящего READY/start, test catalog допустим в tests.

CompetitionGatewayV1.authorize_submission/authorize_workspace: trusted actor/current run/membership/task/condition/time, strict deadline equality закрыта, active elapsed без пауз. Все DB решения в транзакции вызывающего submission service. До runtime adapter production fail closed. CONNECT A3 коротким срезом; если он ждёт — ledger и actions. M05/M06/P03; T07–09.

### P2-04 · feature/match-ledger-results · READY

Pure score #13 проверен, не повторять. Реальный accepted-attempt ledger с unique submission_id и immutable server received/elapsed; register_accepted/apply_result по common v1, idempotent duplicate/out-of-order/SUPERSEDED. FINALIZING ждёт accepted pending results; инфраструктурный сбой не превращать в RE/WA или поражение. Additive failure sink помечает техническую проблему и разрешает восстановление/ручное вмешательство без автоматического победителя.

Winner/downstream/event одной transaction либо согласованным durable outbox; full tie → новый run, старый score не переносится. Domain/DB tests с typed test receipts независимы от sandbox. CONNECT A3 queue/result/failure adapter. M05/M07/J04; T09/T10/T19.

### P2-05 · feature/match-admin-actions · READY для завершения уже начатого среза

Ветка 8f5b762 имеет pure guards, 12 tests, PR ещё не создан. Сохранить эту работу, sync develop, опубликовать малый guards PR с аудитом/CI, затем persisted pause/resume/extend/technical/rematch/replacement. Trusted actor/reason/command receipts, idempotency, history/no-score-carry, atomic запрет изменения после started downstream. Пока runtime ждёт — guards/command store/tests. M08; T11/T20.

### P2-06 · feature/public-events-sse · READY

**P2-06.1 приоритет:** #16 8340014 validator ошибочно требует SOLVED.lastVerdict==OK. OK→WA/CE сохраняют SOLVED, lastVerdict отражает последнюю попытку. Исправить validator без ослабления whitelist/privacy; score→event roundtrip tests, затем merge store slice.

P2-06.2 EventWriter adapter/producers и durable snapshots с coherent lastEventId; P2-06.3 public HTTP/SSE/heartbeat/cursor/resync/connection caps/slow client. PublicAccessV1 A1 подключить отдельным CONNECT, event store/projector/transport tests писать сейчас. Если access adapter ещё отсутствует, public runtime не открывать. Source/email/CE никогда не public. V01–03/S02; T16/T17/T20.

## Агент 3: реальные вердикты, надёжная очередь, workspace

### P3-01 · sandbox harness · исправления проверены, full isolation acceptance открыт

#3 6950f10 включён в integration slice: F01 удалён, F07 PR_SET_DUMPABLE + bounded host pipe исправлены. Fresh Docker image, 12 unit/5 real smoke, bounded PID/memory/network/host/protocol/output/watchdog/compile/cleanup/recovery probes прошли. Обычный следующий job OK. Не повторять готовый harness.

Осталось для LocalJudge: лимиты каждой задачи, compiler/checker в изоляции, ML только по подтверждённому OOM, private bounded diagnostics, restart/orphan cleanup собственных jobs. Fixed smoke limits не заменяют task limits. J01/J03/S01; full T18/T20/T21 открыт, official expert checks ещё нужны.

### P3-02 · normalized problem storage/import core · PARTIAL, READY остаток

#14 9234951 проверен и включён в integration slice: bounded ZIP/no extraction, immutable checksum/version, public/private split/catalog, verified compiler gate. Не писать повторно. Registry сейчас verified=false; подтвердить compiler/runtime перед READY, не ставить true из manifest.

P3-02.2 programmatic normalized import management/API, admin catalog/task selection, access-filtered problem/asset/language endpoints по CompetitionGateway, private artifacts не выдаются. P3-02.3 strict artifact language ID types: list/dict сейчас дают TypeError; typed invalid-manifest tests перед внешним importer. Safe Markdown/TeX rendering у A4. Official mapping отдельно P3-06. P01/P02/E02/S01; T12/T13/T20 partial.

### P3-03 · feature/local-judge · READY, главный execution шаг

JudgeProvider.execute(TrustedJudgeJob) загружает immutable version/checksum из snapshot run, не active latest version. Из normalized bundle реальные compile/test/checker, time/memory/process/output caps, actual compiler allowlist. OK/WA/TL/ML/RE/CE и multiple-valid-output checker, CE author-only, infra failures отдельны. Test solution компилировать/запускать только sandbox; scripts package на host не запускать.

Сначала программно импортированная синтетическая smoke-задача и настоящее исполнение, затем официальный повтор P3-06. Это проверяет рабочий pipeline и не выдаётся за official T12/T14/T21. Можно делать без HTTP match/frontend. J01/J02/E03; T14/T18 partial.

### P3-04 · feature/submission-queue-core → worker/connect · READY

**P3-04.1 приоритет:** #15 7d76d0b concurrent admission даёт OperationalError/database locked → 500. Bounded retry всей transaction только busy/locked с неизменным received_at, либо согласованный write-first подход; исчерпание → понятный retryable 503. File-backed TransactionTestCase: два разных/одинаковых keys, cap/ledger/event rollback, без 500. После review интегрировать core.

P3-04.2 actual run_judge_worker/loop/claim/lease/retry/outbox/restart/own orphan cleanup. P3-04.3 thin local MatchPort/AcceptedLedger/ResultSink adapters к CompetitionGatewayV1: extra local match_id остаётся на стороне queue, ResultApplication.applied преобразуется в bool; applied=false не означает delivery failure. LanguageRegistry совпадает. P3-04.4 trusted job version/checksum из immutable run snapshot; failure sink для exhausted infra jobs, чтобы pending ledger не висел навсегда без понятной технической причины. Никаких fake verdict.

Core/recovery/adapter tests независимы от живого match provider; runtime CONNECT требует реальных A2 ports. Пока он ждёт — LocalJudge и drafts. J04/E03; T09/T14/T19/T20.

### P3-05 · feature/private-drafts-history · READY независимо от judge

Revisioned server drafts user/run/problem/language, author-only source/CE/history, active-user/UUID IDOR/CSRF/no-store. CompetitionGateway workspace allowed_actions/condition availability, test AccessContext до CONNECT; отсутствующий access provider отказывает. Revision conflict сохраняет обе версии, local editor draft sync A4, logout очищает private namespace. E04/S02; T15/T20.

### P3-06 · feature/official-package-adapter · WAITING_EXTERNAL только этот пункт

Получить package/README/permission/checksum от организаторов, mapping к normalized bundle. Import statements/TeX/assets/tests/limits/checker/validator/reference без host scripts; закрытые материалы не коммитить. Official programmatic import и реальный judge/сценарий T12/T14/T21. Пока package нет — P3-02/03/04/05, не завершать всю роль.

### P3-07 · feature/yandex-problem-import · после обязательного MVP

Только import statement/metadata/assets по проверенным официальным API/правам, SSRF guard. Source-only NOT_READY; решения в Яндекс не уходят. Не отнимать время у рабочего local pipeline. TEAM04.

## Агент 4: React и полный пользовательский путь

### P4-01 · feature/frontend-shell-auth · READY, самый срочный UI шаг

Frontend в опубликованных refs отсутствует; проверить свой checkout, не перезаписать неопубликованную работу. React/TS/lockfile/build/router/API client, реальные csrf/register/login/logout/me, role navigation, anonymous public без login redirect, loading/error/retry/empty. Auth доступен сейчас: не ждать A2/A3. Login CSRF rotation, logout чистит user/private cache. P4-01 завершает реальный build/auth, а не только макет. TEAM01/02/S02; T02.

### P4-02 · feature/admin-roster-invites-ui · READY на реальных API

CRUD/directory/roster/seed/cap/invite create/copy/revoke/preview/accept/register flow уже backend-integrated. Подключать настоящий transport сразу, не mock. Browser admin создаёт турнир/ссылку, два participant входят без SQL/manual requests; freeze/revoke/expiry/cap/role errors видимы. M01–03; T03–05.

### P4-03 · feature/admin-match-ui · READY

Bracket/BYE/WAITING/full first-round pairs/config/task selection/start/ready/actions/reason/idempotency, typed dev transport по v1, runtime без fixtures. До готовности endpoint строить компоненты, потом CONNECT по одному. Не ждать всю A2 дорожку. M04–08; T06–11 UI часть.

### P4-04 · feature/participant-workspace · READY независимо от queue

Editor highlight/indent/brackets/hotkeys/languages/templates, safe Markdown/TeX/images/tables/examples, tasks/status/timer, async submit/result/CE/history. Local draft namespace user/run/problem/language/revision, flush на task switch/reload, обе версии при server conflict. Source/CE private, XSS/опасные URL запрещены, diagnostics plain text. До старта условия закрыты.

UI/editor/local persistence доступны сейчас с отдельным dev transport; реальные problem/draft/submission APIs подключать по одному. In production отсутствующий API показывает error, mock verdict запрещён. P01–03/E01–04; T07/T12–15/T20.

### P4-05 · feature/spectator-map · READY

Anonymous bracket/match route map, две дорожки, все задачи/attempts/verdicts/leader/penalty/timer, независимое решение C без A/B, projector. Reducer/snapshot/event dedupe/resync/reconnect/animations можно писать сейчас по fixtures; реальный HTTP/SSE CONNECT P2-06 + PublicAccess A1. Private source/email/CE не запрашиваются. V01–04; T16/T17/T20.

### P4-06 · feature/browser-api-integration · CONNECT по одному, финал после runtime

Не ждать «backend полностью готов»: каждый новый endpoint проверить коротким browser scenario на exact SHA, отдельно admin/две participant sessions/anonymous. Первый реальный срез — create/invite/match start/editor/programmatic smoke bundle/real submission/verdict/score/promotion. Затем official package и полный T01–21, reconnect/reload/task switch/restart/hostile, demo/видео ≤5 минут. Не считать synthetic working slice полной case acceptance.

## Приоритетные milestones

| Milestone | Критерий | Владельцы |
|---|---|---|
| R0: интеграционная база | #3/#11/#13/#14 + текущая платформа вместе, CI pass; #7/#15/#16 исправлены короткими PR | Координатор, A2/A3 |
| R1: первый рабочий путь | React → real API/run → durable queue → LocalJudge → receipt/score → продвижение; programmatic smoke import, без mock runtime | A1 wiring, A2 gateway/ledger, A3 judge/worker, A4 UI |
| R2: обязательные функции | Manual pairs, both_ready, все admin interventions, code persistence, failure/restart/privacy, базовая public map/SSE | Все четыре |
| R3: сдача по кейсу | Official package/checkers, T01–21, hostile checks, одна команда, demo/видео, release/tag | Все четыре |

R1 не отменяет R2/R3. Пакет не блокирует R0/разработку R1, но без official package финальная приёмка не закрыта. История A-ID и P-ID сохранена в docs/history и аудитах. Все задачи сверены с [37 требованиями](docs/requirements.md) и [21 сценарием](docs/quality/mvp-acceptance.md).
