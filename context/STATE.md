# Состояние проекта: три агента и первый рабочий матч

## Release checkpoint · 2026-10-10T08:43:31+03:00

Интеграционная база выпуска: `origin/develop=d524343f75149e624d56e4970cd059d6216e1f5b` (после PR #92–#100, включая A4 Wave 3 PR #93 и A3/A5 Wave 3 slices #92/#94). По поручению команды готовится `release/0.1.0`; PR направляется в `main`, затем annotated tag `v0.1.0` ставится на merge commit, и release возвращается в develop ordinary PR/merge.

Evidence на develop включает основной browser путь и реальные Docker вердикты `OK`/`WA` ([A5 verdict evidence](../docs/quality/evidence/2026-10-10T082341+0300-A5-real-verdicts.md)). Это ограниченный прогон: CE/TL/ML/RE, автоматическое завершение/переход победителя, hostile/restart проверки и официальный package не подтверждены. M0/M1/M2 и T01–T21 сохраняют текущие статусы `NOT_ACCEPTED`/`PARTIAL` в [матрице M0](../docs/quality/m0-demo.md), [приёмке](../docs/quality/mvp-acceptance.md) и [ROADMAP](../ROADMAP.md). Сам выпуск не меняет эти статусы.

Ветка release базируется ровно на указанном SHA. Python уже `0.1.0`; frontend package metadata приводится к `0.1.0` в release metadata. Docker endpoint и секреты в этой сессии не настраивались; evidence #98 относится к отдельному изолированному локальному стенду.

Текущий интеграционный снимок 2026-10-10T06:02:48+03:00, Europe/Moscow. `origin/develop=ee755af6ed93e7c3996cb5e70edd8d21e527c56a`; обычный merge PR #82 интегрировал A4 P2-03.4 (ready HTTP/body-bound match receipts), exact-head CI 5/5 SUCCESS. PR #84 обычным merge интегрировал A4 P1-03 share access; exact-head CI 5/5 SUCCESS. P1-03 implementation audit, P1-03 merge audit.

A4 выполняет последнюю независимую задачу Wave 1 P1-01.1 в `feature/a4-p1-01-1-invite-concurrency` от `ee755af6ed93e7c3996cb5e70edd8d21e527c56a`. A3 legacy invite URI access-log redaction передано в contract request; A4 не меняет A3-owned Nginx/settings/Compose. Wave 2 не начата. Полный M0 остаётся NOT_ACCEPTED.

Снимок 2026-10-10T03:55:27+03:00, Europe/Moscow. Активные роли: A3, A4 (прежний A1/координатор), A5. [ROADMAP v5](../ROADMAP.md), [M0 demo](../docs/quality/m0-demo.md), review.

- Fresh `origin/develop`: `5f8e7d5a76e296e3cdc3bafe88782540c4168179` (merge #77). PR #77 final head `97ca67091a4ad54f3ac0f0db2e70323d4a03dd2d`, ordinary merge; exact-head CI 5/5 SUCCESS: backend, contracts-and-common-imports, domain, frontend, sandbox-unit. P2-03.3 merge audit.
- P2-03.3 provider интегрирован: frozen-run CompetitionGateway/WorkspaceAccess, server-time submit permit и RunProblemSnapshot producer доступны на develop. A3 production queue/worker/draft factory CONNECT всё ещё отсутствует; ready HTTP, body-bound key receipts и end-to-end/browser acceptance открыты. P2-04 ledger/result/failure/finalization также интегрированы в develop с ancestry #58/#59. P2-04 merge audit.
- A4 начал `feature/a4-p4-07-snapshot-correctness` от свежего `5f8e7d5`. PR #53 остаётся OPEN на source head `fd79038847a23b38bb8a444c028b87ce75ed9571`; его ancestry нужно сохранить ordinary merge только в своей feature и исправить snapshot races, source ref не менять. A3 owns runtime/config/submission/draft consumers; A5 owns browser/map clients.
- M0 остаётся NOT_ACCEPTED: real queue/worker/isolated verdict, ledger/failure/promotion, UI/browser multi-session и one-command runtime не подтверждены на одном SHA. A3 owns import/judge/worker/CI; A4 API/domain/events; A5 frontend.

## Готовность

R0: integrated отдельные cores/UI/auth/tournament/invite/bracket/draft. M0 первый реальный матч ещё NOT_ACCEPTED: отсутствует полная production цепочка run/gateway → queue/worker/isolated judge → result+failure sinks → UI/score/winner и one-command runtime. M1 обязательные блоки 1–3 и M2 public/SSE/projector/official/demo также NOT_ACCEPTED. 37 требований/21 acceptance сохранены; unit/CI/static screens не заменяют real/browser/hostile/official acceptance. Срок/процент готовности не заявлен.


## История предыдущих ревизий

Снимок 2026-10-10T01:15:16+03:00, Europe/Moscow. База develop cc204e6 включает code integrations#20/#32/#44/#46 и A4 docs#48/#49. Main e9fc0ef bootstrap. Проверенные новые#21/#50/#51/#52/#54/#55/#56 объединены ordinary merge commits в coordinator feature/mvp-readiness-handoff; до MERGED integration PR статусIN_REVIEW, после фактического MERGED доступны из fresh develop. Отдельный STATE PR не prerequisite. Report, outcome audit, [ROADMAP v4](../ROADMAP.md).

## Подтверждённый результат 2026-10-10T01:36:20+03:00

[PR #60](https://github.com/D0UP1G/FirsterChuv/pull/60) MERGED: develop723985f02b2f1c5fc4a38b3c67f6e055dd1ad8fa, родители cc204e6 и final head9d7996d. [Final CI37999734345](https://github.com/D0UP1G/FirsterChuv/actions/runs/37999734345) 5/5 SUCCESS. #21/#50/#51/#52/#54 latest94d42a0/#55/#56 имеют GitHub MERGED; их heads доступны в develop, 166 audits сохранены. Main e9fc0ef unchanged. Предыдущий IN_REVIEW текст выше — snapshot до операции, не текущее ожидание.

#53/#57/#58/#59 OPEN. Координатор перевёл base #57–59 в develop, source refs не менялись; #58/#59 сейчас требуют merge fresh develop/conflict resolution, кроме correctness fixes. Latest #58 733acc6 добавил FINALIZING drain/winner promotion/events:13 source tests PASS, file-backed accepted/result/config races FAIL, historical participants fix есть только в leaf #59. Синхронизировать обе ветки ordinary merge, сохранять оба среза; готовые cores не повторять. Latest #59 9eb394c19 tests PASS, historical result теперь сохраняется; race/rematch downstream blockers остаются. Полный R1 ещёNOT_ACCEPTED.

A5 получил follow-up о реальном MERGED и active snapshot подтвердил fetch/merge/продолжение auth slice и новой READY очереди. Его84 tests/local code не часть coordinator255/82 evidence. Назначения A1–A4 записаны в Git; наблюдение не означает, что внешние сессии сейчас запущены. Explicit stop конкретной сессии учитывается. Новый closing audit.

## Что изменилось

- Прежний draft CAS blocker#21 исправлен на620f58e: file-backed concurrent first-create/update PASS, stale409, lock exhaustion503; production WorkspaceAccess отсутствует, полныйT15 открыт.
- #50 даёт настоящий admin pairings/reset HTTP с User UUID mapping, CSRF/reason/idempotency/lifecycle/SQLite first-write. Match/config/start/ready/clock/ledger/promotion пока не runtime.
- #52 добавляет frontend CI вместе с существующими4 jobs; combined feature ограничивает worker1.
- #54 брендбук BLITZ_ARENA:13 HTML screens/tokens и собственный inert auth preview fix. React styling переносит новый A5, production UI ещё не branded этим PR.
- #56 Markdown brandbook доступен как reference; #54 latest94d42a0 сохраняет grid/text rhythm и inert auth correction.
- #57/#58/#59 не включены: реальные file-backed configure/admission/result/admin lock errors; historical participants в original #58 mutable, latest #59 9eb394c исправляет snapshot (late result PASS). 19 tests PASS, четыре race probes и rematch downstream probe FAIL; первое READY A2 — исправления и PR base develop.
- #53fd79038 не включён: concurrent snapshot SQLite500/cursor loss и same-cursor different run overwrite. FixA4P4-07 READY, source PR остаётсяOPEN.
- A5 создан в отдельной Codex задаче; первый локальный auth срез завершил, ожидает handoff merge, затем продолжает READY очередь; frontend/P4-01–06 переданы ему. A4 владеет events/SSE/system acceptance. A1 common/access/build, A2 competition/run/ledger, A3 real judge/worker/workspace.

## Проверенный этап и остаток

R0 — совместимые модули; полныйR1 ещёNOT_ACCEPTED. Backend255 PASS/4skips first attempt, file-backed draft18/bracket24, domain68/sandbox15/schema9/import/check/drift, frontend82/typecheck/build PASS; lint5 прежних warnings/editor chunk warning. Combined remote CI публикуется на финальном SHA и отдельно gate перед merge. Actual Docker/hostile/official/full browser pipeline в этой ревизииNOT_RUN.

R1 critical: persisted configured run/gateway → immutable accepted version/checksum → actual worker/LocalJudge providers → durable result/failure ledger → score/winner/promotion → real React endpoints. Для spectator дополнительноPublicAccess/fixed snapshots/producers/HTTP/SSE. R2: полные admin actions/server draft browser persistence/recovery/privacy. R3: official package/README/checkers, полныеT01–21, hostile, одна команда/demo/video/release. Отсутствие пакета блокирует official subset, не независимую normalized smoke разработку.

## Следующая работа параллельно

A1 — P1-02.5 common failure/snapshot typing, затем PublicAccess/build. A2 — fix #57–59 SQLite/frozen participants и base develop, затем P2-03 HTTP/gateway; reserve failure/finalization/admin API. A3 — real worker executor/factory+programmatic bundle, reserve import/drafts/fencing. A4 — snapshotfix#53, reserve public transport/system harness. A5 — branded shared UI+доступныеauth/invite/bracket, reserve responsive/editor/real CONNECT по одному endpoint. WAITING у конкретного adapter не завершает всю роль.

## Предыдущие датированные snapshots

# Состояние проекта после новой проверки PR

Снимок 2026-10-10T00:10:11+03:00, Europe/Moscow. Основной integration #44 MERGED; develop `03a463650828774d5767e086a69183f83c38006b` включает также A4 #45. Closeout feature `feature/mvp-review-closeout` сохраняет поздний sync/audit source #7; production/tests не меняются. Main `e9fc0ef` остаётся bootstrap.

Предыдущий integration [PR #32](https://github.com/D0UP1G/FirsterChuv/pull/32) MERGED: queue #15, LocalJudge #23 и admin catalog #26 доступны в develop. Frontend #33/#35/#36/#39/#40/#42/#43/#45 также MERGED; исходники и карточка активного A4 сохранены.

В develop доступны #7 `1a2b54a`, #16 `a0b1dcc`, #34 `730edd8`, #37 `d331927`, #38 `92af1d6`, #41 `c8b8043` через MERGED [PR #44](https://github.com/D0UP1G/FirsterChuv/pull/44). #16/#34/#37/#38/#41 имеют GitHub MERGED; source #7 успел обновиться до `f300150` и его поздний sync/audit сохраняется отдельным closeout. Его код уже интегрирован: P2-02.2/P2-03 можно продолжать сейчас. Review audit, все попытки CI, merge/closeout audit. Source refs сохранены; отдельный STATE prerequisite отсутствует.

## Проверенная реализация и оставшаяся работа

| Компонент | Проверенный срез | Следующая часть MVP |
|---|---|---|
| Auth/roles/CSRF/CRUD/roster/invites | В develop | Browser/object/runtime acceptance |
| Catalog/queue/LocalJudge/sandbox | В develop через #20/#25/#32 | Verified compiler, official checker/package, runtime wiring |
| Bracket/Match/MatchSlot/MatchRun ORM | #7 в develop через #44; generate/private read, lifecycle guard | HTTP reset/pairings; persisted configured run/API |
| Readiness/clock/score | Clock/score в develop; both_ready #34 в develop через #44 | Atomic readiness/clock persistence, start/config/ready API и clock command |
| Accepted ledger/results | Pure immutable #38 в develop через #44 | Persistent ledger/failure sink, FINALIZING/winner/downstream/events |
| Admin actions | Guards в develop; pure command receipts #41 в develop через #44 | Durable receipt/effect transaction, timer/history/API |
| Public events | #16 в develop через #44; score.changed/cursor, OK→WA/CE fix | Producers/snapshot/PublicAccess/HTTP/SSE |
| Submission worker | #37 в develop через #44; heartbeat/DB recovery/adapters/result+failure outboxes | Trusted accepted-run version/checksum, real providers/executor/factory, own container cleanup |
| Private drafts | #21 `1706ecf` OPEN | P3-05.1 CAS retry/409/503 перед merge |
| Frontend | UI/regressions в develop, включая #45 | Browser CONNECT по готовым endpoint |
| Official package/release | Package/README не получены; выпуск не готов | Official adapter, T01–21, one-command demo/video/release |

Проверки: Django 230 tests PASS, 2 ожидаемых skips; file-backed submissions 49/49; domain 68; sandbox unit 15; strict fixtures 9/common imports; check/migration drift/diff PASS. Final CI #44 4/4 SUCCESS на `2f67974` (37991078272), первый CI P1 FAIL сохранён в publication audit. Итоговый develop с #45: 18 files / 82 UI tests PASS с maxWorkers=1, TypeScript/Vite build PASS. До этого два default timeout FAIL записаны; assertions/timeouts не ослаблялись. File-backed P1 class PASS 2/2. Closeout сохраняет 145 base/source audits и не меняет production/tests; его CI повторяется до merge. Real Docker/browser/official/full acceptance в этой сессии не выполнялась.

## Следующие независимые срезы четырёх ролей

1. A1: PublicAccess/share/proxy; common failure port и runtime wiring/readiness отдельными небольшими PR. Резерв P1-01.1 invite concurrency stability, P1-02.6 frontend CI.
2. A2: #7 code уже в develop через #44 — доступны persisted MatchRun/config/gateway/workspace API, persistent ledger/finalization/promotion/effects. Readiness/ledger/commands cores интегрированы. Резерв: reset/pairings API, typed events/projector/SSE tests; текущий авторский P2-06.2 продолжается независимо.
3. A3: normalized import management и CAS fix #21 доступны независимо; worker snapshot/providers CONNECT относится к конкретным подпунктам. Leases/outboxes/adapters проверены. Container owner/claim fencing и immutable run snapshot описаны в contract requests.
4. A4: продолжать browser/API CONNECT по одному endpoint; bracket generate/read доступен после merge #7, server drafts #21 ещё ждёт исправления. Local editor recovery работает независимо.

WAITING относится к подпункту: в той же сессии брать следующий READY шаг своей зоны. Карточки авторов/старые аудиты — датированные snapshots; перед блокером fetch. Working MVP (R1) ещё требует API → run → queue → sandbox → ledger → promotion. [ROADMAP v3](../ROADMAP.md), [runtime handoffs](../docs/architecture/runtime-handoffs.md).

## Исторический checkpoint при разблокировании агента 3

Снимок 2026-10-09, Europe/Moscow. На старте проверки develop `13cd2d4` (#29); #25 отдельно MERGED `ed14416`; перед публикацией включён A4 #30 `8c6836b`, перед итоговым merge — A4 #31 `b9c25cb`. Main `e9fc0ef` остаётся bootstrap. PR #20 MERGED: sandbox/clock/score/catalog/admin guards в develop. Также MERGED frontend #22/#24/#27/#28/#29/#30/#31.

В `feature/agent-3-merge-unblock` обычными merge commits объединены проверенные #26 `435cef7` admin catalog, #15 `555ca0e` queue race fix и #23 `942b4f5` LocalJudge. До MERGED её integration PR эти три среза находятся в проверенной feature; после MERGED доступны в develop. Исходные feature refs, аудиты и frontend/карточка активного A4 сохранены. Не ждать ещё одного STATE PR после подтверждённого code merge. Аудит и конкретные следующие задачи.

Integration [PR #32](https://github.com/D0UP1G/FirsterChuv/pull/32) опубликован; первый head получил 4/4 CI PASS, после fresh #31 финальные checks повторяются. Publication checkpoint. Этот текст — checkpoint перед операцией; фактический MERGED/remote refs определяют доступность кода.

## Что есть и чего нет

| Компонент | Реализация / интеграция | Остаток до working MVP |
|---|---|---|
| User/common/auth/roles/CSRF | develop #2/#5 | Full browser/object/runtime security acceptance |
| CRUD/roster/seed/freeze | develop #8 | Played-history и browser acceptance |
| Invite backend | develop #12 | A4 реальный browser register/accept flow |
| CI/schemas/common ports | develop #17/#18/#19, 4 jobs pass | Required protection отсутствует; реальных providers ещё нет |
| Sandbox harness | develop #20; обновление task limits из #23 в текущей feature | Fresh image обязателен для нового run argv; ML/checker/worker/official full T18 |
| Pure clock/scoring | develop #20, #11 28d6cda/#13 19bbf88 | Persisted run/start/API/gateway/ledger/finalization/promotion |
| Normalized catalog | develop #20/#25; admin catalog #26 в текущей feature | Normalized import/status API, verified compiler/workspace HTTP/official adapter |
| Bracket ORM/API | #7 обновлён до 1a2b54a, fix опубликован; не включён в эту проверку A3 | Review нового lifecycle fix, потом full reset/pairing HTTP |
| Queue core | #15 555ca0e в текущей feature; SQLite race исправлен, 29 file-backed tests pass | Actual worker/provider/result+failure adapters, runtime CONNECT |
| Event store | #16 обновлён до 6eac91f; новая версия вне текущего A3 review | Проверить новый head; исторический B03 относится к 8340014; producers/access/snapshots/SSE CONNECT |
| Admin guards | develop #20, 8f5b762 | Pure guards; настоящие command store/effects/HTTP отсутствуют |
| LocalJudge | #23 942b4f5 в текущей feature; real Docker/synthetic bundle OK | Worker deployment/readiness, verified compiler, official checker protocol |
| Private drafts | #21 1706ecf OPEN: воспроизведён CAS busy→500 | P3-05.1 bounded retry/revision conflict/503 перед merge |
| Frontend | develop #22/#24/#27/#28/#29/#30/#31, UI P4-01–05 + regression tests | Текущий A4 browser/API CONNECT по endpoint, full acceptance |
| Official package/README | Не получены | Только adapter/final official acceptance WAITING_EXTERNAL |
| Full one-command demo/release | Не готовы | R1→R2→R3; main не релиз |

Текущая проверка: 150 backend tests PASS с 2 ожидаемыми skips после одного записанного P1 concurrency FAIL; отдельно 29 file-backed submissions, 9 strict fixtures/common import, 36 domain и 15 sandbox unit PASS; migration drift нет. Fresh frontend #31: 16 files / 64 tests и TypeScript/Vite build PASS. На отдельном свежем image #23: 5 actual sandbox smoke, task limit 100 ms/64 MiB и 1 real LocalJudge smoke PASS. Production image/tag и compiler readiness не менялись; официальный/полный hostile/browser T01–21 acceptance не закрыт. GitHub CI и publication записаны в publication checkpoint.

## Следующая работа одновременно

1. A1: P1-03 public/share access и proxy/logging; резерв P1-04 infrastructure + P1-02.5 additive failure handoff. Прежний explicit stop отдельной сессии учитывается, документ не запускает её автоматически.
2. A2: P2-02.1 fix #7, P2-06.1 fix #16; затем настоящий MatchRun/API/gateway/ledger, сохраняя готовые pure cores. Резерв command store/actions/projector.
3. A3: P3-02.2 normalized import management (merge-блокер #25 снят), P3-04.2 actual worker; резерв P3-05.1 исправление CAS race #21. Только production ports/version binding подпункт WAITING_CONNECT и P3-06 package WAITING_EXTERNAL.
4. A4: продолжать активный browser/API CONNECT; UI срезы уже опубликованы и интегрированы. Catalog #26 совместим с текущим frontend paginated request; подключение проверить по одному endpoint после merge. Карточка и исходники A4 этой проверкой не менялись.

При зависимости WAITING получает подпункт, исполнитель продолжает следующий READY шаг в той же сессии. [ROADMAP v3](../ROADMAP.md), ревизия всех PR, [runtime handoffs](../docs/architecture/runtime-handoffs.md). Fetch актуального develop перед стартом; авторские feature refs/старые аудиты сохранены, shared app/CI registrations не заменять старыми полными копиями.


Combined #63/#64/#65 frontend final rerun:18 files/84 tests PASS(28.53s), typecheck/lint/build PASS;5 прежних lint warnings и612.88kB chunk warning. Final integrity:170 base context/audits files +5 incoming source audits exact, all3 source heads ancestors; unsafe53/57–59 latest heads excluded; backend/config/CI/scripts/contracts diff zero. Полный browser/hostile/official M0 NOT_RUN.
