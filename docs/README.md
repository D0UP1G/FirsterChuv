# Документация FirsterChuv

Документы задают контракты и критерии приёмки. В `develop` есть backend bootstrap и auth; в feature-ветке Agent 1 добавлены tournament CRUD и roster assignment/list/remove A1-03.1/.2. Ни один частичный срез сам по себе не означает готовность MVP: проверяйте `context/STATE.md`, карточки/аудиты и полный сценарий нужного требования. Подтверждённый стек: Django REST Framework + React, SQLite3, собственная песочница.

| Документ | Что в нём |
|---|---|
| [Исходный PDF кейса](source/Кейс_Платформа_соревнований.pdf) | Первичный источник требований; сохранён с SHA-256 |
| [Требования](requirements.md) | Полное покрытие кейса, ограничения, баллы и владельцы |
| [Архитектура](architecture/README.md) | Карта архитектурных документов |
| [Решения](architecture/decisions.md) | Что выбрала команда и что пока является предложением |
| [Система](architecture/system.md) | Компоненты, границы, SQLite и будущие пути кода |
| [Данные](architecture/data-model.md) | Сущности, ограничения и индексы |
| [Сценарии](architecture/user-flows.md) | Регистрация, администратор, участник, зритель |
| [Матч и сетка](architecture/match-engine.md) | Состояния, таймер, правила результата, вмешательства |
| [API](architecture/api.md) | REST, права и контракты |
| [Проверка кода](architecture/judging.md) | Собственный judge, очередь, sandbox, импорт |
| [События](architecture/realtime.md) | SSE и безопасные публичные DTO |
| [Безопасность](architecture/security.md) | Авторизация, код, секреты, недоверенные архивы |
| [GitFlow](operations/gitflow.md) | Ветки, PR, четыре checkout и выпуск |
| [Запуск и защита](operations/runbook.md) | Целевой запуск, восстановление, демонстрация |
| [Приёмка](quality/mvp-acceptance.md) | Проверки MVP и доказательства выполнения |

Назначения четырёх агентов: [ROADMAP.md](../ROADMAP.md). Текущая работа и аудиты: [context](../context/README.md).
