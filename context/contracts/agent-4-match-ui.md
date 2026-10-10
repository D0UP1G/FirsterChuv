# Запрос контракта Agent 4: match admin UI

- Дата: 2026-10-09.
- Статус: предложения потребителя; A4 принимает и реализует пункты 1–2 как собственный match API contract в P2-03.2. Пункты 3–4 сохраняют целевую семантику bracket endpoints; browser integration остаётся у A5.
- Задача: P4-03, React admin bracket/match UI.
- Причина: `docs/architecture/api.md` объявляет GET `/problems` и PATCH `/matches/{id}`, но не фиксирует list/config DTO; v1 schemas фиксируют match snapshot, не каталог доступных версий.

## Предложение

1. `GET /problems?limit=100&offset=0` возвращает обычную страницу `{count,next,previous,results}`. Элемент `results` содержит только `{problemId,label,version,readiness}`, где `readiness` — `READY` или `NOT_READY`. Public statement и private tests/checker/reference в каталоге не нужны. UI разрешает выбрать только `READY`.
2. До запуска `PATCH /matches/{id}` принимает `{problemIds:string[],matchDurationSec:number,startMode:"manual"|"both_ready"}`. `problemIds` — уникальные UUID готовых immutable versions; длительность — 60–7200 секунд. Scoring defaults берутся из турнира и копируются в run snapshot. Неизвестные поля отклоняются.
3. GET `/tournaments/{id}/bracket` до создания сетки возвращает 404 envelope с кодом `bracket_not_found` (допустимое эквивалентное имя: `bracket_not_generated`). Отсутствие самого endpoint остаётся отдельной ошибкой API и отображается как недоступность интеграции.
4. Повтор `POST /bracket/generate` для уже созданной сетки возвращает её без создания новых match IDs. POST/PUT/PATCH команд используют session CSRF и `Idempotency-Key`; v1 payload для полных пар и action endpoints остаётся совместимым.

## Совместимость и затронутые потребители

- Каталог — additive read projection для A4; поля ID/label/version совместимы с `contracts/mvp-v1/schemas.json` `$defs.problemVersion`. Readiness используется только до включения версии в матч.
- A4 — владелец API авторизации, competition lifecycle, scoring snapshot, часов, готовности и idempotency. UI не решает победителя и не выбирает judge verdict.
- A3 ProblemCatalog остаётся источником READY; каталог не раскрывает private bundle. Frontend передаёт выбранные version IDs, не statement content.
- A4 production transport всегда использует HTTP. Синтетические данные доступны только при `import.meta.env.DEV` и явном `scenario=match-ui`; production build не включает этот transport и не переключается на fixtures при ошибке HTTP.

## Fallback

Пока endpoint или уточнение не интегрированы в `develop`, экран показывает полученную API ошибку. UI не отправляет отдельные PATCH на пару, не подменяет live данные dev-сценариями и не выдаёт mock run/score/verdict за работающий MVP.
