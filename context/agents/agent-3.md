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
- P3-04.1 #15 реализован в `a6d3674`: busy/locked → bounded whole-transaction retry/503, исходный `received_at`, file-backed concurrent keys/rollback tests; PR #15 обновлён и ждёт CI/review.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

## Текущая сессия: P3-03 · LocalJudge

- Статус: `IN_REVIEW`.
- Ветка: `feature/local-judge`; база: `origin/develop` SHA `f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (сверена после `git fetch origin develop`).
- Code commit: `732279bba0994a9f4d6f37e54f62449743201eae`; PR #23: https://github.com/D0UP1G/FirsterChuv/pull/23, base `develop`, status OPEN.
- Требования: J01/J02/E03 и часть J03/S01; ROADMAP v3 P3-03. Источники: `docs/requirements.md`, `docs/architecture/parallel-contracts.md`, `docs/architecture/runtime-handoffs.md`, `docs/architecture/judging.md`, страницы 4–5 и 7 кейса.
- Подзадачи: (1) реализовать `JudgeProvider.execute(TrustedJudgeJob)` поверх доверенного `ProblemCatalogV1.load_bundle`, проверить checksum и неизменяемую версию; (2) использовать только серверный compiler registry, компилировать и запускать каждый тест через собственную sandbox; (3) применить лимиты задачи с жёсткими пределами сервиса и классифицировать OK/WA/TL/ML/RE/CE, отделяя infra failures; (4) ограничить CE diagnostics и оставить их внутренним/private результатом; (5) покрыть policy/verdict/error/privacy границы тестами; (6) проверить реальный programmatically imported synthetic smoke только при доступном Docker Engine, не выдавая его за official acceptance.
- Пути с изменениями: `backend/apps/judge/`, регистрация своей app в `backend/config/settings.py`, `sandbox/runner.py` compatibility import, `sandbox/container_runner.cpp`, `sandbox/smoke.py`, `sandbox/tests/`, их README, эта карточка и отдельный P3-03 audit. `backend/apps/problems/compilers.py` не изменён: `cpp20` остаётся `verified=False` до настоящего Docker proof. `context/STATE.md` и чужие feature refs не менялись.
- Ограничение preflight: на `2026-10-09 20:42 MSK` `docker info` не подключился к `unix:///var/run/docker.sock`; `cpp20` остаётся `verified=False`, пока реальный sandbox/compiler proof не выполнен. Формат official checker неизвестен без package README; не вводить предположительный формат организаторов и не исполнять package scripts на host.
- Runtime CONNECT открыт: текущие `compose.yaml` и `backend/Dockerfile` не дают judge-worker Docker CLI/Engine access; это shared deployment wiring P1-04/P3-04.2. Доступность Docker из host runner сама по себе не меняет compiler readiness.
- Разделение результата: implementation — LocalJudge core и task policy; integration — worker/Docker CLI/Engine CONNECT ещё не выполнен; acceptance — реальный Docker smoke недоступен, checker protocol ждёт package README. GitHub CI PR #23: 4 jobs PASS после одного rerun; первый backend запуск флакнул на чужом invite-concurrency тесте P1, повтор прошёл без изменений ветки. Официальный package/T12/T14/T18/T20/T21 acceptance не закрывается synthetic bundle или тестовыми doubles.

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
