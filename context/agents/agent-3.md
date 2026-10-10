# Агент 3: задачи, очередь, песочница и запуск

## Волна 1 · текущая задача P1-04.2 · 2026-10-10

- Статус: implementation slice готов к review; полная задача `IN_PROGRESS`, acceptance `NOT_RUN` для Docker/runtime. ROADMAP v6.
- Ветка: `feature/p1-04-2-compose-runtime`; база `48cb06a4fc5a02121f117cd1f17330f0cde13fdf`.
- `origin/develop` обновился до `ee755af6ed93e7c3996cb5e70edd8d21e527c56a` и был включён в feature fast-forward до начала новых изменений.
- Scope: одна host-команда запускает web/API/worker/match-clock, собирает pinned sandbox image, Compose health-gates зависимые сервисы и сохраняет DB volume; production API остаётся без Docker socket, socket доступен только trusted judge-worker.
- Требования: D01/D03, S01, частично T01/T19; запуск полного M0 не объявлять без merged P3 factories/compiler/import и реального Docker evidence.
- Пути: `compose.yaml`, `backend/Dockerfile` только для Docker CLI client, `scripts/start-demo.sh`, `README.md`, `docs/operations/runbook.md`, эта карточка и отдельные audits. Чужие apps/worktrees, `.env`, secrets, compiler policy и global Docker state не трогать.
- Fresh `origin/develop` содержит A4 `run_match_clock`; открытые P3-04.2/P3-02.2 PR 83/85 не включать в эту ветку и не сливать.
- Проверка host Docker/Compose в этом окружении: Docker Engine socket и Compose plugin отсутствуют; build/Compose runtime acceptance будет NOT_RUN.
- Проверки implementation: `sh -n scripts/start-demo.sh`, Ruby YAML parse, `git diff --check`, Django `check`, `makemigrations --check --dry-run` прошли. Docker Engine/socket/Compose недоступны, поэтому image build, Compose startup и T01/M0 runtime acceptance — NOT_RUN.
- Независимости: P3-04.2 worker factory и P3-02.2 demo import/compiler остаются отдельными PR. Включать их код сюда нельзя; не объявлять M0 завершённым.
- PR [#86](https://github.com/D0UP1G/FirsterChuv/pull/86) открыт в `develop`, опубликованный head `420c434bf3863354e869e490854389f864939a44`, `OPEN / MERGEABLE`; пять CI jobs на этом head прошли (`38019333813`).
- Следующий шаг: review/решение команды; реальный Docker smoke выполнить после появления Engine и включённых зависимостей. Merge не выполнять.

## Текущая сессия P4-08 · disposable system acceptance harness · 2026-10-10

- ID задачи: `P4-08`; implementation slice: `IN_REVIEW`; полная задача: `IN_PROGRESS`.
- Ветка: `feature/p4-08-acceptance`; базовый SHA: `origin/develop=475cdf71fa88de6aa5aad2142fc9fdbdf90625f6`.
- Объём по ROADMAP v5 и `docs/quality/m0-demo.md`: создать собственный disposable acceptance harness для реально доступных HTTP/runtime путей; фиксировать каждую проверку как `PASS`/`FAIL`/`NOT_RUN`, не выдавая test doubles или отсутствующие production endpoints за PASS.
- Пути планируемых изменений: `scripts/acceptance/`, `docs/quality/evidence/`, эта карточка и отдельный audit `context/audits/`; общие API, контракты, Compose и production apps не менять.
- Предшествующие P3-04.2/import worktree активны отдельно; их исходники и карточки не изменять. Требуемые кейсовые ограничения: D01/D03, J01/J03/J04, T01/T04–T10/T14/T18/T19/T20/T21; полный M0 и T01–21 не объявлять без подтверждения сквозного SHA.
- Реализован narrow real-HTTP runner `scripts/acceptance/run_api_smoke.py`: временная SQLite, временный application admin и participant sessions, loopback WSGI, auth/CSRF/role/invite/idempotent join/bracket permission checks. Evidence контракт и ограничения описаны в [`docs/quality/evidence/README.md`](../../docs/quality/evidence/README.md).
- Проверки разработки: 13/13 API checks PASS на disposable DB; optional `--sandbox` сообщил `NOT_RUN` из-за недоступного Docker Engine; все полные G01–G06 и T01–T21 остаются `NOT_RUN`. Ruff, `py_compile`, `git diff --check` прошли. При разработочном прогоне worktree был dirty; сохранённое acceptance evidence будет создано после commit на точном SHA.
- Следующий шаг: опубликовать reviewable PR в `develop`, не сливать; полное P4-08 остаётся `IN_PROGRESS` до реальных queue/recovery/compiler/runtime и acceptance CONNECT сценариев.

### Checkpoint P4-08 evidence · 2026-10-10T03:15:07+03:00

- Code + implementation audit зафиксированы в `fdf75d89f8c2ee2417d3528e2eb0c36ac022482c`.
- На clean SHA создан [`docs/quality/evidence/2026-10-10T031449+0300-P4-08-api-smoke.json`](../../docs/quality/evidence/2026-10-10T031449+0300-P4-08-api-smoke.json): 13/13 HTTP checks PASS, `worktreeClean=true` до записи manifest. Docker probe `NOT_RUN`; все G01–G06 и T01–T21 остаются `NOT_RUN`. См. [follow-up audit](../audits/2026-10-10T031507+0300-agent-3-P4-08-evidence.md).
- Publication: PR [#75](https://github.com/D0UP1G/FirsterChuv/pull/75) открыт в `develop`, head `6fed027648fc7b6070305cf194d13d58a47638ac`, merge state `CLEAN`, не слит. CI run `38008387145` на этом head: 5/5 SUCCESS; backend 279 tests, 9 skipped. См. [publication audit](../audits/2026-10-10T031939+0300-agent-3-P4-08-publication.md).
- Следующий шаг: дождаться review/интеграции без merge со стороны A3; продолжать P4-08 с реальными queue/recovery/compiler/runtime и acceptance CONNECT только на доступном свежем integration SHA.

### Сверка после CI PR #75 · 2026-10-10T03:25:00+03:00

- PR #75 остаётся OPEN/CLEAN на head 2d008692aee71ba1443456aecb2a46ac2a33ebce; CI run 38008613938 прошёл 5/5 jobs. PR не слит.
- Свежий fetch оставил origin/develop на 475cdf71fa88de6aa5aad2142fc9fdbdf90625f6. В develop уже есть отдельный ручной workflow sandbox-real-smoke.yml; дублирующий запуск не добавлялся. Этот Docker smoke в follow-up не запускался.
- A3 LocalJudge/executor, import, worker и draft ветки ведутся в отдельных worktrees; PR #76 с A4 persistence ещё открыт. Чужая работа не менялась. Свободного READY среза без пересечения на этой сверке не найдено.
- Следующий шаг: оставить #75 открытым и после командной интеграции свежих producer/provider SHA продолжить фактические P4-08 queue/runtime проверки. Подробности: [follow-up audit](../audits/2026-10-10T032500+0300-agent-3-P4-08-followup.md).


## Актуальное назначение координатора 2026-10-10T01:56:32+03:00: ROADMAP v5

- Источник: последнее прямое уточнение команды — ровно три роли A3/A4(прежний A1)/A5.
- Статус назначения READY; actual IN_PROGRESS/branch/base/paths владелец фиксирует перед своими edits. Датированная передача не запускает остановленную сессию.
- Первое действие: P3-04.1 admission contention и P3-04.2 actual LocalJudge executor/factory + normalized import/compiler smoke.
- Независимый резерв: P3-02 import/assets/checker/registry probes; P1-04 build/Compose/settings/readiness; P3-05 private workspace/drafts; P4-08 disposable system harness.
- Владение: problems/submissions/drafts/judge/sandbox, backend/config, deploy/Compose/start scripts/.github CI/scripts/acceptance/docs/quality/evidence. Common contracts и API/domain принадлежат A4.
- Передача: A4 gateway/snapshot/result+failure sinks → A3 factories/queue/worker; не ждать HTTP для собственного judge smoke. CI #63 attempt1 admission lock не исправляется rerun.
- Fresh develop base этой ревизии 85e0cd0d2b82fce9996106af3922171dcee17c76; #60/#61/#62 MERGED. #63/#64 доступны после MERGED coordinator PR; #53/#57–59 пока не integrated. Не ждать отдельный STATE sync.
- M0 → [ROADMAP v5](../../ROADMAP.md), [приёмка](../../docs/quality/m0-demo.md). При WAITING записать конкретный port/producer/consumer/SHA и в той же сессии взять следующий READY пункт. Explicit user stop имеет приоритет. Ни одна готовая часть/чужой audit не удаляется.

## Текущая сессия P3-04.1 · contention при приёме посылок · 2026-10-10

- Статус: `IN_REVIEW`; [PR #68](https://github.com/D0UP1G/FirsterChuv/pull/68) открыт; пять CI checks прошли на head `127d27d`.
- Ветка: `feature/p3-04-1-admission-contention`; начальная база `a6083263b54538275317d86f23d1034125813848`, затем обычный merge свежего `origin/develop=1f95b72385c9bbaea0d6271a98dccffc8f4caa2b` в `ac93676670a23aec00863e992d918b35b29e7795`.
- Основание: ROADMAP v5 и coordinator audit фиксируют uncaught SQLite lock в конкурентном same-key admission в первой CI-попытке #63; зелёный повтор не считается исправлением.
- Изменены: `backend/apps/submissions/services.py`, `backend/apps/submissions/tests/test_admission_concurrency.py`, карточка и [`аудит реализации`](../audits/2026-10-10T022731+0300-agent-3-P3-04.1-admission-contention.md).
- Причина: CI зафиксировал `database table is locked: submissions_queuecounter` на `get_or_create` при одновременной попытке перевести shared-cache read-lock в write-lock; одинаковые retry-паузы могли повторно сталкивать запросы.
- Исправление: первой операцией в admission transaction выполняется `bulk_create(ignore_conflicts=True)` глобального QueueCounter — write-first точка сериализации; затем заново проверяется idempotency. Добавлен барьерный same-key тест, который сводит оба потока к этой операции и проверяет один submission/receipt/event и исходный `received_at`.
- Проверки: shared-cache concurrency 4 passed/1 ожидаемый skip; file-backed submissions 49/49; полный backend 259 passed/4 ожидаемых skip; Django check, migration drift, 9 contract fixtures, common imports, domain suites, compileall и diff check прошли.
- Требования: J04 и частично E03; полный T14/T19/T20 и end-to-end приёмка этой работой не закрываются. Миграций и изменений контрактов нет.
- Публикация: код отправлен только в свою feature-ветку; PR #68 направлен в `develop`. Создание PR и CI зафиксированы в [аудите публикации](../audits/2026-10-10T022937+0300-agent-3-P3-04.1-publication.md) и [аудите CI](../audits/2026-10-10T023211+0300-agent-3-P3-04.1-ci.md).
- Следующий шаг: дождаться review, PR не сливать; затем перепроверить принадлежность и статус следующего P3-04.2 перед любыми изменениями.

## Исторические записи до ROADMAP v5

## Назначение координатора 2026-10-10T01:11:53+03:00: Реальная проверка и workspace

- Источник: прямое поручение команды перераспределить оставшийся MVP и создать нового frontend owner. Это текущее назначение; прежние author checkpoints ниже сохранены как история.
- Статус назначения: READY; фактический IN_PROGRESS выставляет владелец при начале edits в своём изолированном checkout.
- Первое действие: P3-04.2 real LocalJudge executor/factory + programmatic immutable smoke bundle, runtime compiler readiness.
- Независимый резерв: P3-02 import management; P3-05 WorkspaceAccess CONNECT; accepted snapshot fields и own fenced container recovery.
- Владение: problems/submissions/drafts/judge/sandbox; shared config только A1.
- Fresh develop после подтверждённого merge integration feature; #21 CAS исправлен, #50 pairings/reset проверяется вместе, #53 не integrated/нужен fix. Готовые cores не повторять.
- [ROADMAP v4](../../ROADMAP.md), [принятые границы](../contracts/2026-10-10-mvp-boundaries.md). При WAITING одного CONNECT в той же сессии брать следующий READY пункт. Explicit user stop важнее назначения; Git сам не переключает соседний checkout.


## Актуальный checkpoint координатора: разблокирование 2026-10-09

- По поручению команды координатор проверил опубликованные PR и аудиты. Конкретный merge-блокер normalized import management снят: [#25](https://github.com/D0UP1G/FirsterChuv/pull/25) `MERGED`, merge `ed14416fee0d1cccbd0b9a202e563d49f062572a` в `develop`.
- #26 `435cef7` admin catalog, #15 `555ca0e` очередь с исправленным admission race и #23 `942b4f5` LocalJudge проверены и объединены обычными merge commits в `feature/agent-3-merge-unblock`. До `MERGED` её PR это проверенная интеграционная ветка; после merge брать свежий `origin/develop`, отдельный STATE PR не prerequisite. Исходные feature refs автора сохранены.
- P3-04.1 исправлен: file-backed submissions suite 29/29. P3-03 получил настоящую проверку координатора на Docker Engine 29.8.2: 5 sandbox smoke, task limit 100 ms/64 MiB и LocalJudge → immutable stored synthetic bundle → OK. Образ `firsterchuv/review-local-judge:942b4f5` создан отдельно; production image/registry не переключались. `cpp20.verified=False` сохраняется до deployment/readiness wiring. Checker protocol/official acceptance по-прежнему ждут README пакета.
- [#21](https://github.com/D0UP1G/FirsterChuv/pull/21) `1706ecf` остаётся на исправлении: одновременный первый PUT из двух вкладок на файловой SQLite воспроизводит `OperationalError: database is locked`; API не переводит его в контролируемый ответ. **P3-05.1 READY:** bounded retry всей CAS transaction только для BUSY/LOCKED, повторно проверить revision, после исчерпания вернуть retryable 503; другой победивший source должен дать 409, не перезаписываться. File-backed tests: first creation/update, один namespace, оба разных source, ровно одна победившая revision/history, CSRF/IDOR не ослаблять.
- Следующие независимые READY: P3-02.2 normalized upload/import status management (parser #25 уже доступен), P3-04.2 actual worker/lease/recovery/result outbox, P3-05.1 CAS race #21. Не писать заново уже проверенные queue/catalog/LocalJudge cores.
- WAITING_CONNECT ограничен конкретными подпунктами: production A2 gateway/ledger/result/failure sink, version/checksum workspace contract. До подключения использовать DI/test-only ports; runtime fail-closed. Если один подпункт ждёт — в той же сессии продолжать следующую READY задачу. P3-06 отдельно WAITING_EXTERNAL на official package.
- Полная приёмка MVP/browser/hostile/restart не закрыта. Подробности проверки и передачи: [новый аудит](../audits/2026-10-09T224851+0300-coordinator-agent-3-unblock.md).
- Integration PR [#32](https://github.com/D0UP1G/FirsterChuv/pull/32): первый объединённый head прошёл 4/4 CI; fresh A4 #31 сохранён до merge, повтор CI на обновлённом head. [Publication checkpoint](../audits/2026-10-09T230104+0300-coordinator-agent-3-publication.md). После `MERGED` не ждать дополнительный STATE/ответ соседнего автора для уже READY import/worker/CAS fix.

## Исторические checkpoint публикаций

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
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

## Исторический checkpoint: P3-03 · LocalJudge

- Статус: `IN_REVIEW`.
- Ветка: `feature/local-judge`; база: `origin/develop` SHA `f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (сверена после `git fetch origin develop`).
- Code commit: `732279bba0994a9f4d6f37e54f62449743201eae`; PR #23: https://github.com/D0UP1G/FirsterChuv/pull/23, base `develop`, status OPEN.
- Требования: J01/J02/E03 и часть J03/S01; ROADMAP v3 P3-03. Источники: `docs/requirements.md`, `docs/architecture/parallel-contracts.md`, `docs/architecture/runtime-handoffs.md`, `docs/architecture/judging.md`, страницы 4–5 и 7 кейса.
- Подзадачи: (1) реализовать `JudgeProvider.execute(TrustedJudgeJob)` поверх доверенного `ProblemCatalogV1.load_bundle`, проверить checksum и неизменяемую версию; (2) использовать только серверный compiler registry, компилировать и запускать каждый тест через собственную sandbox; (3) применить лимиты задачи с жёсткими пределами сервиса и классифицировать OK/WA/TL/ML/RE/CE, отделяя infra failures; (4) ограничить CE diagnostics и оставить их внутренним/private результатом; (5) покрыть policy/verdict/error/privacy границы тестами; (6) проверить реальный programmatically imported synthetic smoke только при доступном Docker Engine, не выдавая его за official acceptance.
- Пути с изменениями: `backend/apps/judge/`, регистрация своей app в `backend/config/settings.py`, `sandbox/runner.py` compatibility import, `sandbox/container_runner.cpp`, `sandbox/smoke.py`, `sandbox/tests/`, их README, эта карточка и отдельный P3-03 audit. `backend/apps/problems/compilers.py` не изменён: `cpp20` остаётся `verified=False` до настоящего Docker proof. `context/STATE.md` и чужие feature refs не менялись.
- Ограничение preflight: на `2026-10-09 20:42 MSK` `docker info` не подключился к `unix:///var/run/docker.sock`; `cpp20` остаётся `verified=False`, пока реальный sandbox/compiler proof не выполнен. Формат official checker неизвестен без package README; не вводить предположительный формат организаторов и не исполнять package scripts на host.
- Runtime CONNECT открыт: текущие `compose.yaml` и `backend/Dockerfile` не дают judge-worker Docker CLI/Engine access; это shared deployment wiring P1-04/P3-04.2. Доступность Docker из host runner сама по себе не меняет compiler readiness.
- Разделение результата: implementation — LocalJudge core и task policy; integration — worker/Docker CLI/Engine CONNECT ещё не выполнен; acceptance — реальный Docker smoke недоступен, checker protocol ждёт package README. GitHub CI PR #23: 4 jobs PASS после одного rerun; первый backend запуск флакнул на чужом invite-concurrency тесте P1, повтор прошёл без изменений ветки. Официальный package/T12/T14/T18/T20/T21 acceptance не закрывается synthetic bundle или тестовыми doubles.

## Текущая сессия: P3-04.2 · submission worker/recovery

- ID задачи: `P3-04.2`; статус: `IN_PROGRESS` (реализация и локальная проверка завершены; публикация ждёт интеграции PR #15).
- Ветка: `feature/submission-worker`; база `origin/develop`: `15e3edf4fdfe7910f0984f97f26eee8589d5319b`.
- Зависимость: PR #15 (`feature/submission-queue-core`, head `555ca0ee692fdc4472857e3f2350c01819224f1e`) остаётся OPEN/CLEAN, четыре CI jobs PASS. Queue core включён merge commit `cae2d74` только в эту собственную feature-ветку; исходную ветку/worktree не менять.
- Изменены только `backend/apps/submissions/{worker.py,factory.py,README.md}`, собственные management command/tests, эта карточка и audit. Общие config/Compose/contracts и чужие paths не менялись.
- Реализованы durable loop с приоритетом due outbox, worker/executor/result sink fail-closed factory, heartbeat ограниченного claim lease, stale-result guard, infra retry без verdict, command `run_judge_worker` с bounded CLI options, recovery очереди/outbox при повторных циклах.
- Основание: J04/E03 и частичные серверные сценарии T09/T14/T19/T20; runtime snapshot/adapters/failure sink P3-04.3–4 и реальный LocalJudge остаются отдельной работой. В этой задаче нет sandbox process registry, поэтому cleanup ограничен durable DB lease recovery.
- Проверки этой ревизии: submissions suite 41/41 PASS на файловой SQLite; system checks PASS; migration drift отсутствует; compileall и `git diff --check` PASS; command обнаруживается и без factory отказывает закрыто.
- Аудит старта: [`2026-10-09T213942+0300-agent-3-P3-04.2-start.md`](../audits/2026-10-09T213942+0300-agent-3-P3-04.2-start.md). Аудит реализации: [`2026-10-09T214617+0300-agent-3-P3-04.2-worker.md`](../audits/2026-10-09T214617+0300-agent-3-P3-04.2-worker.md).
- Следующий шаг: дождаться merge PR #15 в `develop`; затем обновить эту ветку обычным `git merge origin/develop`, проверить собственный diff и опубликовать PR строго в `develop`. После публикации главный READY execution приоритет — P3-03 LocalJudge; P3-04.3–4 продолжить после него/по доступности A2 adapter и snapshot. До публикации PR #15 не создавать дублирующий stacked PR.
- Handoff-сверка: [`2026-10-09T214821+0300-agent-3-P3-04.2-handoff-correction.md`](../audits/2026-10-09T214821+0300-agent-3-P3-04.2-handoff-correction.md) уточняет порядок из аудита реализации по ROADMAP v3.

## Текущая сессия: P3-04.3 · queue adapters к common v1

- ID задачи: `P3-04.3`; статус: `IN_PROGRESS`.
- Ветка: `feature/submission-worker`; HEAD на старте `38ed3bef68fab79085200a0bda8570be2830f1c3`; последний проверенный `origin/develop=c5682dd657969b699e22b8a2815b5247ad5a1553`.
- Ветка уже содержит локальную queue dependency из PR #15 и предыдущий P3-04.2; чужие worktree/ветки не редактируются. По прямому указанию команды не сливать `origin/develop` или чужие feature branches.
- Планируемые пути: `backend/apps/submissions/adapters.py`, adapter tests, submissions README, эта карточка и отдельные start/implementation audits. Shared contracts/settings/Compose и миграции не менять.
- Срез: адаптировать local queue receipts/ports к common `CompetitionGatewayV1`, `EventWriter`, `LanguageRegistry`, `ResultSink`; `match_id` остаётся local-only, common DTO exact shape сохраняется, `ResultApplication.applied=False` считается успешно доставленным receipt.
- Настоящих A2 production providers ещё нет; адаптеры не создают fallback/fake runtime и не включаются в factory. Не менять открытые PR #15/#16/#21/#23/#25/#26.
- Стартовый аудит: [`2026-10-09T220323+0300-agent-3-P3-04.3-start.md`](../audits/2026-10-09T220323+0300-agent-3-P3-04.3-start.md).
- Реализация: exact common `AttemptReceipt`/`ResultReceipt` mapping (local-only `match_id` не утекает), permit conversion, EventWriter/LanguageRegistry forwarding, `ResultApplication.applied` mapping; `applied=False` проверено end-to-end как успешная outbox delivery. Изменены `submissions/adapters.py`, tests и README; shared contract files/config не менялись.
- Проверки: submissions suite 46/46 PASS на файловой SQLite; Django checks, compileall, migration drift check и `git diff --check` PASS. Runtime A2 providers не запускались.
- Implementation audit: [`2026-10-09T220539+0300-agent-3-P3-04.3-adapters.md`](../audits/2026-10-09T220539+0300-agent-3-P3-04.3-adapters.md). Статус остаётся `IN_PROGRESS` до разрешённой интеграции/PR; user instructed not to merge branches.

## Текущая сессия: P3-04.4 · failure outbox и run snapshot handoff

- ID задачи: `P3-04.4`; статус: `IN_PROGRESS`.
- Ветка: `feature/submission-worker`; HEAD на старте `cb18524abb2e26bb440f8cd44078ea7244a0ac8c`; свежий `origin/develop=c5682dd657969b699e22b8a2815b5247ad5a1553` проверен.
- Работать только с собственным submissions app и документацией; PR/ветки #15/#16/#21/#23/#25/#26 и их worktree не менять. По прямому указанию пользователя branch merge не выполнять.
- READY срез: typed-compatible local `InfrastructureFailureReceipt/Sink`, durable terminal failure outbox и redelivery; собственная app migration допустима. Test doubles только в tests, runtime требует реальный sink.
- Run snapshot version/checksum отсутствуют в common `SubmissionPermit`/production A2 provider. Оформить отдельный contract request без изменения common contract/изобретения A2 API; snapshot resolver не реализовывать до согласования.
- Планируемые пути: submissions ports/models/services/worker/factory/own migration/tests/README, `context/contracts/` request, эта карточка и отдельные audits.
- Стартовый аудит: [`2026-10-09T220642+0300-agent-3-P3-04.4-start.md`](../audits/2026-10-09T220642+0300-agent-3-P3-04.4-start.md).
- Реализация текущего среза: добавлены локальные совместимые `InfrastructureFailureReceipt/Sink`, terminal `InfrastructureFailureOutbox` и app-local migration; exhausted retry и recovery просроченного последнего worker lease создают durable outbox только при успешном status transition. Worker доставляет отдельный технический receipt с allowlisted reason через lease/retry; receipt не содержит source/diagnostics и не создаёт verdict. Test-only sinks остаются только в тестах; factory/runtime по-прежнему требует production ports.
- Run snapshot version/checksum не реализован без A2 provider и решения по boundary. Запрос оформлен в [`agent-3-run-problem-snapshot.md`](../contracts/agent-3-run-problem-snapshot.md), статус `WAITING_CONNECT`; production submit/judge должен оставаться закрыт без источника trusted immutable snapshot.
- Реализация audit: [`2026-10-09T221206+0300-agent-3-P3-04.4-failure-outbox.md`](../audits/2026-10-09T221206+0300-agent-3-P3-04.4-failure-outbox.md). Проверки: submissions suite 49/49, Django system checks, compileall, migration drift check и `git diff --check` PASS.
- Срез остаётся `IN_PROGRESS`: common A1 DTO/Protocol, A2 idempotent technical ledger sink, A2 run snapshot provider и runtime wiring не интегрированы. Код только в этой feature-ветке; другие A3 worktree/PR не редактировались, merge/push/PR в этой сессии не выполнялись по указанию пользователя.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).

## Срез P3-05, начатый до перепланирования v3

- Статус: `IN_REVIEW`; [PR #21](https://github.com/D0UP1G/FirsterChuv/pull/21), feature `feature/private-drafts-history` → `develop`.
- Начальная база: `cad34ea4ddf1171779dc22139f2e1533160b5015`; синхронизации `origin/develop=1f60aa9` (`4b6030d`) и `origin/develop=ae0846b22953527d74835febf963169e2093238d` (`bb33c11`, merge commit). Код/audit commit `fbdb01c`.
- Реализация: private storage/history, CAS, common `WorkspaceContext` actions, active participant/CSRF/IDOR guard, своя миграция. Без настоящего A2 provider runtime fail-closed с 503. Contract proposal остаётся `PROPOSED`.
- Проверки на locked dependencies после последней синхронизации: backend 118/118; contracts 9 fixtures; common imports; domain 36/36; sandbox unit 12/12; Django check, migration drift, compileall и diff check прошли. Browser T15/T20 не выполнялись.
- `context/contracts/agent-3-private-draft-get.md` — `PROPOSED`: уточнить GET run selector и поведение отсутствующей записи. Browser T15 и полная T20 приёмка не выполнены; P4-04 остаётся CONNECT для autosave/history UI. `context/STATE.md` агентом 3 не менялся.
- Следующий шаг: дождаться review/checks PR #21 и решения по contract proposal; затем продолжить очередь ROADMAP v3 с P3-04.1, не изменяя чужую ветку/checkout без проверки владельца.

## Исторический checkpoint: P3-04.1 / admission race

- ID: `P3-04.1`; статус: `IN_REVIEW`.
- Ветка PR: `feature/submission-queue-core`; исходный HEAD `7d76d0b1bf85c7a707de72ebaa1cb8364b4c9207`; исходная база `cad34ea4ddf1171779dc22139f2e1533160b5015`; `origin/develop=ae0846b` синхронизирован merge `c2a653e`, затем `origin/develop=f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (#22) синхронизирован merge `6c1ccbf37d9acbaf482b696240a54b9c903ec2e5`.
- PR [#15](https://github.com/D0UP1G/FirsterChuv/pull/15): base `develop`, remote head `6c1ccbf` на момент публикации, состояние OPEN; после sync CI запущены, четыре GitHub jobs ещё `pending`. Кодовый fix — `a6d36745698fa60eaf2ee0fb17588009bf0d99a4`.
- Изменяемые пути: `backend/apps/submissions/services.py`, `errors.py`, `views.py`, `README.md`, `test_settings.py`, `tests/`, эта карточка и новый аудит. При sync сохранены `SubmissionsConfig` и `ProblemsConfig` в `INSTALLED_APPS`.
- Acceptance: только SQLite busy/locked вызывает bounded retry всей admission transaction; исчерпание преобразуется в retryable 503; сохраняется исходный `received_at`; file-backed concurrent TransactionTestCase покрывает разные/одинаковые idempotency keys, capacity и rollback ledger/event без 500.
- Реализация проверена: максимум 3 попытки всего, retry только SQLite `BUSY/LOCKED`, после исчерпания `503 queue_busy`; `received_at` вычисляется до цикла. File-backed submissions suite `29/29`; полный backend `134` tests, `OK`, один ожидаемый skip для file-backed probe при стандартной SQLite in-memory конфигурации.
- PR #15 и его worktree — существующие артефакты этого agent-3 checkout; не менять чужие ветки/worktrees. Общий `context/STATE.md` не редактировать.
- Publication audit: `context/audits/2026-10-09T203941+0300-agent-3-P3-04.1-publication.md`. Предыдущий head `a6d3674` имел четыре зелёных GitHub CI jobs; на обновлённом head после sync #22 надо дождаться их повторного результата/review.
- Следующий шаг: дождаться checks/review PR #15, не выполнять merge самостоятельно; затем продолжить P3-03 в отдельной feature-ветке от актуального `origin/develop`.

## Актуальная сессия: sync и продолжение P3-04 · 2026-10-09

- Задача: синхронизировать собственную `feature/submission-worker` с актуальной `origin/develop`, затем сверить реализацию очереди/worker с интегрированными queue core, LocalJudge, catalog и runtime contracts.
- Статус: `IN_PROGRESS`. Начальный HEAD feature: `59ed8c91af99077f6e59059989686796a4df2c02`; база до sync: `15e3edf4fdfe7910f0984f97f26eee8589d5319b`; входящий `origin/develop`: `6de4882f1f6ed712ba2704f539ea8421ede9d577`.
- Разрешённый scope: собственная `backend/apps/submissions/` и её tests/migrations/README, собственная карточка/audits и собственные contract requests. `context/STATE.md`, чужие apps/config/Compose, чужие ветки/worktrees и уже активные P3-02.2/P3-05.1 задачи не менять.
- Разрешённая команда merge: обычный `--no-ff` merge `origin/develop` в `feature/submission-worker`; PR merge и merge в `develop`/`main` не выполнять.
- Конфликт при sync возник только в этой карточке: сохранены новый checkpoint координатора и исторический LocalJudge checkpoint из develop, вместе с собственными аудитируемыми P3-04.2–4 записями.
- Стартовый аудит sync: [`2026-10-09T232137+0300-agent-3-P3-04-sync.md`](../audits/2026-10-09T232137+0300-agent-3-P3-04-sync.md).
- Обязательные документы и кейс повторно сверены; submissions suite после sync прошёл 49/49, migration drift отсутствует. Проверка нашла P3-04.2 gap: sandbox удаляет контейнер в `finally`, но аварийная остановка worker может оставить контейнер. Глобальный sweep по ownership label не выполнялся: ADR07 пока `PROPOSED`, и контракт не связывает контейнер с живым/просроченным queue lease; без этого sweep может удалить параллельную активную работу.
- Ограниченный запрос о безопасном worker/container recovery записан в [`agent-3-worker-container-recovery.md`](../contracts/agent-3-worker-container-recovery.md) со статусом `WAITING_CONNECT`. Это не блокирует revalidation и публикацию уже проверенных loop/lease/outbox частей P3-04.2.
- Аудит старта revalidation: [`2026-10-09T232240+0300-agent-3-P3-04.2-revalidation-start.md`](../audits/2026-10-09T232240+0300-agent-3-P3-04.2-revalidation-start.md).
- Revalidation audit: [`2026-10-09T232846+0300-agent-3-P3-04.2-postsync.md`](../audits/2026-10-09T232846+0300-agent-3-P3-04.2-postsync.md). Проверки после sync: submissions 49/49, backend 170 PASS/1 skip, sandbox unit 15/15, Django check, migration drift, compileall и diff check PASS. Docker Engine недоступен; real smoke не выполнен.
- Повторный fetch перед публикацией выявил новый `origin/develop=56c20eb3323c892d7f2fa9aadc6beb905548f677` (PR #35, только A4 transport/tests/audits). Собственная ветка чиста на `584d0fc`; начат follow-up sync в этой же feature.
- Стартовый аудит follow-up sync: [`2026-10-09T232929+0300-agent-3-P3-04-sync-followup-start.md`](../audits/2026-10-09T232929+0300-agent-3-P3-04-sync-followup-start.md).
- Follow-up sync завершён обычным merge `origin/develop` `56c20eb` в свою feature-ветку без конфликтов. Входящие изменения: A4 match transport/client tests и audits; A3 production files не затронуты. Проверен `git diff --check` для merge commit. Завершающий аудит: [`2026-10-09T232958+0300-agent-3-P3-04-sync-followup.md`](../audits/2026-10-09T232958+0300-agent-3-P3-04-sync-followup.md).
- Feature PR [#37](https://github.com/D0UP1G/FirsterChuv/pull/37) в `develop`: implementation-срезы P3-04.2 worker/leases, P3-04.3 adapters и P3-04.4 failure outbox находятся `IN_REVIEW`; PR не слит.
- Сразу после публикации GitHub base продвинулся `56c20eb → 7e2cb46` через PR #36 (A4 editor tests/audits only). Собственная ветка чистая; начинается ещё один ordinary sync перед обновлением PR.
- Стартовый аудит sync PR head: [`2026-10-09T233104+0300-agent-3-P3-04-sync-pr-head-start.md`](../audits/2026-10-09T233104+0300-agent-3-P3-04-sync-pr-head-start.md).
- Follow-up merge #36 завершён в своей ветке без конфликтов. Получены только `frontend/src/workspace/CodeEditor.test.tsx`, карточка/A4 audits; A3 source не затронут. Проверен `git diff --check`; обновление remote PR head ожидает обычного push. Audit: [`2026-10-09T233119+0300-agent-3-P3-04-sync-pr-head.md`](../audits/2026-10-09T233119+0300-agent-3-P3-04-sync-pr-head.md).
- После audit/card push PR #37 достиг head `8e9542829eb4cd83536bc991ef4dd1e0efece271`; CI run `37987957323` на нём прошёл 4/4. PR остаётся `OPEN/MERGEABLE`.
- Новый fetch: `origin/develop=25a82c092236d98275f897d624452b24bd501883` (PR #39, A4 compiler/language tests and docs only). Собственная ветка чиста; A3 source не затронут, начат очередной ordinary sync перед review.
- Стартовый аудит follow-up: [`2026-10-09T233629+0300-agent-3-P3-04-sync-pr-head-followup-start.md`](../audits/2026-10-09T233629+0300-agent-3-P3-04-sync-pr-head-followup-start.md).
- Merge PR #39 в свою feature завершён без конфликтов; изменились только `frontend/src/pages/ParticipantWorkspacePage.test.tsx`, `frontend/src/workspace/devTransport.ts`, A4 card/audits. Проверен `git diff --check`; A3 source/test files не изменились. Завершающий sync audit: [`2026-10-09T233646+0300-agent-3-P3-04-sync-pr-head-followup.md`](../audits/2026-10-09T233646+0300-agent-3-P3-04-sync-pr-head-followup.md).
- PR #37 обновлён fast-forward push до head `d532df06123057dcf395dffce7f8b3b264028b43`; base `25a82c092236d98275f897d624452b24bd501883`; `OPEN/MERGEABLE`. В CI run `37988178652` первый `backend` запуск упал на unrelated P1 invite concurrency (`database_busy`), rerun упал только этот job и прошёл; итоговый CI 4/4 PASS. A3 source не менялся. Audit: [`2026-10-09T234001+0300-agent-3-P3-04-ci-rerun.md`](../audits/2026-10-09T234001+0300-agent-3-P3-04-ci-rerun.md).
- Следующий шаг: дождаться review PR #37 и оставить его открытым до решения о слиянии. Container cleanup, immutable run snapshot и production A2 sinks остаются конкретными CONNECT подпунктами; P3-02.2/P3-05.1 выполняются в отдельных worktree.

### Финальная сверка PR #37 — 2026-10-09

- Повторный `git fetch origin` не выявил новых коммитов: `origin/develop=25a82c092236d98275f897d624452b24bd501883`; ветка `feature/submission-worker` чиста на `26b5cf1916a531868c41cc4728fd38009a400bf8`.
- Последний CI run `37988555234` на этом head завершился `success`, 4/4 job; PR #37 остаётся `OPEN/CLEAN` с базой `develop`.
- Код P3-04 не менялся в ходе сверки. Результат проверки и остающиеся CONNECT ограничения записаны в [аудите](../audits/2026-10-09T234207+0300-agent-3-P3-04-final-sync-ci.md).
- PR не слит. Следующий шаг: дождаться review; не интегрировать в `develop` без решения команды. Конкретные ожидания по container recovery, run snapshot и production A2 sinks остаются в contract requests.

## Текущая задача P3-05.1 · CAS race в приватных черновиках · 2026-10-10

- Статус: `IN_REVIEW`; PR [#21](https://github.com/D0UP1G/FirsterChuv/pull/21), feature `feature/private-drafts-history` → `develop`.
- Исходный head `1706ecfb8d16a693a462b3f3b7f379caeedc0060` синхронизирован обычными merge-коммитами с `origin/develop=1b7cc9e`, `659c45fe7e10250a0ea8dd14b637cce6b304a359` (PR #48) и свежим `cc204e62a060eb2ceb16067a1b0693a2e083d9ab` (PR #49). PR #48/#49 изменяли только A4 карточки/audits; единственный sync conflict был в этой карточке Agent 3, все historical блоки сохранены.
- Исправление: вся CAS transaction повторяется до 3 раз только для SQLite BUSY/LOCKED; после каждой ошибки транзакция откатывается перед повтором. После exhausted lock сервис выдаёт безопасный `503 draft_busy`; конкурентная запись после retry возвращает 409 с текущим server draft. Другие `OperationalError` не маскируются.
- Пути: `backend/apps/drafts/{services.py,errors.py,views.py,README.md,test_settings.py,tests/test_services.py,tests/test_api.py,tests/test_concurrency.py}`, эта карточка и audits.
- Проверки: file-backed drafts 18/18; отдельная first-create/update race 2/2; полный backend 248/248 PASS при повторном запуске (4 skips); queue admission file-backed 5/5; domain suites, 9 strict fixtures/common imports, Django check, migration drift, compileall и diff check PASS. В первом общем backend запуске один queue admission тест на in-memory SQLite закончил retryable `AdmissionBusy`; отдельный повтор 5/5 и полный suite повторно прошли. Эта отдельная flakiness записана в audit, не изменяла draft code.
- Требования `docs/requirements.md`: E04/S02; T15/T20 покрыты частично. Browser autosave/reconnect, hostile и полная T15/T20 приёмка не заявляются; настоящий A2 WorkspaceAccess provider отсутствует, поэтому production drafts API остаётся fail-closed.
- Стартовый аудит sync: [`2026-10-10T002545+0300-agent-3-P3-05.1-sync.md`](../audits/2026-10-10T002545+0300-agent-3-P3-05.1-sync.md); итоговый аудит: [`2026-10-10T003648+0300-agent-3-P3-05.1-cas-fix.md`](../audits/2026-10-10T003648+0300-agent-3-P3-05.1-cas-fix.md). Следующий шаг: опубликовать fast-forward push в PR #21 и проверить CI на новом head; PR не сливать.

## Текущая сессия P1-04.1 · runtime image/build slice · 2026-10-10

- Статус: `IN_PROGRESS` в целом; frontend image/build sub-slice готов к review, P1-04.1 не закрыта.
- Ветка: `feature/p1-04-1-runtime-build`; исходный `origin/develop=1f95b72385c9bbaea0d6271a98dccffc8f4caa2b`; обычный sync merge свежего `origin/develop=f9da1dda236fe66bcca30b79505f9f86e2fd426c` — `76c3a7af5822a989b6f78c07656811e356d8a893`.
- Основание: ROADMAP v5, P1-04.1 owner A3; порядок A3 ставит P3-04.2 раньше, но он уже помечен `IN_PROGRESS` в другом worktree, поэтому этот резерв выполняется без его изменения.
- До исходников проведён runtime inventory: Compose содержит API и профили web/runtime, но web монтирует host `frontend/dist`; frontend Dockerfile отсутствует. SQLite и package artifacts находятся в volume/БД. API entrypoint применяет WAL и migrations.
- Планируемые пути: новый `.dockerignore`, новый `frontend/Dockerfile`, `compose.yaml`, `docs/operations/runbook.md`, карточка и отдельный audit; не документировать full startup без реального runtime proof.
- Изменены: `.dockerignore`, `frontend/Dockerfile`, `compose.yaml`, `docs/operations/runbook.md`, карточка и [`audit реализации`](../audits/2026-10-10T024338+0300-agent-3-P1-04.1-runtime-build.md).
- Реализовано: multi-stage image собирает frontend из package lock и отдаёт static build через Nginx; Compose web больше не монтирует локальный `frontend/dist`, сохраняет профиль, localhost binding и API proxy. Build context исключает env/secrets, `.data`, official package/submission uploads и локальные dependencies. API/worker/sandbox не получили Docker socket.
- Проверки: `npm ci` 253 packages; production frontend build PASS; frontend 84/84; Ruby YAML parse/structural checks и `git diff --check` PASS. Docker image/Compose service smoke не выполнялись: engine/socket и `docker compose` plugin недоступны.
- Граница: это reviewable build/config slice, не вся P1-04.1 и не M0. Full startup зависит от нормализованного import command, A4 `run_match_clock` и real submission worker factory/providers, отсутствующих в `develop`; их active branches не менялись.
- Publication: [PR #72](https://github.com/D0UP1G/FirsterChuv/pull/72) открыт в `develop`; срез и текущий CI state зафиксированы в [publication audit](../audits/2026-10-10T024548+0300-agent-3-P1-04.1-publication.md).
- CI run `38006040901`: первый backend attempt упал на неизменённом queue admission SQLite lock-тесте; после `gh run rerun ... --failed` повтор прошёл (`270` tests, `9` skips), итоговые пять CI jobs зелёные. См. [CI retry audit](../audits/2026-10-10T025305+0300-agent-3-P1-04.1-ci-rerun.md).
- Следующий шаг: дождаться review, PR не сливать; вернуться к оставшейся P1-04.1 после интеграции зависимостей или выбрать следующий независимый A3 пункт.
- Найденные зависимости/ограничения: на актуальном develop отсутствуют management-команда `run_match_clock`, normalized bundle import command и настроенный production `SUBMISSION_WORKER_FACTORY`; P3-02.2/P3-04.2 и A4 runtime provider/clock связаны с активными чужими ветками, их не менять. Docker CLI есть, Docker Engine недоступен, `docker compose` plugin отсутствует; реальный image/stack smoke пока невозможен.
- Требования: D01/D03/S01, частично D06; полный T01/T18/T20/D04/D05 не заявлять. До независимого image и runtime smoke не считать P1-04.1 или M0 завершёнными.
