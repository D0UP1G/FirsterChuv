<!-- Статус интеграции: снимок в context/STATE.md. PR #78 (P4-07), #82 (P2-03.4), #84 (P1-03) интегрированы. Остальные целевые routes не означают реализованные endpoints. -->

> Актуальная передача 2026-10-10, ROADMAP v5: A4 (прежний A1) owns API/accounts/tournaments/competition/events/common contracts; A3 owns problems/submissions/drafts/judge/worker + config/Compose/CI/system acceptance; A5 весь frontend. A2 больше не активный producer. Старые датированные назначения ниже — история; поля v1 и принятые additive boundaries не меняются. Missing provider блокирует только CONNECT, не всю роль.
# API и права доступа

Целевой contract DRF API. Реализацию конкретных маршрутов сверять с [STATE](../../context/STATE.md) и аудиторскими evidence: наличие pure core/catalog не означает, что его HTTP route готов. PR #74 интегрировал private match read/config/manual-start; PR #77 — `CompetitionGateway`/`WorkspaceAccess`; PR #78 — public match snapshot; PR #82 — participant ready/body-bound receipts; PR #84 — unlisted share access. Production A3 consumer CONNECT, language route, admin API/browser CONNECT and full M0 remain separate slices. Префикс `/api/v1`, JSON camelCase, UUID, время RFC 3339 UTC. Django routes не должны молча перенаправлять POST из-за trailing slash; маршруты не имеют завершающего `/`.

Session auth через HttpOnly cookie и CSRF для mutations. `GET /auth/csrf` выдаёт `csrfToken` в JSON и HttpOnly CSRF cookie; frontend посылает `X-CSRFToken`. Register/login/logout имеют явную CSRF protection, не полагаются только на SessionAuthentication. Публичные GET не требуют login.

Обозначения: `A` — admin, `P` — authenticated participant, `Own` — автор/назначенный игрок с object access, `Public` — public visibility либо действующий unlisted share token. Админские права глобальные в предлагаемом MVP. Поведение admin-only endpoints не даёт admin автоматически право submit.

## Аккаунт и турнир

| Метод и путь | Право | Содержание |
|---|---|---|
| GET `/health` | Public | Минимальная readiness без secrets/version dump |
| GET `/auth/csrf` | Без login | Выдаёт `{csrfToken}` и HttpOnly cookie; `Cache-Control: no-store` |
| POST `/auth/register` | Без login + CSRF/rate limit | email/password/displayName, неизвестные поля отклоняются, роль всегда participant |
| POST `/auth/login` | Без login + CSRF/rate limit | Session; одинаковый 401 для неизвестного email, неверного пароля и inactive account |
| POST `/auth/logout` | Auth + CSRF | Инвалидировать session, 204 |
| GET `/me` | Auth | id/displayName/role; private cache no-store |
| GET `/admin/users?q=...&limit=...&offset=...` | A | Только active participant; ограниченный поиск, UUID/displayName без email, pagination |
| GET `/tournaments` | A / P | Admin все; participant только с активным roster membership; pagination |
| POST `/tournaments` | A | Создать турнир; `createdBy`, `status`, slug и roster state назначает сервер |
| GET `/tournaments/{id}` | A / joined P | Private management/member view; participant вне активного состава получает 404 |
| PATCH `/tournaments/{id}` | A | Whitelist полей и правила по status/freeze; неизвестные/read-only поля отклоняются |
| DELETE `/tournaments/{id}` | A | Нефрозеный draft удаляется; после freeze или lifecycle progress — архивируется, история не уничтожается |
| GET `/tournaments/{id}/participants` | A / joined P | Admin видит ACTIVE/REMOVED; P — active display names/seed, без private user fields |
| POST `/tournaments/{id}/participants` | A | `{userId, seed?}`, только active participant. Повтор той же assignment идемпотентен; другая seed требует PATCH |
| PATCH `/tournaments/{id}/participants/{userId}` | A | Только numeric seed или `null` до roster freeze |
| DELETE `/tournaments/{id}/participants/{userId}` | A | Логический remove до freeze; повтор идемпотентен. После freeze — 409; замена игравшего только через контролируемый match action |
| GET/POST `/tournaments/{id}/invites` | A | Список metadata / создание expiresAt/maxUses |
| DELETE `/tournaments/{id}/invites/{inviteId}` | A | Revoke |
| GET `/invites/{token}` | Без login + rate limit | Минимальные сведения/validity, не private roster |
| POST `/invites/{token}/accept` | P | Идемпотентное join, атомарное use/cap |

Invite API P1-01 (интегрирован PR #12): create принимает `expiresAt`, `maxUses` или оба; хотя бы один должен ограничивать ссылку. Ответ `201` содержит `{invite, token, url}`; случайный raw token возвращается только при создании, в БД хранится SHA-256. List — paginated metadata без token/hash, revoke — идемпотентный `204`. Preview возвращает только `{tournament:{id,title},valid:true,expiresAt}`, доступен без login и ограничен `30/minute`; неизвестный token — `404`, истёкший/отозванный/исчерпавший лимит — `410`. Accept требует активную authenticated роль participant и CSRF; первый успешный accept атомарно расходует use, создаёт roster entry и acceptance ledger, повтор возвращает `200` без повторного расхода. Freeze/status/cap conflict — `409`, use расход откатывается вместе с транзакцией. При кратком SQLite lock после bounded retry вернётся `503/database_busy`; транзакция откатывается, повтор может затем получить `410/invite_unavailable`. Invite ответы устанавливают `Cache-Control: no-store` и `Referrer-Policy: no-referrer`; full browser T04 ещё не пройден.

Не добавлять public endpoint смены роли. Bootstrap admin — management command. Если команда позже захочет admin role-management, это отдельное защищённое и аудируемое решение.

Успешная регистрация возвращает `201` с `{id, displayName, role}`; login возвращает тот же user summary и обновлённый `csrfToken` после session/CSRF rotation. Auth responses и `/me` имеют `Cache-Control: no-store`. Текущие scoped limits: register `20/hour`, login `10/minute` на клиентский IP; reverse proxy topology должна соответствовать `NUM_PROXIES` в settings. Account endpoints, базовые application-role permission probes и bootstrap command интегрированы PR #5 и покрыты tests; реальные admin tournament writes интегрированы PR #8. Roster интегрирован PR #8; participant-specific match ownership ещё не реализован; T02 остаётся открытым, а T20 не проходила как полный security suite.

Пример создания турнира:

```json
{
  "title": "Блиц 2026",
  "description": "Четыре задачи, один соперник",
  "startsAt": "2026-10-09T12:00:00Z",
  "endsAt": "2026-10-09T15:00:00Z",
  "format": "single_elimination",
  "participantLimit": 16,
  "visibility": "public",
  "matchDurationSec": 1200,
  "startMode": "manual",
  "scoringRule": {
    "order": ["solved_desc", "penalty_asc", "last_accepted_asc"],
    "wrongAttemptPenaltySec": 60,
    "penalizedVerdicts": ["WA", "TL", "ML", "RE"],
    "finalTiePolicy": "rematch"
  }
}
```

60 секунд здесь — пример выбора admin, не правило кейса. Для tournament defaults сервер требует `endsAt > startsAt`, `participantLimit >= 2`, поддерживает только `single_elimination`, а `visibility` — `public` или `unlisted`. `matchDurationSec` ограничен 60–7200 секундами; scoring order должен быть ровно `solved_desc`, `penalty_asc`, `last_accepted_asc`, штраф — 0–7200 секунд, penalized verdicts — уникальное подмножество WA/TL/ML/RE, final tie policy — `rematch`. Поля статуса/владельца и любые неизвестные ключи не принимаются из клиента. Match run snapshot immutable после старта.

В A1-03 mutation endpoints для tournament и roster защищены application role admin, session CSRF и `Cache-Control: no-store`. Directory возвращает только id/displayName active participant, без email. Tournament GET разрешён admin и active joined participant; поиск чужого/снятого private tournament возвращает 404. До roster freeze разрешены date/format/cap/config и roster changes. После freeze эти изменения закрыты; title/description/visibility остаются редактируемыми, пока турнир не перешёл в `running`, `completed` или `archived`. DELETE нефрозеного `draft` выполняет hard delete; в остальных случаях устанавливается `archived`. Полные T03/T05 остаются `NOT_RUN` до интегрированной browser/API-приёмки. Для T05 дополнительно требуется подтвердить сохранение уже сыгравшего entrant на реальном match history.

Participant `seed` принимает `null` или целое значение `1..2147483647`, уникальное среди активного состава одного турнира. Повтор активной assignment с тем же seed (или без seed) возвращает существующую запись; изменение seed — отдельный PATCH. POST/DELETE и active count изменяются в одной транзакции. Снятая запись остаётся в БД как `REMOVED`; повторный DELETE идемпотентен, повторная assignment до freeze реактивирует ту же строку.

`POST /tournaments/{id}/bracket/generate` вызывается агентом 2 в одной внешней `transaction.atomic()` с `backend.apps.tournaments.services.freeze_roster(tournament_id)`. Сервис возвращает active roster по seed ascending, null seed last, затем `userId` ascending; непосредственно перед генерацией он также проверяет active account и роль `participant` каждого entrant. Успешная генерация и frozen roster коммитятся вместе; ошибка проверки или создания bracket откатывает freeze. Freeze идемпотентен, требует минимум двух active participants, а любые последующие add/remove/seed изменения возвращают conflict. Match/bracket replacement после старта остаётся отдельным контролируемым action агента 2.

## Задачи и сетка

| Метод и путь | Право | Содержание |
|---|---|---|
| POST `/problem-imports` | A | Multipart official package, ограничения размера/путей, checksum |
| GET `/problem-imports/{id}` | A | Import status/errors без secrets |
| POST `/problem-imports/yandex` | A | Планируемое `{contestId, problemIds}`; server-config source, не arbitrary URL |
| GET `/problems` | A | Пагинированные версии и READY/NOT_READY; только public metadata/languages, без checksum и private artifacts; `limit` ограничен 100 |
| PUT `/tournaments/{id}/problems` | A | Набор готовых задач из пакета |
| POST `/tournaments/{id}/bracket/generate` | A | `{seedingMode: "manual"}`, atomic generation |
| PUT `/tournaments/{id}/bracket/pairings` | A | Полный первый раунд `{pairings:[{position,leftUserId,rightUserId}],reason}`, atomic; v1 уточняет DTO |
| POST `/tournaments/{id}/bracket/reset` | A | `{reason}`, idempotency key; только до первого start, тот же frozen roster |
| GET `/tournaments/{id}/bracket` | A / joined P | Bracket DTO, без source |
| PATCH `/matches/{id}` | A | Готовые задачи, duration/startMode до start; пары меняются отдельной атомарной командой первого раунда |
| GET `/matches/{id}/problems` | A / Own P | Meta до старта; condition только после start (admin может inspect) |
| GET `/matches/{id}/problems/{problemId}` | A / Own P | Markdown/public asset IDs/limits/examples |
| GET `/matches/{id}/problems/{problemId}/languages` | A / Own P | Только реально установленный compiler registry и templates |
| GET `/problem-assets/{assetId}` | Access to problem | Только разрешённый public asset, не путь к tests |

Import не запускает package scripts на хосте. Формат private tests/checkers определяется README пакета. Условия из Яндекса без полного local judge data не становятся READY.

## Матч и посылки

| Метод и путь | Право | Содержание |
|---|---|---|
| GET `/matches/{id}` | A / Own P | Текущий настроенный run/state/clock/rules и v1 match projection; private source/CE исключены |
| POST `/matches/{id}/ready` | Own P | Строго `{}` + `Idempotency-Key`; записать готовность, для `both_ready` второй сигнал запускает часы серверным временем; вернуть match v1 |
| POST `/matches/{id}/start` | A | Строго `{}` + `Idempotency-Key`; `READY/manual → RUNNING`, точный повтор возвращает исходный DTO |
| POST `/matches/{id}/pause` | A | `{reason}` |
| POST `/matches/{id}/resume` | A | Возобновление часов |
| POST `/matches/{id}/extend` | A | `{seconds, reason}`, bounded positive extension |
| POST `/matches/{id}/technical-result` | A | `{winnerUserId, reason}` |
| POST `/matches/{id}/rematches` | A | Новый run, `{reason, problemIds?}` |
| POST `/matches/{id}/replacements` | A | `{oldUserId, newUserId, reason}`, rules по состоянию |
| POST `/matches/{id}/submissions` | Own P + RUNNING | Сохранить допустимую source в queue → 202 |
| GET `/matches/{id}/submissions?problemId=...` | Own P | Только свои попытки, pagination, metadata/verdict |
| GET `/submissions/{id}` | Автор P | Own detail, bounded diagnostics |
| GET `/submissions/{id}/source` | Автор P | Только собственный source |
| GET/PUT `/matches/{id}/problems/{problemId}/draft?languageId=...` | Own P | user/run/problem/language draft + revision |

Match API slice P2-03.2:

- `PATCH /matches/{id}` принимает строго `{problemIds, matchDurationSec, startMode}`; `problemIds` — непустой список уникальных UUID, duration — integer `60..7200`, startMode — `manual|both_ready`. Обязателен `Idempotency-Key` и session CSRF. Только `DjangoProblemCatalog` с реально READY задачей/verified compiler создаёт immutable version/checksum/rules snapshot. Tournament scoring defaults копируются в run. Точный повтор actor/match/key/body возвращает сохранённый исходный DTO; reuse этого ключа с другим action/body даёт `409 idempotency_conflict`. Поле пар не принимается: используется PUT `/tournaments/{id}/bracket/pairings` целым первым раундом.
- `GET /matches/{id}` доступен admin или активному назначенному участнику. До настройки run возвращается `409 match_run_not_configured`; это ожидаемое состояние выбора матча, а не отсутствие route. Успех имеет форму `contracts/mvp-v1/match.json`, `Cache-Control: no-store`; score/task attempts берутся из accepted/result ledger текущего run. В приватный DTO добавлены `resolutionRequired` и `infrastructureFailures` с кодом из allowlist и `retryable`; diagnostics, source, checksum и private artifacts не читаются и не возвращаются. Terminal failure не становится verdict/поражением и не назначает автоматического winner; FINALIZING остаётся открытым для восстановления или ручного решения. `conditionAvailable` для участника становится true только после старта; admin может просматривать до старта.
- `POST /matches/{id}/start` принимает только `{}`, обязательный `Idempotency-Key` и manual run в READY. Эффект и receipt с hash ключа, actor/action/body digest и исходным DTO сохраняются одной транзакцией; exact retry возвращает тот же DTO и не сдвигает `started_at`. `both_ready` закрыт от ручного запуска; ответ — безопасный `409`.
- `POST /matches/{id}/ready` принимает только `{}` от активного назначенного participant с session CSRF. Неучастник/чужой UUID получает тот же `404`, admin не может отметить игрока готовым. В `manual` сигнал записывается без старта; в `both_ready` второй сигнал в транзакции переводит текущий run в `RUNNING` и начинает часы по времени сервера. Возвращается полный `match.json` DTO с `readyUserIds`; при ненастроенном матче — `409 match_run_not_configured`.
- Config/start/ready receipts scoped к `(match, actor, SHA-256(Idempotency-Key))`. Request hash включает action и канонический валидированный JSON body. Ключ ограничен 128 печатными UTF-8 байтами, не хранится в исходном виде. Эффект и response receipt атомарны; точный retry воспроизводит сохранённый payload, конфликт action/body возвращает `409`.
- Успешные private responses устанавливают `Cache-Control: no-store`. Время сервера UTC, clock elapsed вычисляется по сохранённому run и server time; client не присылает старт, длительность, score, winner или task snapshot.

Submission request требует `Idempotency-Key` header и `{runId, problemId, languageId, source}`. Server проверяет current run и разрешённый compiler; client не передаёт argv/image/timeouts/score. Один ключ с другим содержимым → 409, тот же запрос → тот же submission. Reply:

```json
{
  "submissionId": "00000000-0000-0000-0000-000000000001",
  "runId": "00000000-0000-0000-0000-000000000002",
  "status": "QUEUED",
  "verdict": null,
  "receivedAt": "2026-10-09T12:01:02.123Z",
  "elapsedMs": 62123
}
```

`QUEUED/RUNNING/RETRY_WAIT/FINISHED/INFRA_FAILED/CANCELLED` — process status; `OK/WA/TL/ML/RE/CE` — verdict только после реальной проверки. `INFRA_FAILED` не означает RE. До решения инфраструктурной проблемы матч может оставаться FINALIZING.

Draft PUT `{runId, source, expectedRevision}` возвращает новый revision. Conflict 409 содержит собственную server revision, чтобы frontend сохранил обе версии. Request limits на source и diagnostics фиксируются конфигурацией и UI; неверные значения отклоняются до queue.

## Публичное API и live

| Метод и путь | Право | Содержание |
|---|---|---|
| GET `/public/tournaments` | Public | Только public, pagination |
| GET `/public/tournaments/{id}/bracket` | Public | Сетка, statuses, scores; `{id}` — UUID турнира |
| GET `/public/matches/{id}` | Public | Anonymous public/unlisted snapshot; unlisted uses `X-Tournament-Share-Token`, `public-match` v1 allowlist |
| GET `/tournaments/{id}/share-links` | A | Share-link metadata only; no raw token or hash |
| POST `/tournaments/{id}/share-links` | A | CSRF; `{expiresAt}`; raw token returned once; link uses URL fragment |
| DELETE `/tournaments/{id}/share-links/{shareLinkId}` | A | CSRF; idempotent revoke |
| GET `/public/matches/{id}/events` | Public | SSE allowlist (`score.changed`, `match.admin_action`), Last-Event-ID, heartbeat/resync |

Unlisted read требует действующий tournament-scoped share grant. В БД хранится SHA-256; create endpoint показывает raw token один раз. Он передаётся через URL fragment (`/watch/{tournamentId}#shareToken=...`), который browser не отправляет серверу; frontend читает его и передаёт API заголовком `X-Tournament-Share-Token`. Query/path token transport не поддерживается. Unknown, чужой, истёкший и отозванный grant дают одинаковый 404. Grant даёт только read-only доступ и не является invite/membership. Public response устанавливает `Cache-Control: no-store` и `Referrer-Policy: no-referrer`. Public DTO не включает source, tests, checker, private email или CE diagnostics; public routes state не меняют.

Share management contracts: `GET /tournaments/{id}/share-links` returns an array of metadata `{id,tournamentId,expiresAt,revoked,createdAt}`. `POST` accepts only `{expiresAt}` and returns `201` once with:

```json
{
  "share": {
    "id": "<share-link-uuid>",
    "tournamentId": "<tournament-uuid>",
    "expiresAt": "<RFC-3339 UTC>",
    "revoked": false,
    "createdAt": "<RFC-3339 UTC>"
  },
  "shareToken": "<one-time secret>",
  "shareUrl": "/watch/<tournament-uuid>#shareToken=<one-time secret>",
  "accessHeader": "X-Tournament-Share-Token"
}
```

The fragment consumer must not copy the secret into query/path; send it only as the named header to a public read. `DELETE /tournaments/{id}/share-links/{shareLinkId}` returns 204 and may be retried. Share-link admin GET/POST/DELETE require active global admin; unsafe requests require CSRF. Raw token is absent from list/revoke responses.

## Ошибки и ограничения

Target response `{error: {code, message, fields?}, requestId}`. 400/422 — неверные поля; 401 — нет session; 403 — нет role; 404 — не существует/недоступный чужой private объект; 409 — conflict state/revision/idempotency/cap; 410 — expired/revoked invite; 413 — oversized; 429 — rate limit; 503 — временная недоступность до сохранения запроса. После 202 source уже persisted, infrastructure error выдаётся status объекта, не потерей данных.

DRF по умолчанию имеет собственный формат/особенности 401/403; агент 1 нормализует его явно. Message отображается как text, не HTML. Private responses `Cache-Control: no-store`. Admin writes, extension и rematch имеют command idempotency key, чтобы сетевой retry не повторял действия.

Role permission проверяется вместе с ownership/run state. Зарегистрированный participant другого турнира не имеет private доступа; known UUID не даёт право submit. Для changes whitelist serializer fields, нельзя mass-assign role/score/createdBy/winner из обычного DTO. Source/Markdown/URL всегда недоверенные данные.

## Уточнение и текущие маршруты после новой ревизии 2026-10-10

#50 реализует admin PUT /tournaments/{id}/bracket/pairings и POST /tournaments/{id}/bracket/reset с reason и Idempotency-Key. #74 реализует match GET/config/manual-start; #76 добавил durable submission ledger/finalization/admin effects; #82 реализует participant ready route и body-bound receipts; #84 интегрирует share links/PublicAccess для public и unlisted snapshot reads. A3 workspace provider CONNECT, language/condition endpoints and browser/system acceptance остаются отдельными slices. #21 private draft CAS исправлен; endpoint требует WorkspaceAccess: GET /matches/{id}/problems/{problemId}/draft?runId=...&languageId=...; missing record 404, PUT body прежний. [Selector принят координатором](../../context/contracts/2026-10-10-mvp-boundaries.md).

P2-04 через PR #76 добавил durable accepted/result/failure ledger и pending-aware finalization. A4 P2-03.3 в отдельной feature реализует provider `backend.apps.competition.gateway.DjangoCompetitionGateway`: его factory пути — `get_competition_gateway` и `get_run_problem_snapshot_provider`. Он проверяет активное членство, actor из frozen run roster, assignment задачи, current run и server deadline для submit; version/checksum возвращаются только по `runId` из immutable run snapshot. `authorize_workspace` выдаёт actions по purpose, не допускает admin к draft/source и не открывает participant condition до старта. Provider не считается production-connected до A3 factory/startup/consumer CONNECT; browser/M0 остаётся NOT_ACCEPTED.
