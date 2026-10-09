# Агент 3: sandbox, задачи и код

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

## Текущая сессия: P3-04

- ID задачи: `P3-04`; статус: `IN_REVIEW`.
- Ветка: `feature/submission-queue-core`; база `origin/develop`: `cad34ea4ddf1171779dc22139f2e1533160b5015`; исходный HEAD: `cad34ea4ddf1171779dc22139f2e1533160b5015`.
- Пути в работе: `backend/apps/submissions/`, `backend/config/settings.py`, разрешённая регистрация `backend/apps/common/api_urls.py`, эта карточка и отдельный аудит.
- Объём: private source/submission storage, idempotent bounded admission через обязательные injected ports, SQLite conditional claim/lease/retry/recovery и durable result outbox. HTTP/runtime без настоящих ports не принимать.
- Ограничения: provider/CompetitionGateway/EventWriter не реализованы в develop; тестовые adapters будут только в изолированных tests. Не менять чужие apps/branches и общий `context/STATE.md`.
- Реализовано в этой feature-сессии: admission + private author API, idempotency/hash, глобальная/авторская/матчевая capacity, rate limit, leases/renewal/recovery/backoff и ResultSink outbox; приложение и routes зарегистрированы штатно. Production POST без ports отвечает 503.
- Проверки feature worktree: `backend.apps.submissions` — 19 tests; полный backend — 66 tests; Django check, migration drift, compileall и diff check прошли. Реальный judge, HTTP 202 на настоящих MatchPort adapters и browser/hostile acceptance не запускались.
- PR: [#15](https://github.com/D0UP1G/FirsterChuv/pull/15), base `develop`, head `8462ba287585b0b548bfb4b44b113d7d77e4720c`, статус OPEN/MERGEABLE. Обязательных status checks нет.
- Текущий статус: срез опубликован и ожидает review; `context/STATE.md` не менялся. Подробности публикации — отдельный audit.
- Следующий шаг agent 3: пока P3-04 ожидает review/CONNECT, начать независимую P3-05 в отдельной feature-ветке от свежего `origin/develop`. После готовности P2-03/04 и P3-03 выполнить runtime CONNECT; не выдавать текущий core за работающий judge.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
