# FirsterChuv

Веб-платформа для блиц-турниров по спортивному программированию: управление турниром на выбывание, рабочее место участника с проверкой кода и живая карта матча для зрителей.

## Текущее состояние

Auth/roles/CRUD/roster/invites, bracket/manual pairings/reset, clock/score/readiness/ledger cores, queue/worker/outboxes, normalized catalog, LocalJudge, drafts CAS и React editor/map интегрированы через #60/#61/#62. Полного рабочего MVP пока нет: требуется production run/gateway/providers/worker/sinks и реальный browser сценарий. #53/#57–59 требуют correctness fixes и пока не слиты. #63/#64/#65 reference/React бренд/mobile входят в текущую coordinator feature до её MERGED.

[ROADMAP v5](ROADMAP.md): три активных владельца — A4 (прежний A1) API/domain/events/common contracts, A3 judge/tasks/queue + config/Compose/startup/CI/acceptance, A5 весь frontend. Первым делаем [M0: реальный матч двух участников](docs/quality/m0-demo.md); полные обязательные блоки кейса остаются отдельной приёмкой. [STATE](context/STATE.md), [review/проверки](docs/reviews/2026-10-10-mvp-readiness.md), [contracts](docs/architecture/parallel-contracts.md), [handoffs](docs/architecture/runtime-handoffs.md), [дизайн](frontend/design/README.md).

## Начать работу

1. Прочитать [инструкции для агентов](AGENTS.md).
2. Проверить [контекст проекта](context/PROJECT.md), [актуальное состояние](context/STATE.md) и собственную карточку в [context/agents](context/agents/README.md).
3. Выбрать задачу из [роадмапа трёх владельцев](ROADMAP.md), прочитать контракт v1 и занять READY задание в своей карточке.
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
