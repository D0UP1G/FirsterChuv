# Агент 3: sandbox, задачи, код

## Текущая сессия

- P3-02.3 — `IN_REVIEW`; ветка `feature/problem-management-api`, база `origin/develop` SHA `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`.
- До завершения сверены `AGENTS.md`, PROJECT/STATE/карточка, ROADMAP v3, требования P01/P02/E02/S01, кейс (стр. 5–7), parallel contracts, архитектурные решения и аудиты P3-02.
- Реализован P3-02.3: typed rejection для private artifact language IDs и invalid-manifest tests. Локально пройдены backend 106/106, app tests 8/8, Django/migration checks, contracts/import boundary/domain/sandbox suites, compileall и diff check.
- Аудит: [2026-10-09T210104+0300-agent-3-P3-02.3-artifact-language-types.md](../audits/2026-10-09T210104+0300-agent-3-P3-02.3-artifact-language-types.md). Следующий шаг: feature PR в `develop`, дождаться PR CI/review; не сливать самостоятельно.

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
