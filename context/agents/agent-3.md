# Агент 3: sandbox, задачи, код

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).

## Текущая сессия: P3-04.1 / admission race

- ID: `P3-04.1`; статус: `IN_PROGRESS`.
- Ветка PR: `feature/submission-queue-core`; исходный HEAD `7d76d0b1bf85c7a707de72ebaa1cb8364b4c9207`; исходная база `cad34ea4ddf1171779dc22139f2e1533160b5015`; `origin/develop=ae0846b22953527d74835febf963169e2093238d` синхронизирован merge-коммитом `c2a653e05da96802ddc58104f0c789eea32640d6`.
- Изменяемые пути: `backend/apps/submissions/services.py`, `errors.py`, `views.py`, `README.md`, `test_settings.py`, `tests/`, эта карточка и новый аудит. При sync сохранены `SubmissionsConfig` и `ProblemsConfig` в `INSTALLED_APPS`.
- Acceptance: только SQLite busy/locked вызывает bounded retry всей admission transaction; исчерпание преобразуется в retryable 503; сохраняется исходный `received_at`; file-backed concurrent TransactionTestCase покрывает разные/одинаковые idempotency keys, capacity и rollback ledger/event без 500.
- Реализация проверена: максимум 3 попытки всего, retry только SQLite `BUSY/LOCKED`, после исчерпания `503 queue_busy`; `received_at` вычисляется до цикла. File-backed submissions suite `29/29`; полный backend `134` tests, `OK`, один ожидаемый skip для file-backed-specific assertion при стандартной SQLite in-memory конфигурации.
- PR #15 и его worktree — существующие артефакты этого agent-3 checkout; не менять чужие ветки/worktrees. Общий `context/STATE.md` не редактировать.
- Следующий шаг: включить код и audit в commit, fast-forward push в существующую feature-ветку и обновить описание PR #15 без rebase/force push; затем начать P3-03 в отдельной feature-ветке от актуального `origin/develop`.
