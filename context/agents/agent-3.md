# Агент 3: sandbox, задачи, код

## Текущая сессия

### Снимок P3-02.3 до подтверждённого merge #25

- P3-02.3 — `IN_REVIEW`; ветка `feature/problem-management-api`, база `origin/develop` SHA `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`.
- До завершения сверены `AGENTS.md`, PROJECT/STATE/карточка, ROADMAP v3, требования P01/P02/E02/S01, кейс (стр. 5–7), parallel contracts, архитектурные решения и аудиты P3-02.
- Реализован P3-02.3: typed rejection для private artifact language IDs и invalid-manifest tests. Локально пройдены backend 106/106, app tests 8/8, Django/migration checks, contracts/import boundary/domain/sandbox suites, compileall и diff check.
- PR [#25](https://github.com/D0UP1G/FirsterChuv/pull/25) открыт в `develop`; проверенный head `ee036ad31ad109407076b7cbdf7fac8410caf750`, все четыре CI job прошли (`37970626824`), `OPEN / CLEAN`, не слит.
- Аудиты: [implementation](../audits/2026-10-09T210104+0300-agent-3-P3-02.3-artifact-language-types.md), [publication](../audits/2026-10-09T210259+0300-agent-3-P3-02.3-publication.md), [последний head CI](../audits/2026-10-09T210424+0300-agent-3-P3-02.3-final-head-check.md). Следующий шаг: дождаться review/merge по GitFlow; не сливать самостоятельно.

### Снимок P3-02.2 до интеграции #26

- P3-02.2 admin-catalog slice — `IN_REVIEW`; изолированная ветка `feature/problem-catalog-management` от актуального `origin/develop` SHA `505a2bc0cee82281becb431996bf3a62827edac8`.
- Реализован admin-only `GET /problems` для paginated version/readiness list без checksum/private artifacts; DTO описан в `docs/architecture/api.md`. Contract request о run-pinned version/checksum добавлен со статусом `WAITING_CONNECT`. Проверки: problems 25/25, backend 109/109, Django/migration, compileall, contracts 9, common import, domain 36, sandbox 12, diff check — PASS.
- Пути: `backend/apps/problems/{serializers.py,views.py,urls.py,tests/test_catalog_api.py}`, `backend/apps/common/api_urls.py`, `docs/architecture/api.md`, `context/contracts/agent-3-workspace-problem-version.md`, эта карточка и audit.
- P3-02.3 реализован отдельно в PR [#25](https://github.com/D0UP1G/FirsterChuv/pull/25) и остаётся открытым, неинтегрированным до merge в `develop`; чужие/общие ветки и checkout не редактировать.
- Audit: [2026-10-09T211119+0300-agent-3-P3-02.2-admin-catalog.md](../audits/2026-10-09T211119+0300-agent-3-P3-02.2-admin-catalog.md).
- PR [#26](https://github.com/D0UP1G/FirsterChuv/pull/26) открыт в `develop`; implementation SHA `57134337c1ccc1feb84da0f4886c56591dcb0a40`, все четыре CI jobs прошли, `OPEN / CLEAN`, не слит.
- Publication audit: [2026-10-09T211328+0300-agent-3-P3-02.2-publication.md](../audits/2026-10-09T211328+0300-agent-3-P3-02.2-publication.md). Не объединять этот PR с PR #25 и не выдавать P3-02.2 за завершённый.
- P3-02.2 residual: normalized importer/status management требует P3-02.3 parser fix; task selection зависит от A2 persistence; participant workspace access ждёт version/checksum contract. Не выдавать весь P3-02.2 за завершённый.

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
