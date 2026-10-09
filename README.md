# FirsterChuv

Веб-платформа для блиц-турниров по спортивному программированию: управление турниром на выбывание, рабочее место участника с проверкой кода и живая карта матча для зрителей.

## Текущее состояние

В `develop` есть backend bootstrap, custom User, health endpoint, account endpoints register/login/logout/me с CSRF, глобальные application-role permissions и защищённая management command первоначального admin. В текущей feature-ветке `feature/tournament-roster` добавлен A1-03.1: admin-only tournament CRUD; он ещё не интегрирован, roster и приглашения не завершены. Ограниченные backend checks прошли, но полная приёмка запуска и безопасности не пройдена. UI, сетка, judge, worker commands и сквозной сценарий ещё не готовы; это не demo-версия. Целевую инструкцию запуска добавит агент 1 после проверки полного сценария.

Для локальной разработки backend нужны Python 3.14 и uv. Скопируйте `.env.example` в `.env`, затем запустите `./scripts/dev.sh`. Для текущего feature среза прошли backend tests, Django checks и migration drift check; ранее на feature-ветках Agent 1 проверены SQLite WAL, dev server, API image/health и account auth. Это ограниченные проверки, а не полная T01 или security acceptance: roster, UI, workers, official package и sandbox ещё не готовы. Полный запуск через Compose, `web` и профили `runtime` пока не готов.

У аккаунта одна глобальная роль: `participant` или `admin`. Регистрация всегда выдаёт `participant`; public role promotion запрещён. Начальный admin создаётся через `./scripts/manage.sh create_admin` с интерактивным паролем или защищённой secret injection; повторный запуск не меняет пароль существующего admin. По целевому правилу только `admin` сможет создавать и редактировать турниры. Публичный просмотр турнира будет доступен без регистрации.

## Начать работу

1. Прочитать [инструкции для агентов](AGENTS.md).
2. Проверить [контекст проекта](context/PROJECT.md), [актуальное состояние](context/STATE.md) и собственную карточку в [context/agents](context/agents/README.md).
3. Выбрать задачу из [роадмапа для четырёх агентов](ROADMAP.md), проверить её зависимости и занять её в своей карточке.
4. Создать `feature/<краткое-название>` от актуальной `develop`. Работа идёт строго по [GitFlow](docs/operations/gitflow.md).
5. После работы записать отдельный [аудит](context/audits/README.md), обновить свою карточку и создать PR в `develop`.

## Документация

- [Навигация по документации](docs/README.md).
- [Требования кейса и их покрытие](docs/requirements.md).
- [Исходный PDF кейса](docs/source/Кейс_Платформа_соревнований.pdf) в репозитории.
- [Архитектура и решения](docs/architecture/README.md).
- [API и права доступа](docs/architecture/api.md).
- [Пользовательские сценарии](docs/architecture/user-flows.md).
- [Приёмка MVP](docs/quality/mvp-acceptance.md).
- [Развёртывание и защита](docs/operations/runbook.md).

## MVP

Администратор создаёт турнир и приглашение, участники входят по ссылке, запускается матч, реальная посылка получает вердикт, зритель видит событие на карте, победитель автоматически проходит дальше по сетке. Обязательные требования кейса, включая ручные вмешательства и автоматический запуск, перечислены в матрице требований. Дополнительные форматы и другие улучшения вынесены за пределы MVP.

Команда выбрала Django REST Framework + React, SQLite3 и собственную песочницу для проверки решений (вариант Б кейса). Яндекс Контест используется только для планируемого импорта задач. Предлагаемые компоненты интерфейса: TypeScript, Monaco Editor и SSE. Подробные [решения и ограничения](docs/architecture/decisions.md) нужны агентам перед реализацией.

Репозиторий: [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv).
