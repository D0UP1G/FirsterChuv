# Запрос контракта: выбор run для GET черновика

- Автор: agent 3, задача P3-05.
- Статус: `PROPOSED`, решение координатора не зафиксировано.
- Связанные требования: E04/S02; T15/T20 остаются приёмкой, не закрытой этим запросом.
- Документы: `docs/architecture/api.md` (таблица draft route), `docs/architecture/parallel-contracts.md` (`authorize_workspace`, namespace draft), `contracts/mvp-v1/draft.json`.

## Текущее состояние

HTTP-таблица задаёт `GET/PUT /matches/{id}/problems/{problemId}/draft?languageId=...`; тело `PUT` содержит `runId`, `source`, `expectedRevision`. Одновременно draft хранится по ключу user/run/problem/language, а общий `CompetitionGatewayV1.authorize_workspace` требует `runId` для обоих методов. Как GET выбирает run, контракт явно не говорит.

## Предложение

Добавить `runId` как обязательный query-параметр только для `GET`, рядом с `languageId`. A2 gateway проверяет, что run принадлежит match и разрешён авторизованному участнику. `PUT` остаётся без изменения: `runId` в body, `languageId` в query. Не добавлять history route и не менять форму `draft.json`.

Для отсутствующего сохранённого черновика определить GET `404` с обычным error envelope. Fixture schema требует положительную `revision` и RFC 3339 `updatedAt`, поэтому не возвращать фиктивный пустой draft с revision `0` и `updatedAt: null`; первая запись использует `expectedRevision: 0` и создаёт revision `1`.

## Совместимость и потребители

Предложение уточняет отсутствующий selector GET и семантику отсутствующей записи, не меняя DTO сохранённого draft и shape `PUT`. До появления production A2 adapter endpoint остаётся fail-closed (`503`). P4-04 должен передавать выбранный run и трактовать `404` как пустой editor; A2 должен сверять run через свой gateway. До принятия запроса feature PR не следует считать доказательством полной API/browser-интеграции.

## Независимая работа и fallback

P3-05 storage, CAS revisions, приватная история, auth guards и tests используют уже опубликованный `WorkspaceContext`/actions. Их можно review независимо. Fallback для HTTP wiring — не выводить run из недоверенного client ID без проверки gateway; если предложенная форма будет отклонена, согласовать иной способ получить текущий run до подключения P4-04.
