# Агент 3: sandbox, задачи и код

Перепланировано координатором 2026-10-09 по PR #3. Историческое NOT_RUN сохранено в аудитах владельца.

## Текущая сессия: P3-05

- ID задачи: `P3-05`; статус: `IN_PROGRESS`.
- Ветка: `feature/private-drafts-history`; начальная база `origin/develop`: `cad34ea4ddf1171779dc22139f2e1533160b5015`; синхронизировано merge-коммитом `4b6030d887bc41f3eb01d37370a3c9b36651760a` с `origin/develop=1f60aa9ad93a818d12c0b04b94cacec3f25b8d4e`.
- Пути в работе: `backend/apps/drafts/`, регистрация своей app/routes в `backend/config/settings.py` и `backend/apps/common/api_urls.py`, `docs/architecture/data-model.md`, запрос `context/contracts/agent-3-private-draft-get.md`, эта карточка и отдельный аудит.
- Объём: private user/run/problem/language draft, revision/history, version-conflict response. Используются опубликованные `WorkspaceContext` и отдельные actions `read_draft`, `write_draft`, `read_history`. Draft не запускает judge и не меняет score.
- Ограничения: не добавлять history HTTP route и не расширять GET/PUT без review contract request; admin/spectator не получают author-only code; не менять чужие apps/branches и `context/STATE.md`. Тестовый access adapter существует только в tests.
- Реализовано: private storage/history, CAS revisions, конфликт 409 с текущей серверной версией, CSRF/active participant/object-access guard, no-store для ответов с draft, собственная миграция. Без реального A2 provider/factory production API fail-closed с 503.
- Contract request `agent-3-private-draft-get.md` — `PROPOSED`: таблица HTTP не объясняет выбор run в GET и ответ для отсутствующей записи. Кодовая ветка требует `runId` в GET query; это не считается принятым решением или browser contract до review.
- Проверки на locked-зависимостях: drafts 13/13; полный backend 61/61; system check без issues; migration drift — No changes detected; 9 v1 fixtures/schema checks; common imports; standalone domain suite — ожидаемый no-op (suite отсутствуют); compileall и diff checks прошли.
- Приёмка: T15 browser reload/task/language/reconnect и полный T20 security matrix не выполнены; A2 production adapter отсутствует; P4-04 подключает autosave/history UI. `context/STATE.md` этим агентом не редактировался.
- Следующий шаг: проверить staged diff, коммитить содержимое вместе с аудитом, опубликовать `feature/private-drafts-history` PR в `develop` и запросить review contract proposal. Не merge-ить без подтверждённого review/merge по GitFlow.

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
