# Агент 2: сетка и live backend

Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Статус: `IN_REVIEW` — P2-02.1 lifecycle fix обновлён из latest `origin/develop` `fb9edb3d39dba22297febcb0523e389cef67ff02`; PR #7 остаётся собственным feature PR.
- Исполнитель: Codex в роли агента 2.
- Текущая ветка/база: `feature/bracket-runtime`; PR #7 продолжен от сохранённого HEAD `1952244`; последняя синхронизация — merge с `origin/develop` `fb9edb3d39dba22297febcb0523e389cef67ff02`.
- Scope: status guard `DRAFT`/`SCHEDULED` для generate/reset/full-pairings services до любых reads/existing-bracket return/freeze; SQLite conditional write сериализует решение с archive/start; отказ не меняет roster freeze или сетку.
- План-проверки: persistence regression для трёх mutators, HTTP regression для имеющегося generate endpoint, проверка первого SQL write до чтений; файлы: `backend/apps/competition/services.py`, собственные bracket tests, эта карточка и отдельный audit.
- Граница: без новых HTTP endpoints/idempotency/full-pairings DTO P2-02.2; чужие tournament/common/app paths не менять. После review P2-02.1 следующий независимый пункт — P2-06.1.
- Audit текущего среза: [P2-02.1 lifecycle](../audits/2026-10-09T223736+0300-agent-2-P2-02-1-bracket-lifecycle.md).
- Последняя синхронизация PR #7 разрешила только `common/api_urls.py` и `config/settings.py`: сохранены competition routes/config вместе с актуальными problems/submissions/judge registrations; 25 bracket tests, backend 175 tests (2 skips), Django check и migration drift check прошли. Подробности — [sync audit](../audits/2026-10-10T000400+0300-agent-2-P2-02-1-develop-sync.md).
- Следующий зависимый срез P2-02.2 остаётся после review/merge #7; пока он ожидает, Agent 2 продолжает независимый P2-06.2 в своей event feature-ветке.

- Проверены/integration feature: pure clock #11 28d6cda и score #13 19bbf88, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- Первое READY P2-02.1: fix #7 1952244 generate/reset/pairings только draft/scheduled, SQLite transactional lifecycle guard + regression. Ordinary registration/rank/import уже готовы. Затем merge #7 и P2-02.2 HTTP/idempotency/reason/full pairings.
- Второй короткий READY P2-06.1: fix #16 8340014 SOLVED/lastVerdict WA/CE roundtrip без ослабления public whitelist.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score повторно.
- Резерв во время CONNECT: P2-05 pure guards 8f5b762 включены в integration feature → command store/effects, P2-06 projector/snapshot/SSE tests. Не ждать живой judge/importer/frontend для своих domain/DB/API slices.
- Пути: competition/events, свои migrations/tests; common wiring кратким CONNECT. При sync сохранить all app registrations, CI и чужие audits.
- Runtime без реального catalog/access provider отказывает. Full T05–11/T16–17/T19–20 не пройдены; own cards/audits фиксируют implementation/integration/acceptance отдельно.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
