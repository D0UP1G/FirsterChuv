# Агент 2: сетка и live backend

Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Проверены/integration feature: pure clock #11 `28d6cda` и score #13 `19bbf88`, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- P2-01/P2-02.1: bracket runtime/lifecycle guard отправлены в PR #7; не переписывать эти изменения в event ветке.
- P2-03 pure readiness PR #34: head `730edd827236a42d98b3efe85551f6277a1d5d97`, OPEN/CLEAN, 4/4 checks SUCCESS.
- P2-04 pure ledger PR #38: head `92af1d666f539b5fdc9e694444e389eb373692a1`, OPEN/CLEAN, 4/4 checks SUCCESS.
- P2-05 command receipt PR #41: head `c8b80430707e51faa83619a0ccf41e749ac51b9e`, OPEN/CLEAN, 4/4 checks SUCCESS.
- P2-06.1 correction опубликована в PR #16; remote head `a0b1dcc682fac8f2fb1285743a62758310feeaa3`, checks 4/4 SUCCESS, merge status DIRTY до sync. Локальная feature синхронизирована с актуальным `origin/develop` `623a17912efa55fd00550565fdfc0ac06d41607a` обычным merge.
- Статус: `IN_PROGRESS` — P2-06.2 pure score→event producer; после sync base `623a17912efa55fd00550565fdfc0ac06d41607a`.
- Планируемые пути: новый `backend/apps/events/projectors.py`, `backend/apps/events/tests.py`, эта карточка и audit. Shared contracts/ORM/HTTP/SSE не менять в текущем срезе.
- Граница: проецировать существующий `MatchScore` в единственный полностью описанный v1 `score.changed` payload, затем повторно валидировать строгим public allowlist. Прочие realtime event schemas и coherent public snapshot требуют своих полных payload/current MatchRun sources; не угадывать их по summary-таблице.

### P2-06.2 snapshot completion

- Durable `MatchSnapshot` persistence is implemented in PR #53 on `feature/public-events-sse` at head `c0409de`.
- The snapshot stores public-safe payload, run UUID, and monotonic `last_event_id`; stale cursor writes are ignored and reads return the validated public envelope.
- Migration and regression coverage are included. Local Django execution is unavailable because dependencies are not installed; CI is the acceptance gate.
- Next slice: P2-06.3 public HTTP/SSE transport with cursor/resync and heartbeat.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score cores повторно.
- Резерв во время CONNECT: P2-05 pure guards `8f5b762` включены в integration feature → command store/effects; P2-06 projector/snapshot/SSE tests остаются следующими срезами. Не ждать живого judge/importer/frontend для независимых domain/DB/API slices.
- Пути общей интеграции менять только при необходимости, сохраняя все app registrations, CI и чужие audits. Runtime без реального catalog/access provider отказывает.
- Источники: `ROADMAP.md` P2-06, `docs/architecture/realtime.md`, `docs/architecture/parallel-contracts.md`, `contracts/mvp-v1/score-event.json`, `contracts/mvp-v1/public-match.json`; V01–03, S02, T16/T17/T20.
- Audit исходного event store: [P2-06.1](../audits/2026-10-09T173634+0300-agent-2-P2-06-1-event-store.md). Новый аудит фиксирует этот corrective slice.
- Локальная проверка correction: event app 11 tests, весь backend 117 tests, domain suites 36 tests, 9 контрактных fixtures и migration drift check прошли.
- Audit correction: [SOLVED/lastVerdict roundtrip](../audits/2026-10-09T225633+0300-agent-2-P2-06-1-solved-verdict-roundtrip.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
