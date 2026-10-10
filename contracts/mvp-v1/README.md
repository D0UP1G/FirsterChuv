# Примеры контрактов v1

Владелец общей спецификации: координатор; распределение файлов — в ROADMAP. JSON здесь — собственные synthetic примеры для изолированной разработки и проверок. Они не содержат реальные аккаунты/посылки, не являются official package и не подтверждают готовность endpoint. Runtime/demo не использует эти данные как результат проверки.

Основание: [parallel-contracts](../../docs/architecture/parallel-contracts.md), [REST](../../docs/architecture/api.md), [SSE](../../docs/architecture/realtime.md).

`roster.json` содержит вход и ожидаемый порядок adapter, остальные файлы — response/event examples. User UUID одинаковы в roster/bracket/match/public snapshot, problem/run/submission IDs согласованы. public-match/score-event запрещено расширять private source, email, CE logs или secret test data. `draft.json` намеренно private. Invite token заведомо synthetic/non-working.

A4 копирует/загружает примеры только в dev/test entrypoint, не создаёт fallback mock в production HTTP client. Backend использует их для contract tests, а не для JudgeProvider. Полный enum/state/error contract задаёт документация; один пример не покрывает все варианты.

`schemas.json` описывает строгие JSON Schema Draft 2020-12 для всех девяти fixtures. Каждый объект закрыт от незадокументированных полей, включая публичные `public-match` и `score-event`. Проверить примеры локально: `uv run --locked python scripts/check_contracts.py`. Эта проверка подтверждает только форму synthetic DTO и не заменяет API/browser/security acceptance.
