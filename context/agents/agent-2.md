# Агент 2: сетка и live backend

## Назначение координатора 2026-10-10T01:11:53+03:00: Настоящий матч и результат

- Источник: прямое поручение команды перераспределить оставшийся MVP и создать нового frontend owner. Это текущее назначение; прежние author checkpoints ниже сохранены как история.
- Статус назначения: READY; фактический IN_PROGRESS выставляет владелец при начале edits в своём изолированном checkout.
- Первое действие: исправить проверенные #57–59 (0073fbd/1f3fae5/7465a9c): SQLite read→write/full bounded retry, frozen participants original run, exact-command replay; file-backed tests. PR только в develop, после #50 база доступна без переписывания веток. Persistence cores уже написаны, не повторять. Затем P2-03 get/config/start/ready + production gateway/snapshot, по одному endpoint.
- Независимый резерв: HTTP serializers/permissions для config/start/ready, P2-04 durable failure sink/finalization/promotion, P2-05 API/replacement. #58 accepted/result и #59 actions исправлять по конкретным замечаниям [review](../../docs/reviews/2026-10-10-mvp-readiness.md), не реализовывать повторно.
- Владение: competition/models/services/migrations/tests; events переданы A4.
- Fresh develop после подтверждённого merge integration feature; #21 CAS исправлен, #50 pairings/reset проверяется вместе, #53 не integrated/нужен fix. Готовые cores не повторять.
- [ROADMAP v4](../../ROADMAP.md), [принятые границы](../contracts/2026-10-10-mvp-boundaries.md). При WAITING одного CONNECT в той же сессии брать следующий READY пункт. Explicit user stop важнее назначения; Git сам не переключает соседний checkout.


Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Коррекция аудита P2-03: короткий ref `6320b4b` раскрывается в `6320b4bb75a0dbc5284946cb0161cb1842d15847`; две исходные записи не переписывались. См. [коррекционный аудит](../audits/2026-10-10T002548+0300-agent-2-P2-03-base-sha-correction.md).

- Проверены/integration feature: pure clock #11 28d6cda и score #13 19bbf88, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- Первое READY P2-02.1: fix #7 1952244 generate/reset/pairings только draft/scheduled, SQLite transactional lifecycle guard + regression. Ordinary registration/rank/import уже готовы. Затем merge #7 и P2-02.2 HTTP/idempotency/reason/full pairings.
- Второй короткий READY P2-06.1: fix #16 8340014 SOLVED/lastVerdict WA/CE roundtrip без ослабления public whitelist.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score повторно.
- Резерв во время CONNECT: P2-05 pure guards 8f5b762 включены в integration feature → command store/effects, P2-06 projector/snapshot/SSE tests. Не ждать живой judge/importer/frontend для своих domain/DB/API slices.
- Пути: competition/events, свои migrations/tests; common wiring кратким CONNECT. При sync сохранить all app registrations, CI и чужие audits.
- Runtime без реального catalog/access provider отказывает. Full T05–11/T16–17/T19–20 не пройдены; own cards/audits фиксируют implementation/integration/acceptance отдельно.
- P2-06.1 correction опубликована в PR #16 на `a0b1dcc`; checks прошли, PR OPEN/CLEAN. Изменение пока не интегрировано в develop.
- Статус: `IN_PROGRESS` — P2-03 pure readiness/start policy для `manual` и `both_ready`; ветка `feature/match-ready-gate`, база синхронизирована merge из `origin/develop` `6320b4bb75a0dbc5284946cb0161cb1842d15847`.
- Пути текущего независимого среза: `backend/apps/competition/domain/start_policy.py`, тесты в `backend/apps/competition/tests/test_clock.py`, эта карточка и audit. Pure clock #11 повторно не реализуется.
- Граница: закрыть идемпотентную ready policy и auto-start обоих игроков для `both_ready`; не добавлять persistence/API. `Match`/`MatchRun` модели принадлежат незавершённому PR #7, поэтому ORM wiring продолжается после его интеграции.
- Реализация: [P2-03 readiness gate, PR #34](https://github.com/D0UP1G/FirsterChuv/pull/34), latest head `fba94a28aabbfd773e025e9ee626dc11b8326994`, OPEN/CLEAN; четыре CI check прошли.
- Аудиты сессии и публикации: [readiness gate](../audits/2026-10-09T231559+0300-agent-2-P2-03-readiness-gate.md), [PR #34 publication](../audits/2026-10-09T231837+0300-agent-2-P2-03-readiness-publication.md), [зелёные checks](../audits/2026-10-09T232130+0300-agent-2-P2-03-readiness-checks.md).
- Свежая GitHub сверка: PR #7 head `1a2b54a` OPEN/DIRTY; PR #16 head `a0b1dcc` OPEN/DIRTY; integration PR #32 MERGED и develop на `6320b4b`. MatchRun persistence остаётся WAITING_CONNECT на PR #7.
- Следующий независимый срез Agent 2: P2-04 accepted-ledger/result domain core в отдельной `feature/*` ветке; P2-03 persistence/API продолжить после интеграции #7.

## Текущий checkpoint

- P2-02.1 lifecycle fix PR #7 опубликован на head `1a2b54a`, OPEN/DIRTY; не менять чужую feature-ветку.
- P2-06.1 опубликован в PR #16 на `a0b1dcc`, OPEN/DIRTY.
- P2-03 pure readiness/start slice опубликован в PR #34; head `730edd827236a42d98b3efe85551f6277a1d5d97`, OPEN/CLEAN, четыре checks SUCCESS.
- P2-03 persisted MatchRun/config/API — `WAITING_CONNECT` на #7; работу продолжать по следующей независимой очереди.
- Текущая база обновлена обычным fast-forward до `origin/develop` `56c20eb3323c892d7f2fa9aadc6beb905548f677` (PR #35 MERGED).
- Статус: `IN_REVIEW` — P2-04 accepted-ledger/result pure core опубликован как [PR #38](https://github.com/D0UP1G/FirsterChuv/pull/38), текущая локальная ветка синхронизирована с develop до `7e2cb466676e13f6ecc5a90eba858f3655eed570`; локальный head `4bb3f267b2f8b42a200dc8a4d9f48bbeba15be86` ожидает публикации sync merge.
- Планируемые пути: `backend/apps/competition/domain/result_ledger.py`, tests в существующем `backend/apps/competition/tests/test_scoring.py` (suite уже запускает этот файл), эта карточка и audit. Shared suite runner/API/ORM/events не менять в этом срезе.
- Подзадача: immutable `AttemptReceipt` registry, duplicate/conflicting/out-of-order `ResultReceipt`, stale/superseded run без score mutation, pending-aware финализация по runtime handoff. Полный P2-04 дополнительно требует persistence, infrastructure-failure port/outbox и atomic downstream/event transition.
- PR #7 head `1a2b54a12d2070c39c1c47ef67d37396c345a064` и PR #16 head `a0b1dcc682fac8f2fb1285743a62758310feeaa3` остаются OPEN/DIRTY; чужие ветки не менялись.
- Начальный audit P2-04: [accepted ledger core](../audits/2026-10-09T232844+0300-agent-2-P2-04-ledger-core.md).
- Publication audit P2-04: [PR #38](../audits/2026-10-09T233257+0300-agent-2-P2-04-ledger-publication.md).
- Develop sync P2-04: [fresh-ref merge](../audits/2026-10-09T233507+0300-agent-2-P2-04-develop-sync.md).
- Следующий независимый срез: P2-05 persisted command/effects core, отдельная ветка от свежего develop; не смешивать с #38.

## Текущий checkpoint

- P2-03 pure readiness/start PR #34: head `730edd827236a42d98b3efe85551f6277a1d5d97`, OPEN/CLEAN, 4/4 checks SUCCESS; persisted run/API ждёт #7.
- P2-04 pure ledger/result PR #38: head `92af1d666f539b5fdc9e694444e389eb373692a1`, OPEN/CLEAN, четыре CI checks SUCCESS. Persistence/technical-failure/outbox не готовы.
- P2-02.1 PR #7 head `1a2b54a12d2070c39c1c47ef67d37396c345a064`, OPEN/DIRTY; P2-06.1 PR #16 head `a0b1dcc682fac8f2fb1285743a62758310feeaa3`, OPEN/DIRTY.
- Статус: `IN_PROGRESS` — P2-05 idempotent admin-command receipt core; ветка `feature/match-admin-command-store`, база синхронизирована до `origin/develop` `25a82c092236d98275f897d624452b24bd501883`.
- Пути: `backend/apps/competition/domain/command_store.py`, tests в `backend/apps/competition/tests/test_admin_actions.py`, эта карточка и новый audit. Не менять persisted models/API/shared wiring.
- Подзадача: строгая fingerprint для intent (match/key/actor/action/reason/arguments), exact retry возвращает первоначальный plan, тот же key с другим payload — conflict; чистый helper не заявляется как durable production store.
- Audit P2-05: [command receipt core](../audits/2026-10-09T234217+0300-agent-2-P2-05-command-store.md).
- Реализация опубликована в [PR #41](https://github.com/D0UP1G/FirsterChuv/pull/41), head `5c5740a34fb5cc498167cbb44cc8596741332b89`, OPEN; при publication: contracts/sandbox-unit выполнялись, backend/domain были в очереди.
- Publication audit: [PR #41](../audits/2026-10-09T234419+0300-agent-2-P2-05-command-publication.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).

## Авторский checkpoint синхронизации #7, 2026-10-10

- Source head f3001505fb70e9e810cd5da774a9a6dda996240f: обычный merge develop fb9edb3 в feature/bracket-runtime; 25 bracket/175 backend (2 skips), check/drift PASS у автора.
- [Оригинальный sync audit](../audits/2026-10-10T000400+0300-agent-2-P2-02-1-develop-sync.md) сохранён без изменений. Исторический source card доступен в ancestry f300150.
- Автор продолжает независимый P2-06.2 в собственной event feature во время review #7. Прежние readiness/ledger/command checkpoints этой карточки сохранены.
- Код P2-01/P2-02.1 уже в develop через MERGED #44 (03a4636); текущий coordinator closeout объединяет поздний source sync и audit. После его MERGED обновить свою ветку из fresh develop и продолжить готовый подпункт.

## P2-02.2 current completion

- Implemented manual first-round pairings and bracket reset HTTP commands with frozen participant mapping, actor/reason validation, CSRF/admin protection, idempotency replay, conflicting-intent `409`, lifecycle guards, atomic receipt persistence, and SQLite lock retry.
- Added migration `competition.0002_bracketcommandreceipt`, API/domain regression coverage, and same-key concurrency coverage.
- Verification on this branch: targeted bracket API plus persistence tests `23 passed`; same-key concurrency test `1 passed`; full backend suite `237 passed, 2 skipped`; Django system check clean; migration drift check clean; `git diff --check` clean.
- Branch includes fresh `origin/develop` sync at merge commit `7815160`; P2-02.2 implementation remains ready to publish as a follow-up PR after merged PR #7.

## Current publication closeout (2026-10-10)

- P2-02.2 manual pairing/reset API is published in [PR #50](https://github.com/D0UP1G/FirsterChuv/pull/50).
- P2-03 base-SHA audit correction is published in [PR #51](https://github.com/D0UP1G/FirsterChuv/pull/51).
- P1-02.6 frontend CI is published in [PR #52](https://github.com/D0UP1G/FirsterChuv/pull/52).
- P2-06.2 durable public snapshots is published in [PR #53](https://github.com/D0UP1G/FirsterChuv/pull/53), latest head `fd79038`.
- P3-05.1 draft CAS retry is already included in open [PR #21](https://github.com/D0UP1G/FirsterChuv/pull/21), latest head `620f58e`, with four successful CI checks.
- Next independent implementation remains P2-03 persisted runtime; P2-06.3 public HTTP/SSE stays gated on PublicAccessV1.
