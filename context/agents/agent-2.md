# Агент 2: сетка и live backend

Карточка объединена координатором при повторной ревизии 2026-10-09 по запросу команды. Собственные аудиты исполнителя сохранены.

- В feature/mvp-integration-review-2 собраны pure clock PR #11 (28d6cda) и scoring PR #13 (19bbf88). Это проверенные малые срезы, до интеграции общего PR не являются кодом develop.
- PR #7 (1952244) остаётся открытым: archived/running/completed допускают generate/reset/pairing. Нужен lifecycle guard и regression до merge.
- PR #16 (8340014) остаётся открытым: SOLVED с lastVerdict WA после OK ошибочно отвергается; contract v1 допускает этот результат.
- Pure admin guards опубликованы в feature/match-admin-actions (8f5b762), отдельный PR пока отсутствует. ORM/HTTP/idempotency/event effects этим не реализованы.
- Следующие задачи: исправления #7/#16, затем persisted MatchRun/clock/API, CompetitionGatewayV1 ledger/results, public snapshots/SSE. Pure core не заменяет этот runtime.
- При зависимости продолжать следующую доступную задачу в своей зоне, оставлять WAITING_CONNECT только у конкретного подключения. Не завершать дорожку из-за отсутствия judge/UI.

[ROADMAP](../../ROADMAP.md), [v1](../../docs/architecture/parallel-contracts.md). Итог интеграции проверяется по GitHub MERGED и свежим refs; далее карточка будет дополнена общим планом ревизии.
