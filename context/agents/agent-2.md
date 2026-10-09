# Агент 2: сетка и live backend

Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Проверены/integration feature: pure clock #11 28d6cda и score #13 19bbf88, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- Первое READY P2-02.1: fix #7 1952244 generate/reset/pairings только draft/scheduled, SQLite transactional lifecycle guard + regression. Ordinary registration/rank/import уже готовы. Затем merge #7 и P2-02.2 HTTP/idempotency/reason/full pairings.
- Второй короткий READY P2-06.1: fix #16 8340014 SOLVED/lastVerdict WA/CE roundtrip без ослабления public whitelist.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score повторно.
- Резерв во время CONNECT: P2-05 pure guards 8f5b762 включены в integration feature → command store/effects, P2-06 projector/snapshot/SSE tests. Не ждать живой judge/importer/frontend для своих domain/DB/API slices.
- Пути: competition/events, свои migrations/tests; common wiring кратким CONNECT. При sync сохранить all app registrations, CI и чужие audits.
- Runtime без реального catalog/access provider отказывает. Full T05–11/T16–17/T19–20 не пройдены; own cards/audits фиксируют implementation/integration/acceptance отдельно.
- P2-06.1 correction опубликована в PR #16 на `a0b1dcc`; checks прошли, PR OPEN/CLEAN. Изменение пока не интегрировано в develop.
- Статус: `IN_PROGRESS` — P2-03 pure readiness/start policy для `manual` и `both_ready`; ветка `feature/match-ready-gate`, база синхронизирована merge из `origin/develop` `6320b4b51ef2e053c1e9ce81349d4480be85f9d4`.
- Пути текущего независимого среза: `backend/apps/competition/domain/start_policy.py`, тесты в `backend/apps/competition/tests/test_clock.py`, эта карточка и audit. Pure clock #11 повторно не реализуется.
- Граница: закрыть идемпотентную ready policy и auto-start обоих игроков для `both_ready`; не добавлять persistence/API. `Match`/`MatchRun` модели принадлежат незавершённому PR #7, поэтому ORM wiring продолжается после его интеграции.
- Аудит сессии: [P2-03 readiness gate](../audits/2026-10-09T231559+0300-agent-2-P2-03-readiness-gate.md). Реализация/локальные проверки зафиксированы; публикация feature PR ожидает завершения коммита в этой ветке.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
