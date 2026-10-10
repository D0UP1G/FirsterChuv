# Документация FirsterChuv

Документы задают контракты и приёмку. В develop имеются готовые auth/tournament/invite/bracket/draft/queue/judge/UI части, но полная production цепочка ещё не принята. [ROADMAP v5](../ROADMAP.md) распределяет три роли A3/A4(прежний A1)/A5; [M0](quality/m0-demo.md) — первый реальный матч, не полное выполнение кейса. [STATE](../context/STATE.md), актуальная ревизия.

| Документ | Что в нём |
|---|---|
| [Исходный PDF кейса](source/Кейс_Платформа_соревнований.pdf) | Первичный источник требований; сохранён с SHA-256 |
| [Брендбук BLITZ_ARENA](source/brandbook.md) | Визуальный стиль, палитра, шрифты и UI-концепция от команды; границы MVP — в decisions.md |
| [Требования](requirements.md) | Полное покрытие кейса, ограничения, баллы и владельцы |
| [Архитектура](architecture/README.md) | Карта архитектурных документов |
| [Решения](architecture/decisions.md) | Что выбрала команда и что пока является предложением |
| [Система](architecture/system.md) | Компоненты, границы, SQLite и будущие пути кода |
| [Данные](architecture/data-model.md) | Сущности, ограничения и индексы |
| [Сценарии](architecture/user-flows.md) | Регистрация, администратор, участник, зритель |
| [Матч и сетка](architecture/match-engine.md) | Состояния, таймер, правила результата, вмешательства |
| [Контракты параллельной работы](architecture/parallel-contracts.md) | DTO/порты/атомарные границы и fixtures v1 |
| [API](architecture/api.md) | REST, права и контракты |
| [Проверка кода](architecture/judging.md) | Собственный judge, очередь, sandbox, импорт |
| [События](architecture/realtime.md) | SSE и безопасные публичные DTO |
| [Безопасность](architecture/security.md) | Авторизация, код, секреты, недоверенные архивы |
| [GitFlow](operations/gitflow.md) | Ветки, PR, изолированные checkout и выпуск |
| [Запуск и защита](operations/runbook.md) | Целевой запуск, восстановление, демонстрация |
| [Приёмка](quality/mvp-acceptance.md) | Проверки MVP и доказательства выполнения |

План работ: [ROADMAP.md](../ROADMAP.md). Текущее состояние: [context](../context/README.md).

- [Передача production adapters и infra failure](architecture/runtime-handoffs.md).

- [Приёмка первого матча M0](quality/m0-demo.md).
