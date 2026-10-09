# FirsterChuv

Веб-платформа для блиц-турниров по спортивному программированию: управление турниром на выбывание, рабочее место участника с проверкой кода и живая карта матча для зрителей.

## Текущее состояние

Актуальная ревизия 2026-10-10: интегрированы auth/roles/CRUD/roster/invites, bracket foundation, clock/score/readiness/ledger cores, queue/worker/outboxes, LocalJudge и React UI. Новые проверенные draft CAS, pairings/reset API, frontend CI и BLITZ_ARENA design references входят в coordinator integration feature до её MERGED. Полного рабочего MVP пока нет: нужно подключить real match/run/gateway/ledger/providers и public HTTP/SSE; #53 snapshot имеет два correctness blockers.

Точный снимок и gate: [STATE](context/STATE.md), [новая ревизия и покрытие кейса](docs/reviews/2026-10-10-mvp-readiness.md). [ROADMAP v4](ROADMAP.md) распределяет пять владельцев: A1 платформа/запуск, A2 competition/runtime, A3 judge/workspace, A4 events/SSE/приёмка, новый A5 весь frontend/брендбук. [Контракты v1](docs/architecture/parallel-contracts.md), [runtime handoffs](docs/architecture/runtime-handoffs.md) и [принятые уточнения](context/contracts/2026-10-10-mvp-boundaries.md). Дизайн — [frontend/design](frontend/design/README.md), без runtime verdicts.

## Начать работу

1. Прочитать [инструкции для агентов](AGENTS.md).
2. Проверить [контекст проекта](context/PROJECT.md), [актуальное состояние](context/STATE.md) и собственную карточку в [context/agents](context/agents/README.md).
3. Выбрать задачу из [роадмапа пяти владельцев](ROADMAP.md), прочитать контракт v1 и занять READY задание в своей карточке.
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

Команда выбрала Django REST Framework + React, SQLite3 и собственную песочницу для проверки решений (вариант Б кейса). Яндекс Контест используется только для планируемого импорта задач. Текущий frontend использует TypeScript, CodeMirror 6 и безопасный Markdown/TeX renderer; SSE transport ещё подключается. Подробные [решения и ограничения](docs/architecture/decisions.md) нужны агентам перед реализацией.

Репозиторий: [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv).
