# Корректировка аудита: Agent 4 / P4-06 catalog contract

- Автор/роль: Agent 4 — React, редактор и пользовательские сценарии.
- Время: `2026-10-09T23:10:00+03:00` — `2026-10-09T23:12:02+03:00` (Europe/Moscow).
- Связанная запись: [аудит синхронизации и выбора CONNECT](2026-10-09T231000+0300-agent-4-P4-06-develop-sync.md).
- Задача: P4-06, проверка каталога `GET /problems` в API client/MatchAdminTransport.
- Ветка: `feature/browser-api-integration`; develop — `6320b4bb75a0dbc5284946cb0161cb1842d15847`.
- Статус: исходное предположение исправлено до изменений frontend API-кода; next-step contract test ещё не выполнен.

## Исправление факта

В предыдущем аудите утверждалось, что endpoint возвращает `problem_id`, тогда как frontend ждёт `problemId`. Это было сделано только по именам serializer fields и до чтения активного renderer. Утверждение неверно: `backend/config/settings.py` устанавливает `backend.apps.common.api.CamelCaseJSONRenderer`; он рекурсивно проходит по mappings/lists и превращает ключи serializer `problem_id`/`time_limit_ms` в `problemId`/`timeLimitMs`. API тест каталога уже подтверждает wire casing ключом `isActive`.

`api.readyProblems()` запрашивает `/problems?limit=100&offset=0`, возвращает `Page<ProblemCatalogEntry>`, а HTTP MatchAdminTransport использует `results`. Поэтому casing adapter не нужен. Вместо него следующий тестовый срез должен зафиксировать фактическую страницу и только нужную UI projection (`problemId`, `label`, `version`, `readiness`), сохранить `count/next/previous` и доказать, что отказ API не переключает production transport на fixtures. Production code до этого подтверждения не менялся.

## Что остаётся верным из предыдущей записи

- PR #32 merged в `develop` на exact SHA `6320b4b`; route доступен только application admin, использует limit/offset pagination и ставит `Cache-Control: no-store`.
- Participant statement/language, run/draft workspace, bracket lifecycle, public snapshot/SSE и real worker/result integration остаются отдельными зависимостями.
- Ветка синхронизирована обычным merge; общая `context/STATE.md` и чужие ветки не менялись.

## Проверки

| Проверка | Результат | Ограничения |
|---|---|---|
| `backend.apps.common.api` | `CamelCaseJSONRenderer` рекурсивно конвертирует mapping keys и элементы nested lists | Source inspection на текущем feature/develop merge. |
| `backend/config/settings.py` | Renderer включён через DRF `DEFAULT_RENDERER_CLASSES` | Это приложение серверного контракта; не отдельный HTTP запрос. |
| `backend/apps/problems/tests/test_catalog_api.py` | Wire test обращается к `isActive`, что подтверждает camelCase renderer | Тест не проверяет поле `problemId` непосредственно. |
| `frontend/src/matches/transport.ts`, `frontend/src/api/client.ts` | Уже подключён production HTTP transport `/problems?limit=100&offset=0`; fixtures включаются только явным DEV `scenario=match-ui` | Полный AdminMatchPage всё ещё зависит от bracket/match endpoints. |

## Передача

Сохранить эту корректировку отдельной записью, не переписывая исходный аудит. Следующий Agent 4 feature от свежего `origin/develop` добавит регрессионные тесты существующего catalog client/projection и ошибки без fallback; не менять backend renderer или A3 serializers. После проверки снова свериться с T06/T07/T20 и точным endpoint SHA. Полный browser scenario и кейсовая приёмка остаются `NOT_RUN`.
