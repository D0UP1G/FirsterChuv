# Запрос A3: pinned version задачи в WorkspaceContext

- Статус: `WAITING_CONNECT` — запрос не меняет v1 контракт без согласования владельца A2/команды.
- Автор/потребитель: агент 3, P3-02.2 workspace endpoints.
- Производитель: агент 2, CompetitionGatewayV1.
- Основание: frozen task selection каждого match run и immutable ProblemVersion в A3 каталоге.

## Текущий контракт

`CompetitionGatewayV1.authorize_workspace(actorId, matchId, runId, problemId, purpose)` возвращает `WorkspaceContext` с `actorId`, `runId`, `problemId`, `allowedActions` и `conditionAvailable`. Он авторизует доступ, но не сообщает, какая immutable версия задачи зафиксирована в run.

## Предложение

Добавить в `WorkspaceContext` nullable optional поля `problemVersion: string | null = null` и `problemChecksum: string | null = null`. A2 заполняет их значениями из immutable task snapshot именно этого `runId`. A3 сверяет `(problemId, problemVersion)` и checksum с `ProblemCatalogV1.load_bundle` до выдачи statement, public assets или language templates.

`null` сохраняет source compatibility для v1 consumers, но A3 должен fail closed с readiness/integration error для condition/assets/languages. Нельзя подменять поля active latest version или принимать версию от браузера. A2 должен подтвердить наличие version/checksum в snapshot или указать отдельный immutable source.

## Потребители, совместимость и проверки

- Затронуты: A2 producer и его snapshot/store; A3 statement/asset/language endpoints; contract examples/tests.
- Это additive nullable DTO field, не изменение аргументов `authorize_workspace` и не runtime provider implementation. После решения обновить `parallel-contracts.md`, dataclass/schema examples и A2/A3 tests одним согласованным contract slice.
- Acceptance: match run pinned к v1 продолжает возвращать v1 после публикации v2; checksum mismatch отказывает закрыто; чужой actor/problem/run не получает statement/assets; ни один ответ не содержит tests/checker/reference/source.

## Независимая работа

Пока ждёт ответа, можно реализовывать admin catalog/import services, strict parser, compiler readiness и собственные API tests. Participant workspace endpoints по этому подпункту остаются `WAITING_CONNECT`.
