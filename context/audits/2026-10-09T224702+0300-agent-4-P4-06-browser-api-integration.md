# Аудит: Agent 4 / P4-06 browser API integration

- Автор/роль агента: Agent 4, пользовательские интерфейсы, редактор и зрительская карта.
- Начало и окончание: `2026-10-09T22:21:43+03:00` — `2026-10-09T22:47:02+03:00` (Europe/Moscow; продолжение после P4-05 merge/start checkpoint).
- ID задач: P4-06; M01–M03; E04, V01–V04 и T20 — частичная проверка.
- Ветка: `feature/browser-api-integration`.
- Исходная база P4-06: `13cd2d44c629a921481b9e70cb284fdeca264c81`.
- Синхронизация GitFlow: `origin/develop` продвинулся PR #25 до `ed14416fee0d1cccbd0b9a202e563d49f062572a`; он влит в feature обычным merge `b1a4e260ca18c01e540a76f73b80a15dff9c6055`. Конфликтов не было.
- Статус: `IN_PROGRESS`; доступный browser slice проверен, runtime CONNECT остаётся частичным.
- PR / последующие коммиты: будет добавлен после публикации.

## Цель и исходное состояние

P4-06 требует проверять каждый интегрированный endpoint отдельным browser scenario на exact SHA: admin, две participant sessions и anonymous spectator. Начальный рабочий путь должен включать создание/приглашение, старт матча, editor, submission, вердикт, score и promotion. Исходная база `13cd2d44` включала auth/tournament/invite API, но public match/events, drafts, submission и problem endpoints не были смонтированы.

Во время работы `origin/develop` продвинулся PR #25. Изменение было изучено, fetched и влито в feature обычным GitFlow merge. PR #25 добавляет проверку, что private checker/validator/reference language ID является зарегистрированной строкой или `null`; URL/API routes он не меняет. Текущий route registry по-прежнему содержит auth и tournaments; participant problem/language routes, drafts, submissions, public events и bracket runtime отсутствуют. Открытые PR #7, #15, #16, #21, #23 и #26 не использовались как production dependencies.

Сверены `AGENTS.md`, `context/PROJECT.md`, `context/STATE.md`, карточка Agent 4, ROADMAP v3, матрица требований и исходный кейс. Страницы 5–6 кейса требуют редактор, сохранение при reload/task switch, живую зрительскую карту, попытки/verdicts и обновление WebSocket/SSE. Локальные fixtures не засчитываются как полноценная runtime приёмка.

## Выполненные изменения

- `frontend/src/spectator/SpectatorMapPage.test.tsx`: regression test передаёт недоверенный HTML-подобный title и displayName через dev transport и проверяет, что React отображает строки как текст и не создаёт `img` DOM node.
- `frontend/src/workspace/transport.test.ts`: HTTP consumer test проверяет, что draft GET с ожидаемыми match/problem/run/language параметрами трактует 404 как отсутствие сохранённой записи, а 503 `integration_unavailable` остаётся ошибкой.
- `context/agents/agent-4.md`: зафиксированы выполненный browser slice, точная синхронизация с develop, ограничения, зависимости и риски.
- `context/STATE.md`, backend/apps, API contracts и чужие feature branches не изменялись.

Browser smoke выполнен в локальном frontend/backend на disposable SQLite, с синтетическими учётными записями и отдельными host-specific browser sessions:

- Admin создал турнир через UI и реальный API (`POST /api/v1/tournaments` → 201), затем invite с лимитом 2 (`POST .../invites` → 201).
- Anonymous invite preview показал только название турнира и состояние ссылки; roster/email/source не показывались.
- Два участника зарегистрировались и приняли ссылку каждый в отдельной browser session. Admin UI показал roster `2/4`; список invite показал исчерпанный лимит `2/2`.
- Anonymous `/watch/<tournament-id>` без dev scenario показал unavailable для отсутствующего public endpoint; login wall не появился.
- Participant `/matches/<id>` без dev scenario не открыл fixture workspace и показал fail-closed not-found/integration state.
- Admin bracket/match route без dev scenario показал недоступность match/bracket endpoint.

## Проверки

| Команда или сценарий | Результат | Ограничения |
|---|---|---|
| `npm run typecheck` | exit 0 | После исправления matcher option в spectator test; повторно пройдена после добавления transport test. |
| `npm run lint` | exit 0 | 5 прежних `react(set-state-in-effect)` warnings в P4-04 (`useDraftController.ts:159`, `ParticipantWorkspacePage.tsx:152,157,202,243`). |
| `npm test` | 16 files / 63 tests passed | DOM/unit suite не заменяет backend/SSE acceptance. |
| Повторный одновременный запуск четырёх frontend checks | typecheck, lint и build завершились успешно; `npm test` получил три timeout по 5 секунд | При отдельном повторе `npm test` прошёл: 16 файлов / 63 теста за 9.42 с; код тестов не менялся. |
| `npm run build` | Успешно | Существующий CodeEditor chunk 612.84 kB превышает 500 kB warning threshold. |
| `git diff --check` | Успешно | Проверена чистота пробелов. |
| Browser smoke по auth/tournament/invite | Создание, preview, две регистрации/accept и roster/cap подтверждены через UI и реальные endpoints | Синтетические записи жили только в disposable SQLite. Не проверяет match/runtime путь. |
| Match/workspace/public production routes | Отсутствующие endpoints показывают unavailable/not-found; dev fixtures не включены | Реальные bracket/start/draft/submission/problem/SSE providers отсутствуют в `develop`. |
| GitFlow sync | `origin/develop` PR #25 `ed14416` merged в feature-коммит `b1a4e260`; merge без конфликтов | `develop` не переключался и напрямую не изменялся. |

## Сверка с кейсом и границы

- M01–M03: доступный auth/CRUD/invite browser slice подтверждён; freeze/seed/removal и полная hostile/object access матрица здесь не закрыты.
- E04: локальная draft persistence существует в интегрированном frontend. Draft consumer уже передаёт `runId` и `languageId`; PR #21 предлагает именно этот GET selector и 404 для отсутствующей записи, так что Agent 4 потребительски совместим. Сам запрос #21 остаётся `PROPOSED`, решение координатора не зафиксировано, PR открыт и основан на более старом SHA `ae0846b`; server draft/reload/task-switch CONNECT не выполнялся.
- Problem catalog: PR #26 предлагает только admin `GET /problems`, основан на более старом SHA `505a2bc` и открыт. Его body явно не добавляет participant statement/language endpoints; контракт workspace problem version/checksum остаётся `WAITING_CONNECT`. Подключать каталог к participant editor нельзя.
- V01–V04/T16–T17: P4-05 UI/dev fixture интегрирован PR #29, но реальные anonymous snapshot/bracket/SSE и reconnect остаются partial до PublicAccess A1 и P2-06.
- T20: добавлен regression для публичного отображения пользовательского текста. Он не закрывает server privacy, IDOR, CSRF, unsafe URL или hostile API matrix; безопасная sanitizer-проверка Markdown условия уже есть в `ProblemStatement.test.tsx`.
- R1 путь заканчивается до match start, editor на реальных задачах, submission/verdict/score/promotion. Нельзя объявлять P4-06 или MVP выполненным.

## Решения, ограничения и риски

- Не подключал PR #7/#15/#16/#21/#23/#26: это открытые feature PR, а не integrated `develop`. Для PR #21/#26 дополнительно проверено, что их base SHA устарел; после merge каждого provider сделать fetch и повторный CONNECT на точном SHA.
- PR #25 уже слит. Его private artifact language validation не является participant language registry/API и не меняет editor CONNECT.
- Во время локального smoke dev runserver вывел invite path token в access-log строку. Значение не копировалось в файлы/аудит; disposable DB удалена. Исправление access-log redaction относится к P1-03/A1; backend здесь не менялся.
- Browser smoke использовал `localhost:8081`; cookies не разделяются по порту, поэтому прежняя host-only `localhost` session могла быть заменена синтетической. Исходное значение cookie не сохранялось, восстановить его из теста нельзя. Созданные smoke вкладки закрыты.
- Django/Vite процессы остановлены; временный Vite config и disposable SQLite удалены. Скриншот browser smoke как файл не сохранён; доказательствами служат ручные наблюдения страницы и HTTP статусы. Синтетические invite token/credentials в аудит не включены.
- `context/STATE.md` не менялся.

## Передача следующему шагу

Оставить P4-06 в `IN_PROGRESS`. После следующего подходящего provider merge выполнить fetch, проверить актуальный contract и провести отдельный exact-SHA browser CONNECT. Порядок доступных потребительских срезов: admin problem catalog после #26 merge; draft GET/PUT после contract decision, PR #21 sync/merge и A2 WorkspaceAccess; submission после #15 + LocalJudge/provider; public map после PublicAccess A1 и P2-06 HTTP/SSE. Полные R1–R3 и T01–T21 остаются незакрытыми.
