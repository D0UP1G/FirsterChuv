# Документация FirsterChuv

Документы описывают будущую архитектуру. Реализация не начата; готовность подтверждается кодом и приёмкой, а не этими файлами. Подтверждённый стек: Django REST Framework + React, SQLite3, собственная песочница.

| Документ | Что в нём |
|---|---|
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
