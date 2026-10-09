# Агент 3: sandbox, задачи, код

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

## Текущая сессия: P3-04.2 · submission worker/recovery

- ID задачи: `P3-04.2`; статус: `IN_PROGRESS`.
- Ветка: `feature/submission-worker`; база `origin/develop`: `15e3edf4fdfe7910f0984f97f26eee8589d5319b`.
- Зависимость: PR #15 (`feature/submission-queue-core`, head `555ca0ee692fdc4472857e3f2350c01819224f1e`) содержит queue core и P3-04.1. Его код будет включён только в собственную локальную feature-ветку; исходную ветку/worktree не менять.
- Планируемые пути: `backend/apps/submissions/worker.py`, management command для запуска worker, worker/recovery tests, `backend/apps/submissions/README.md`, эта карточка и отдельный audit. Общие config/Compose и чужие paths не менять без необходимости/координации.
- Объём по ROADMAP v3: durable claim/lease loop, retry/outbox delivery, restart recovery и уборка только собственных orphan jobs; реальные ports остаются fail-closed, test doubles только в tests.
- Основание: требования J04/E03 и T09/T14/T19/T20; runtime CONNECT с A2 и LocalJudge отдельно фиксировать, не подменять fake verdict.
- Стартовый аудит: [`2026-10-09T213942+0300-agent-3-P3-04.2-start.md`](../audits/2026-10-09T213942+0300-agent-3-P3-04.2-start.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
