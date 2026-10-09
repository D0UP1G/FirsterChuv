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

- P2-03 pure readiness/start PR #34: head `730edd827236a42d98b3efe85551f6277a1d5d97`, OPEN/CLEAN, 4/4 checks SUCCESS; persisted run/API ждёт #7.
- P2-04 pure ledger/result PR #38: head `92af1d666f539b5fdc9e694444e389eb373692a1`, OPEN/CLEAN, четыре CI checks SUCCESS. Persistence/technical-failure/outbox не готовы.
- P2-02.1 PR #7 head `1a2b54a12d2070c39c1c47ef67d37396c345a064`, OPEN/DIRTY; P2-06.1 PR #16 head `a0b1dcc682fac8f2fb1285743a62758310feeaa3`, OPEN/DIRTY.
- Статус: `IN_PROGRESS` — P2-05 idempotent admin-command receipt core; ветка `feature/match-admin-command-store`, база синхронизирована до `origin/develop` `25a82c092236d98275f897d624452b24bd501883`.
- Пути: `backend/apps/competition/domain/command_store.py`, tests в `backend/apps/competition/tests/test_admin_actions.py`, эта карточка и новый audit. Не менять persisted models/API/shared wiring.
- Подзадача: строгая fingerprint для intent (match/key/actor/action/reason/arguments), exact retry возвращает первоначальный plan, тот же key с другим payload — conflict; чистый helper не заявляется как durable production store.
- Audit P2-05: [command receipt core](../audits/2026-10-09T234217+0300-agent-2-P2-05-command-store.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
