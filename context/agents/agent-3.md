# Агент 3: sandbox, задачи, код

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).

## Срез P3-05, начатый до перепланирования v3

- Статус: `IN_PROGRESS` до создания feature PR; ветка `feature/private-drafts-history`.
- Начальная база: `cad34ea4ddf1171779dc22139f2e1533160b5015`; синхронизирована с `origin/develop=1f60aa9` коммитом `4b6030d887bc41f3eb01d37370a3c9b36651760a`. Текущий fetch `origin/develop=ae0846b22953527d74835febf963169e2093238d` входит в выполняемый merge.
- Реализация: код/audit commit `fbdb01c`; private storage/history, CAS, common `WorkspaceContext` actions, active participant/CSRF/IDOR guard, своя миграция. Без настоящего A2 provider runtime fail-closed с 503.
- Проверки на locked dependencies: draft tests 13/13; backend 61/61; check/migration drift/contracts/common imports/compile passed; domain script корректно no-op, suites в ref отсутствуют.
- `context/contracts/agent-3-private-draft-get.md` — `PROPOSED`: уточнить GET run selector и поведение отсутствующей записи. Browser T15 и полная T20 приёмка не выполнены; P4-04 остаётся CONNECT для autosave/history UI. `context/STATE.md` агентом 3 не менялся.
- Следующий шаг: синхронизировать merge `ae0846b`, опубликовать отдельный P3-05 PR в `develop`, обновить карточку/аудит публикации; затем продолжить по приоритету ROADMAP v3 (сначала P3-04.1, затем P3-03).
