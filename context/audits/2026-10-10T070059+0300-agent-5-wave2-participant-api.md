# Аудит: Агент 5 / волна 2 (1/4) / backend API участника

- Автор/роль агента: Агент 5 по прямому поручению пользователя («бери себе задачи всех агентов»); файлы в зонах A3 (problems, submissions, config) и A4 (контракт доступа).
- Начало и окончание: `2026-10-10T06:46:00+03:00` — `2026-10-10T07:00:59+03:00`.
- ID задач: волна 2 ROADMAP v6: эндпоинты условия и языков (A3), WorkspaceAccess для черновиков (A3), подключение провайдеров API.
- Ветка: `feature/agent-5-wave2-participant-api`.
- Базовый SHA: `feef318e8ea9ceecb92570925f03c8f2db19874a` (`origin/develop`, merge #81).
- Статус: `IN_REVIEW` после публикации PR.
- PR / последующие коммиты: нет.

## Цель и исходное состояние

Рабочее место участника не могло работать на реальном backend: нет эндпоинтов условия и языков; `WORKSPACE_ACCESS_FACTORY` и `SUBMISSION_SERVICE_FACTORY` не заданы, поэтому API черновиков и посылок в рабочем окружении всегда отвечал 503. Шлюз `authorize_workspace(purpose="statement")` и `resolve(run, problem)` уже существовали.

## Выполненные изменения

- `backend/apps/problems/catalog.py`: `DjangoProblemCatalog.describe_pinned(problem_id, version, checksum)` читает публичную проекцию точной версии, закреплённой в запуске (READY и совпадающая контрольная сумма); последняя активная версия не используется.
- `backend/apps/problems/workspace_views.py`, `urls.py`: `GET /matches/{id}/problems/{problemId}` (условие, примеры, лимиты, id ресурсов) и `.../languages` (только компиляторы с `verified=True`). Доступ через WorkspaceAccess: участник замороженного запуска или админ; посторонний получает 404; до старта 409 `condition_not_available`; `Cache-Control: no-store`, `Referrer-Policy: no-referrer`; приватные тесты, чекеры и контрольные суммы в ответ не попадают.
- `backend/apps/submissions/api_runtime.py` (новый): `build_submission_service()` с реальным gateway, реестром проверенных компиляторов и писателем событий приёма. `submission.accepted` принимается и отбрасывается, потому что у него нет публичного payload-контракта (приватные поля нельзя отдавать в поток); любой другой тип отклоняется.
- `backend/config/settings.py`: `WORKSPACE_ACCESS_FACTORY`, `SUBMISSION_SERVICE_FACTORY`.
- Тесты: `problems/tests/test_workspace_api.py` (6), `submissions/tests/test_api_runtime.py` (3); два существующих теста («порт не задан → 503») теперь явно отключают фабрику через `override_settings`, их смысл сохранён.
- `backend/apps/submissions/README.md`: убрана устаревшая запись о неподключённых портах.
- `context/agents/agent-5.md`: запись среза. Миграций и контрактов v1 не менялось.

## Сверка с кейсом

P01/P02/P03 (условие, примеры, лимиты, переключение задач), E02 (языки из реально проверенных компиляторов), E03/E04 (доступ к посылкам и черновикам) — серверная часть; T12/T13 остаются partial.

## Проверки

| Команда или сценарий | Результат | Ограничения |
|---|---|---|
| `manage.py test` новых модулей | 9 тестов OK | |
| drafts + submissions + events + `test_match_api`, последовательно | 116 тестов, до правки двух тестов 2 FAIL, после правки оба OK | Полный набор после правки не повторялся последовательно |
| Параллельный прогон drafts/submissions/problems/competition/events без `test_archive`, `test_import_command` | не завершён: `pickle`-ошибка параллельного раннера маскирует результат на Windows | `test_import_command` падает на Windows до слияния #88 (O_BINARY) |
| `manage.py check` | без проблем | |

Не проверялось: реальный браузер и Docker; реальный компилятор `cpp20` остаётся `verified=False`, поэтому список языков на реальном каталоге пока пуст, а посылка отклоняется как неподдерживаемый язык.

## Решения и отклонения

Эндпоинт списка `GET /matches/{id}/problems` и `GET /problem-assets/{id}` не добавлялись: список задач уже есть в `GET /matches/{id}` (`problemVersions`), у демо-задач нет ресурсов; ресурсы остаются открытым пунктом. Писатель событий приёма отбрасывает `submission.accepted` осознанно, пока A4 не выпустит публичный producer.

## Блокеры и риски

- Реальная проверка компилятора (`verified=True`) и Docker Engine в этой среде отсутствуют: без них ни один язык не предлагается.
- Публичный producer `submission.accepted` / `submission.judged` — у A4.

## Передача следующему агенту

Следующий шаг (2/4): frontend рабочее место (P5-03c) на эти эндпоинты. Результат доступен только в feature-ветке до merge PR.
