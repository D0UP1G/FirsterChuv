# Агент 2: сетка и live backend

Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Проверены/integration feature: pure clock #11 28d6cda и score #13 19bbf88, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- Первое READY P2-02.1: fix #7 1952244 generate/reset/pairings только draft/scheduled, SQLite transactional lifecycle guard + regression. Ordinary registration/rank/import уже готовы. Затем merge #7 и P2-02.2 HTTP/idempotency/reason/full pairings.
- Второй короткий READY P2-06.1: fix #16 8340014 SOLVED/lastVerdict WA/CE roundtrip без ослабления public whitelist.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score повторно.
- Резерв во время CONNECT: P2-05 pure guards 8f5b762 включены в integration feature → command store/effects, P2-06 projector/snapshot/SSE tests. Не ждать живой judge/importer/frontend для своих domain/DB/API slices.
- Пути: competition/events, свои migrations/tests; common wiring кратким CONNECT. При sync сохранить all app registrations, CI и чужие audits.
- Runtime без реального catalog/access provider отказывает. Full T05–11/T16–17/T19–20 не пройдены; own cards/audits фиксируют implementation/integration/acceptance отдельно.

## Текущий checkpoint

- P2-02.1 lifecycle fix PR #7 опубликован на head `1a2b54a`, OPEN/DIRTY; не менять чужую feature-ветку.
- P2-06.1 опубликован в PR #16 на `a0b1dcc`, OPEN/DIRTY.
- P2-03 pure readiness/start slice опубликован в PR #34; head `730edd827236a42d98b3efe85551f6277a1d5d97`, OPEN/CLEAN, четыре checks SUCCESS.
- P2-03 persisted MatchRun/config/API — `WAITING_CONNECT` на #7; работу продолжать по следующей независимой очереди.
- Текущая база обновлена обычным fast-forward до `origin/develop` `56c20eb3323c892d7f2fa9aadc6beb905548f677` (PR #35 MERGED).
- Статус: `IN_PROGRESS` — P2-04 accepted-ledger/result pure core; ветка `feature/match-ledger-results`, база `origin/develop` `56c20eb3323c892d7f2fa9aadc6beb905548f677`.
- Планируемые пути: `backend/apps/competition/domain/result_ledger.py`, tests в существующем `backend/apps/competition/tests/test_scoring.py` (suite уже запускает этот файл), эта карточка и audit. Shared suite runner/API/ORM/events не менять в этом срезе.
- Подзадача: immutable `AttemptReceipt` registry, duplicate/conflicting/out-of-order `ResultReceipt`, stale/superseded run без score mutation, pending-aware финализация по runtime handoff. Полный P2-04 дополнительно требует persistence, infrastructure-failure port/outbox и atomic downstream/event transition.
- PR #7 head `1a2b54a12d2070c39c1c47ef67d37396c345a064` и PR #16 head `a0b1dcc682fac8f2fb1285743a62758310feeaa3` остаются OPEN/DIRTY; чужие ветки не менялись.
- Начальный audit P2-04: [accepted ledger core](../audits/2026-10-09T232844+0300-agent-2-P2-04-ledger-core.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
