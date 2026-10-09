# Агент 3: sandbox, задачи, код

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- P3-04.1 #15 реализован в `a6d3674`: busy/locked → bounded whole-transaction retry/503, исходный `received_at`, file-backed concurrent keys/rollback tests; PR #15 обновлён и ждёт CI/review.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

## Текущая сессия: P3-04.2 · submission worker/recovery

- ID задачи: `P3-04.2`; статус: `IN_PROGRESS` (реализация и локальная проверка завершены; публикация ждёт интеграции PR #15).
- Ветка: `feature/submission-worker`; база `origin/develop`: `15e3edf4fdfe7910f0984f97f26eee8589d5319b`.
- Зависимость: PR #15 (`feature/submission-queue-core`, head `555ca0ee692fdc4472857e3f2350c01819224f1e`) остаётся OPEN/CLEAN, четыре CI jobs PASS. Queue core включён merge commit `cae2d74` только в эту собственную feature-ветку; исходную ветку/worktree не менять.
- Изменены только `backend/apps/submissions/{worker.py,factory.py,README.md}`, собственные management command/tests, эта карточка и audit. Общие config/Compose/contracts и чужие paths не менялись.
- Реализованы durable loop с приоритетом due outbox, worker/executor/result sink fail-closed factory, heartbeat ограниченного claim lease, stale-result guard, infra retry без verdict, command `run_judge_worker` с bounded CLI options, recovery очереди/outbox при повторных циклах.
- Основание: J04/E03 и частичные серверные сценарии T09/T14/T19/T20; runtime snapshot/adapters/failure sink P3-04.3–4 и реальный LocalJudge остаются отдельной работой. В этой задаче нет sandbox process registry, поэтому cleanup ограничен durable DB lease recovery.
- Проверки этой ревизии: submissions suite 41/41 PASS на файловой SQLite; system checks PASS; migration drift отсутствует; compileall и `git diff --check` PASS; command обнаруживается и без factory отказывает закрыто.
- Аудит старта: [`2026-10-09T213942+0300-agent-3-P3-04.2-start.md`](../audits/2026-10-09T213942+0300-agent-3-P3-04.2-start.md). Аудит реализации: [`2026-10-09T214617+0300-agent-3-P3-04.2-worker.md`](../audits/2026-10-09T214617+0300-agent-3-P3-04.2-worker.md).
- Следующий шаг: дождаться merge PR #15 в `develop`; затем обновить эту ветку обычным `git merge origin/develop`, проверить собственный diff и опубликовать PR строго в `develop`. До публикации PR #15 не создавать дублирующий stacked PR.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).

## Текущая сессия: P3-04.1 / admission race

- ID: `P3-04.1`; статус: `IN_REVIEW`.
- Ветка PR: `feature/submission-queue-core`; исходный HEAD `7d76d0b1bf85c7a707de72ebaa1cb8364b4c9207`; исходная база `cad34ea4ddf1171779dc22139f2e1533160b5015`; `origin/develop=ae0846b` синхронизирован merge `c2a653e`, затем `origin/develop=f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (#22) синхронизирован merge `6c1ccbf37d9acbaf482b696240a54b9c903ec2e5`.
- PR [#15](https://github.com/D0UP1G/FirsterChuv/pull/15): base `develop`, remote head `6c1ccbf` на момент публикации, состояние OPEN; после sync CI запущены, четыре GitHub jobs ещё `pending`. Кодовый fix — `a6d36745698fa60eaf2ee0fb17588009bf0d99a4`.
- Изменяемые пути: `backend/apps/submissions/services.py`, `errors.py`, `views.py`, `README.md`, `test_settings.py`, `tests/`, эта карточка и новый аудит. При sync сохранены `SubmissionsConfig` и `ProblemsConfig` в `INSTALLED_APPS`.
- Acceptance: только SQLite busy/locked вызывает bounded retry всей admission transaction; исчерпание преобразуется в retryable 503; сохраняется исходный `received_at`; file-backed concurrent TransactionTestCase покрывает разные/одинаковые idempotency keys, capacity и rollback ledger/event без 500.
- Реализация проверена: максимум 3 попытки всего, retry только SQLite `BUSY/LOCKED`, после исчерпания `503 queue_busy`; `received_at` вычисляется до цикла. File-backed submissions suite `29/29`; полный backend `134` tests, `OK`, один ожидаемый skip для file-backed probe при стандартной SQLite in-memory конфигурации.
- PR #15 и его worktree — существующие артефакты этого agent-3 checkout; не менять чужие ветки/worktrees. Общий `context/STATE.md` не редактировать.
- Publication audit: `context/audits/2026-10-09T203941+0300-agent-3-P3-04.1-publication.md`. Предыдущий head `a6d3674` имел четыре зелёных GitHub CI jobs; на обновлённом head после sync #22 надо дождаться их повторного результата/review.
- Следующий шаг: дождаться checks/review PR #15, не выполнять merge самостоятельно; затем продолжить P3-03 в отдельной feature-ветке от актуального `origin/develop`.
