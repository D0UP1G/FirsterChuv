# API и права доступа

Целевой contract DRF API. A1-01 реализовал платформенную основу, A1-02 — auth slice, A1-03.1/.2 в feature-ветке добавили admin-only tournament CRUD, participant directory и roster API. Capacity/freeze hardening остаётся в A1-03.3. Префикс `/api/v1`, JSON camelCase, UUID, время RFC 3339 UTC. Django routes не должны молча перенаправлять POST из-за trailing slash; в A1-01 выбран вариант без завершающего `/`. В этом документе пути указаны без slash.

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

Не добавлять public endpoint смены роли. Bootstrap admin — management command. Если команда позже захочет admin role-management, это отдельное защищённое и аудируемое решение.

Успешная регистрация возвращает `201` с `{id, displayName, role}`; login возвращает тот же user summary и обновлённый `csrfToken` после session/CSRF rotation. Auth responses и `/me` имеют `Cache-Control: no-store`. Текущие scoped limits: register `20/hour`, login `10/minute` на клиентский IP; reverse proxy topology должна соответствовать `NUM_PROXIES` в settings. Account endpoints, базовые application-role permission probes и bootstrap command покрыты тестами в `feature/account-roles`; реальные admin tournament writes добавлены в `feature/tournament-roster`. Roster и participant-specific match ownership ещё не интегрированы; T02 остаётся открытым, а T20 не проходила как полный security suite.

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

В A1-03.1/.2 mutation endpoints для tournament и roster защищены application role admin, session CSRF и `Cache-Control: no-store`. Directory возвращает только id/displayName active participant, без email. Tournament GET разрешён admin и active joined participant; поиск чужого/снятого private tournament возвращает 404. До roster freeze разрешены date/format/cap/config и roster changes. После freeze эти изменения закрыты; title/description/visibility остаются редактируемыми, пока турнир не перешёл в `running`, `completed` или `archived`. DELETE нефрозеного `draft` выполняет hard delete; в остальных случаях устанавливается `archived`. Полные T03/T05 остаются `NOT_RUN` до integrated browser/API сценария, concurrency/freeze hardening и проверки истории сыгравшего участника.

Participant `seed` принимает `null` или целое значение `1..2147483647`, уникальное среди активного состава одного турнира. Повтор активной assignment с тем же seed (или без seed) возвращает существующую запись; изменение seed — отдельный PATCH. POST/DELETE и active count изменяются в одной транзакции. Снятая запись остаётся в БД как `REMOVED`; повторный DELETE идемпотентен, повторная assignment до freeze реактивирует ту же строку.

`POST /tournaments/{id}/bracket/generate` вызывается агентом 2 в одной внешней `transaction.atomic()` с `backend.apps.tournaments.services.freeze_roster(tournament_id)`. Успешная генерация и frozen roster коммитятся вместе; ошибка создания bracket откатывает freeze. Freeze идемпотентен, а любые последующие add/remove/seed изменения возвращают conflict. Match/bracket replacement после старта остаётся отдельным контролируемым action агента 2.

## Задачи и сетка

| Метод и путь | Право | Содержание |
|---|---|---|
| POST `/problem-imports` | A | Multipart official package, ограничения размера/путей, checksum |
| GET `/problem-imports/{id}` | A | Import status/errors без secrets |
| POST `/problem-imports/yandex` | A | Планируемое `{contestId, problemIds}`; server-config source, не arbitrary URL |
| GET `/problems` | A | Доступные версии, READY/NOT_READY |
| PUT `/tournaments/{id}/problems` | A | Набор готовых задач из пакета |
| POST `/tournaments/{id}/bracket/generate` | A | `{seedingMode: "manual"}`, atomic generation |
| GET `/tournaments/{id}/bracket` | A / joined P | Bracket DTO, без source |
| PATCH `/matches/{id}` | A | Пары, готовые задачи, duration/startMode до start |
| GET `/matches/{id}/problems` | A / Own P | Meta до старта; condition только после start (admin может inspect) |
| GET `/matches/{id}/problems/{problemId}` | A / Own P | Markdown/public asset IDs/limits/examples |
| GET `/matches/{id}/problems/{problemId}/languages` | A / Own P | Только реально установленный compiler registry и templates |
| GET `/problem-assets/{assetId}` | Access to problem | Только разрешённый public asset, не путь к tests |

Import не запускает package scripts на хосте. Формат private tests/checkers определяется README пакета. Условия из Яндекса без полного local judge data не становятся READY.

## Матч и посылки

| Метод и путь | Право | Содержание |
|---|---|---|
| GET `/matches/{id}` | A / Own P | Current run/state/clock/rules, own stats |
| POST `/matches/{id}/ready` | Own P | Идемпотентная готовность; при both_ready запускает service |
| POST `/matches/{id}/start` | A | READY → RUNNING |
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
| GET `/public/tournaments/{slug}` | Public | Турнир без user email/secrets |
| GET `/public/tournaments/{slug}/bracket` | Public | Сетка, statuses, scores |
| GET `/public/tournaments/{slug}/events` | Public | SSE advancement/lifecycle |
| GET `/public/matches/{id}` | Public | Public snapshot с lastEventId/server clock |
| GET `/public/matches/{id}/events` | Public | SSE allowlist, Last-Event-ID, heartbeat/resync |

Unlisted read требует share token; хранить hash, redact token query в логах, `Referrer-Policy: no-referrer`. Ни один public маршрут не изменяет state и не возвращает исходник, tests, checker, private email или CE diagnostics. Error payload не раскрывает private object existence.

## Ошибки и ограничения

Target response `{error: {code, message, fields?}, requestId}`. 400/422 — неверные поля; 401 — нет session; 403 — нет role; 404 — не существует/недоступный чужой private объект; 409 — conflict state/revision/idempotency/cap; 410 — expired/revoked invite; 413 — oversized; 429 — rate limit; 503 — временная недоступность до сохранения запроса. После 202 source уже persisted, infrastructure error выдаётся status объекта, не потерей данных.

DRF по умолчанию имеет собственный формат/особенности 401/403; агент 1 нормализует его явно. Message отображается как text, не HTML. Private responses `Cache-Control: no-store`. Admin writes, extension и rematch имеют command idempotency key, чтобы сетевой retry не повторял действия.

Role permission проверяется вместе с ownership/run state. Зарегистрированный participant другого турнира не имеет private доступа; known UUID не даёт право submit. Для changes whitelist serializer fields, нельзя mass-assign role/score/createdBy/winner из обычного DTO. Source/Markdown/URL всегда недоверенные данные.
