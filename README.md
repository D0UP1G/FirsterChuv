# FirsterChuv

Веб-платформа для блиц-турниров по спортивному программированию: управление турниром на выбывание, рабочее место участника с проверкой кода и живая карта матча для зрителей.

## Текущее состояние

На проверенном develop `146b2cb` интегрированы backend, custom User, auth/CSRF/roles/bootstrap admin и tournament CRUD/roster/freeze (PR #2/#5/#8). 37 backend tests прошли при ревизии. Invites, интегрированный match/runtime, полноценный judge/worker, frontend и сквозное demo пока не integrated. Open PR #7 на a89b8fc содержит алгоритм/ORM/построение сетки, ещё без штатного подключения, PR #3 — sandbox harness с найденными дефектами запуска/протокольной границы. Полная приёмка MVP и безопасности не пройдена.

Точный снимок: [STATE](context/STATE.md). Все 9 PR, аудиты, команды и замечания: [ревизия 2026-10-09](docs/reviews/2026-10-09-repository-audit.md). Новый [план четырёх агентов](ROADMAP.md) даёт независимые READY задачи и отдельные CONNECT-шаги; [контракты v1](docs/architecture/parallel-contracts.md) позволяют писать UI/домены без ожидания соседних feature branches.

Локальный backend: Python 3.14 + uv, `.env.example` → `.env`, `./scripts/dev.sh`. Полный Compose запуск web/clock/judge пока не готов. У аккаунта global participant/admin; регистрация всегда participant. Только admin управляет турнирами. Первый admin: `./scripts/manage.sh create_admin` с защищённым вводом пароля; anonymous spectator будет смотреть через public API.

## Начать работу

1. Прочитать [инструкции для агентов](AGENTS.md).
2. Проверить [контекст проекта](context/PROJECT.md), [актуальное состояние](context/STATE.md) и собственную карточку в [context/agents](context/agents/README.md).
3. Выбрать задачу из [роадмапа для четырёх агентов](ROADMAP.md), прочитать контракт v1 и занять READY задание в своей карточке.
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
