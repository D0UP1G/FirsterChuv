# Агент 3: sandbox, задачи и код

## Текущая сессия: P3-01

- ID задачи: `P3-01`; статус: `IN_PROGRESS`.
- Ветка: `feature/sandbox-proof`; база `origin/develop`: `d9488e3bf960c6a2248fd4399ba5848a091b8769`; исходный HEAD: `932c1a9deff64b222ecbebc9154c72547ac08ab8`.
- Пути в работе: `sandbox/runner.py`, `sandbox/container_runner.cpp`, `sandbox/tests/test_runner.py`, `sandbox/smoke.py`, `sandbox/README.md`, эта карточка и отдельный аудит сессии.
- Объём: устранить несовместимый `--pid=private`, закрыть доступ недоверенного процесса к stdout управляющего процесса и ограничить чтение stdout/stderr на хосте; выполнить локальные проверки и реальный runtime только при доступном Docker Engine.
- Проверено перед началом: рабочее дерево чистое; ветка содержит актуальный `origin/develop` merge; Docker socket в этом окружении ранее недоступен.
- Сделано локально: PID-флаг удалён; supervisor вызывает `PR_SET_DUMPABLE=0`; host runner ограничивает оба Docker pipe и завершает CLI при превышении; добавлены unit tests и smoke fixture `protocol-write`.
- Проверки: 12/12 sandbox unit tests, Python compile, C++20 syntax (`-Wall -Wextra -Werror`) и `git diff --check` прошли. `docker info` не подключился к `/var/run/docker.sock`; `python3 sandbox/smoke.py --case protocol-write` завершился `NOT_VERIFIED`, поэтому runtime probe и Engine inspect не подтверждены.
- Ограничение и следующий шаг: P3-01 остаётся `IN_PROGRESS` до runtime/hostile checks на доступном Docker Engine; затем синхронизировать/обновить PR #3. Независимый P3-02 выполнить в отдельной `feature/*` ветке от актуального `origin/develop`; внешний формат пакета не предполагать.
- Публикация: commit `4026c37dc0dcd4699a596bfbaed896e7a7d22bf0` отправлен в `origin/feature/sandbox-proof`; PR #3 остаётся `OPEN`, base `develop`, head SHA совпадает. GitHub вернул `mergeStateStatus=UNKNOWN` после обновления; merge не выполнялся.

Перепланировано координатором 2026-10-09 по PR #3. Историческое NOT_RUN сохранено в аудитах владельца.

- Реализация: harness в feature/sandbox-proof, HEAD 3a0d865, PR [#3](https://github.com/D0UP1G/FirsterChuv/pull/3) OPEN, пока не integrated; полного LocalJudge/worker/API нет.
- Проверки: 8 unit tests и C++ syntax прошли. Координатор собрал образ на доступном Docker 29.8.2; неизменённый runner НЕ запускается: --pid=private → invalid PID mode. Диагностическая копия без флага прошла 4 real smoke cases, это не исправление PR. Дополнительные sandbox риски см. отчёт ревизии.
- Первое задание: **P3-01 READY** — исправить запуск и границу управляющего канала, подтвердить bounded hostile/runtime checks, новый audit/PR. Не ждать агента 1 или официальный пакет для этого.
- Пути: sandbox, backend/apps/problems, submissions, drafts, judge; свои migrations/tests, fixtures problem/submission/draft.
- Очередь: P3-01 runner → P3-02 storage/safe import core → P3-03 LocalJudge → P3-04 durable queue → P3-05 private drafts/history. Если runtime/review/CONNECT ждёт, storage/queue core/drafts пишутся независимо с DI/test ports.
- **Только P3-06 WAITING_EXTERNAL:** официальный пакет и README отсутствуют. Mapping официального архива не угадывать. До получения вести normalized internal bundle и synthetic fixtures; финальные T12/T14/T21 не закрывать.
- P3-07 Yandex import после обязательного local MVP, никаких внешних вердиктов.
- Исторические аудиты: [harness](https://github.com/D0UP1G/FirsterChuv/blob/feature/sandbox-proof/context/audits/2026-10-09T140224+0300-agent-3-A3-01c.md), [publication](https://github.com/D0UP1G/FirsterChuv/blob/feature/sandbox-proof/context/audits/2026-10-09T143912+0300-agent-3-A3-01-pr.md).
- Следующий шаг: sync develop, собственные IN_PROGRESS/branch/base/paths; устранить F01/F07 и перепроверить реальные контейнеры. Отсутствующий adapter/provider в runtime всегда fail closed.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.

## Текущая сессия владельца: синхронизация и план

- Исполнитель: Codex, агент 3 по назначению пользователя.
- Поручение: `SYNC-PLAN-P3`; синхронизация, изучение изменений и план завершены локально. Реализация P3-01–05 ожидает прямого разрешения пользователя.
- Статус плана: `IN_REVIEW` у пользователя; статусы задач остаются согласно ROADMAP v2, P3-01–05 готовы к началу, но в этой сессии не выполнялись.
- Ветка: `feature/sandbox-proof`; исходный HEAD `3a0d86503b22b95b5004625ef8998cd1cc4c11c3`; новая база `origin/develop` = `d9488e3bf960c6a2248fd4399ba5848a091b8769`.
- Собственные пути сессии: эта карточка и `context/audits/2026-10-09T165721+0300-agent-3-SYNC-PLAN-P3.md`; код sandbox/backend не редактировался.
- Текущее окружение: read-only `docker info` вновь не подключился к `unix:///var/run/docker.sock`; доступен только default context. Результаты Docker в отчёте координатора относятся к его проверенной среде и не подтверждают доступность Engine в этой сессии.
- Порядок после разрешения: P3-01 исправление F01/F07 → P3-02 storage/import core → P3-03 LocalJudge → P3-04 durable queue → P3-05 private drafts/history. При ожидании runtime/review/CONNECT продолжать независимый storage/core своей дорожки.
- Только P3-06 ждёт официальный package/README; live A2 gateway/result/access wiring является CONNECT отдельных подпунктов P3-04/05. Production без реальных адаптеров отказывает.
