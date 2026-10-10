# Контракты v1 для независимой разработки

> Актуальная передача 2026-10-10, ROADMAP v5: A4 (прежний A1) owns API/accounts/tournaments/competition/events/common contracts; A3 owns problems/submissions/drafts/judge/worker + config/Compose/CI/system acceptance; A5 весь frontend. A2 больше не активный producer. Старые датированные назначения ниже — история; поля v1 и принятые additive boundaries не меняются. Missing provider блокирует только CONNECT, не всю роль.

Дата: 2026-10-09. Назначение: реализация пяти дорожек без ожидания соседней feature-ветки. Это спецификация целевых границ; готовность конкретного адаптера подтверждается кодом/PR, а не этим документом. В `common/contracts.py` объявлены immutable DTO и typing Protocol для submission/result/workspace, problem catalog, public access, judge и events; они не содержат provider implementations и не импортируют optional apps. До интеграции конкретных apps доступ к ним остаётся только через готовый adapter, а отсутствие provider закрывает действие.

## Приоритет и версия

Выполненные auth/tournament/roster endpoints остаются совместимыми с кодом `develop` на базе повторной ревизии `dd80c93` (включая invitations/CI). Будущие REST endpoints описаны в [api.md](api.md), доменные правила — в [match-engine.md](match-engine.md), события — в [realtime.md](realtime.md). Этот документ уточняет nullable seed, независимое тестирование и порты. При расхождении проверять фактическую реализацию и исправлять контракт явно, не переключать потребителя на свой формат молча.

`contracts/mvp-v1/*.json` — примеры DTO, не backend и не все возможные состояния. `v1` — версия соглашения. Новое optional поле допустимо с обновлением примера; изменение обязательного поля/enum/семантики требует версии и migration plan. Fixtures не подтверждают выполнение требований кейса.

`contracts/mvp-v1/schemas.json` содержит JSON Schema Draft 2020-12 для всех девяти примеров; `scripts/check_contracts.py` сверяет комплектность, типы/форматы и запрещает неописанные поля. Для публичных match/event DTO схема также проверяет отклонение private `source`. CI запускает проверку отдельно от API integration; synthetic examples не являются runtime fixtures и не доказывают S02.

## Уже доступная база для всех

| Граница | Фактический контракт |
|---|---|
| Auth | GET `/api/v1/auth/csrf`, POST register/login/logout, GET `/api/v1/me`; session cookie, CSRF header; login возвращает новый csrfToken |
| JSON | camelCase на HTTP, snake_case в Python; UUID строкой, UTC/RFC3339 |
| Private API | 401 без session, 403 запрещённая роль, 404 чужой private объект; no-store |
| Турниры | Admin CRUD, participant list/read только active joined; server-controlled status/owner/slug |
| Roster | GET/POST participants, PATCH/DELETE participants/{userId}; API participant ID — **User UUID**, а не UUID строки TournamentParticipant |
| Seed | `null` или unique active integer 1..2147483647; omitted seed не означает автоматически назначенный рейтинг |
| Freeze | `backend.apps.tournaments.services.freeze_roster(tournament_id)`; outer atomic bracket transaction, rollback вместе с сеткой |

Сам `freeze_roster` — идемпотентное чтение уже замороженного состава. Bracket endpoint дополнительно проверяет editable lifecycle; archive не разрешает generate/reset. Замороженный roster не снимается reset: меняются пары ещё не начатой сетки на том же составе. Add/remove/seed после freeze закрыты.

### Nullable seed: решение для PR #7

Сервис A1 сортирует по seed ascending/null last, затем user UUID ascending. A2 перечисляет возвращённые строки: `SeededParticipant(str(entry.pk), rank)` для `rank=1..N`. Это временные **позиции порядка**, не новые значения seed в БД. Так seeded 10/20 нормализуются так же, как seeded 1/2; все null тоже допустимы и детерминированы. Внешний roster повторно не сортировать по UUID строки entrant. Внутренний builder a89b8fc использует UUID строки TournamentParticipant; HTTP/порты actor используют User UUID, это разные идентичности. Fixture entryId — вход freeze test, не дополнительное поле существующего roster API.

В [roster.json](../../contracts/mvp-v1/roster.json) участники с seed 10/20/null/null дают rank 1/2/3/4. Успешная генерация freeze+save атомарна; duplicate generate возвращает существующий результат, явный reset до первого start не создаёт дублей. Это закрывает seed/freeze вопросы PR #7; ответ на старый комментарий не требуется для продолжения реализации.

## Целевые порты между доменами

Порты — Python вызовы, не публичный HTTP callback. Сериализуемые поля указаны в camelCase для ясности; внутренние dataclass поля snake_case. Методы принимают только доверенные server timestamps/ID, а не произвольные настройки исполнения от браузера.

| Порт/владелец | Метод и результат | Кто использует |
|---|---|---|
| CompetitionGatewayV1 / A2 | `authorize_submission(actorId, matchId, runId, problemId, receivedAt)` → Permit `{runId, elapsedMs, scoringVersion}` | A3 submission admission |
| CompetitionGatewayV1 / A2 | `register_accepted(AttemptReceipt)` → `None` after durable pending-ledger write | A3, в общей transaction до 202 |
| CompetitionGatewayV1 / A2 | `apply_result(ResultReceipt)` → `{applied: bool}` | A3 worker, идемпотентно |
| CompetitionGatewayV1 / A2 | `authorize_workspace(actorId, matchId, runId, problemId, purpose)` → WorkspaceContext | A3 statement/draft/history; purpose `metadata/statement/draft/history` |
| ProblemCatalogV1 / A3 | `describe_ready(problemIds)` → immutable public versions/limits/languages, отказ для NOT_READY/unknown | A2 config/start |
| ProblemCatalogV1 / A3 | `load_bundle(problemId, version)` → private ProblemBundleV1 | A3 JudgeProvider |
| LanguageRegistry / A3 | `is_supported(languageId)` → `bool` из server-owned allowlist | A3 admission |
| PublicAccessV1 / A1 | `assert_can_view(tournamentId, shareToken?)` → public-safe access context | A4 snapshot/SSE |
| EventWriter / A4 | `append(scope, eventType, publicPayload)` → monotonic event ID | Domain changes в той же transaction |
| JudgeProvider / A3 | `execute(TrustedJudgeJob)` → JudgeResult; infrastructure failure отдельным typed error | Один trusted worker |

`AttemptReceipt`: submissionId, runId, userId, problemId, receivedAt, elapsedMs, scoringVersion. `ResultReceipt`: та же неизменяемая идентичность + verdict; данные A2 сверяются с уже принятым ledger, worker не может подменить elapsed/player/problem. Accepted ledger уникален по submissionId. При duplicate result возвращается applied=false; старый run сохраняет history и не меняет current/downstream score. При lease смене только текущий claim может завершить submission, старый worker результат не публикует.

`WorkspaceContext`: actorId/runId/problemId, разрешённые действия и признак раскрытия условия. Actor active participant и принадлежит run; до start разрешены metadata, условие не раскрывается. Для собственной истории старых runs доступ определяется автором и membership/history policy, не только current run. Админ управляет матчем, но этот порт не даёт ему исходник чужого решения. Metadata admin inspect — отдельная admin view.

`TrustedJudgeJob`: submissionId, source (server-owned private content/reference), languageId из server registry, problemId/version/checksum. Image, argv, compiler path, network, limits и checker конфигурация выбираются trusted provider из registry/bundle; браузер их не задаёт. `JudgeResult.verdict` типизирован как OK/WA/TL/ML/RE/CE, но provider всё равно валидирует runtime enum и bounded/private compile diagnostics. Ошибка Docker/checker — infrastructure error, не RE/WA и не начисление score.

### ProblemBundleV1

Нормализованный объект catalog: problemId/version/checksum, public statementMarkdown/assets/examples/limits/languages и private `tests` (input bytes, nullable expected-output bytes) вместе с `private_artifacts` (role/sourcePath/languageId/content bytes для checker/validator/reference). Public projection содержит лишь asset IDs и не выдаёт checksum/private artifacts; `load_bundle` предназначен доверенному judge-коду. Закрытые данные не идут в API response, static server или solution container. Checker получает только нужные данные в собственной ограниченной среде; код участника не получает expected output.

Это **не заявленный формат архива организаторов**. P3-02 создаёт нормализатор/storage на собственных synthetic fixtures; P3-06 читает настоящий README и пишет внешний mapping. Яндекс statement без private local judge data остаётся NOT_READY. Чтение пакета не исполняет его scripts на host.

## Общие атомарные границы

1. **Generate:** lifecycle guard → freeze_roster → adapter rank → save slots/matches → commit. Ошибка откатывает freeze.
2. **Admit:** server receivedAt в короткой SQLite atomic transaction → authorize_submission/current run → persist source/submission/idempotency → register_accepted → public accepted event → commit → 202. Конфликт не оставляет расход или pending ledger без submission. Проверка и запись не разделяются сетевым вызовом.
3. **Judge:** вне DB write transaction, isolated compile/run/checker. Claim lease short, retries bounded. После сохранения source отказ инфраструктуры меняет status, не теряет запрос.
4. **Result:** guarded lease completion + ResultSink ledger/score/winner/downstream/event в одной atomic transaction либо durable outbox с идемпотентным повтором. Нельзя пометить submission FINISHED и потерять score при crash; если выбран outbox, это явно документируется и проверяется recovery test.
5. **Finalize:** A2 смотрит свой accepted ledger, поэтому может реализовать FINALIZING независимо от таблицы submissions A3; pending записи появляются только в admission transaction и закрываются реальным result/cancel/infra policy. Infrastructure failure требует retry или явного audited admin action.

SQLite не даёт обычных row locks PostgreSQL. Использовать conditional update/unique constraints/short transaction/retry; clock и worker не удерживают write lock во время Docker/SSE. Порты находятся в одном процессе/БД; замена на удалённый сервис потребует отдельной версии атомарной модели.

## HTTP и fixtures для frontend

- [invite.json](../../contracts/mvp-v1/invite.json): admin create result `{invite,token,url}`; list возвращает paginated metadata без token, revoke 204. Metadata id/tournamentId/expiresAt/maxUses/uses/revokedAt; maxUses/expiresAt nullable, минимум один ограничитель обязателен. Preview валидного token возвращает `{tournament:{id,title},valid:true,expiresAt}`; истёкший/отозванный/исчерпавший лимит — 410 error envelope, неизвестный — 404. Accept 200 с `{tournamentId,userId,joined:true}` и для идемпотентного повтора. P1-01 интегрирован PR #12; полный browser CONNECT остаётся P4-02.
- [bracket.json](../../contracts/mvp-v1/bracket.json): форма уже опубликованного serializer PR #7 a89b8fc: `{tournamentId,rosterFrozenAt,bracketSize,matches}`. Match: id/key/roundIndex/position/kind/status/winner/nextMatchId/nextSlot/slots. Slot: index/resolution/participant/sourceMatchId; participant/winner `{id,userId,displayName,seed}` либо null. Здесь id участника — roster entry UUID, userId — account UUID. BYE — kind=BYE/status=BYE, без MatchRun; downstream WAITING отличается от пустого BYE. В будущем public stream может добавить optional lastEventId, но текущий private DTO его не обещает.
- Ручные пары: **PUT `/tournaments/{id}/bracket/pairings`**, admin+CSRF+command Idempotency-Key, `{pairings:[{position:0,leftUserId:UUID|null,rightUserId:UUID|null},...],reason}`. Полный первый раунд, позиции непрерывны 0..bracketSize/2-1, каждый frozen active entrant ровно один раз, обе стороны null запрещены. API преобразует User UUID в roster entry UUID и вызывает существующий set_first_round_pairings; response — bracket DTO. Так UI не угадывает внутренний entry ID и не делает два неатомарных PATCH при обмене игроков. PATCH `/matches/{id}` остаётся для pre-start config; изменение одной пары возможно только с проверкой/пересборкой всего раунда.
- Explicit POST `/tournaments/{id}/bracket/reset` с `{reason}` и command Idempotency-Key возвращает bracket DTO на том же frozen roster только до первого start. Lifecycle draft/scheduled обязателен, archived/running/completed отклоняются. PUT pairings и POST reset требуют активного admin + CSRF; reason/actor, hashed key и исходный response receipt сохраняются атомарно с изменением сетки. Точный повтор возвращает исходный DTO, повтор ключа с другим actor/action/body даёт `409 idempotency_conflict`; новый reset после первого старта даёт `409` без изменения истории.
- [match.json](../../contracts/mvp-v1/match.json): own/admin match DTO. clock/state/current run/tasks/rules; private source сюда не включается.
- P2-03.4: `POST /api/v1/matches/{matchId}/ready` доступен только активному назначенному participant с session CSRF; принимает строго `{}` и обязательный `Idempotency-Key`, возвращает полный DTO `match.json`. В режиме `manual` сигнал только сохраняется. В `both_ready` сигнал второго участника атомарно запускает run по серверному времени. `readyUserIds` содержит только UUID участников.
- [problem.json](../../contracts/mvp-v1/problem.json): публичная часть разрешённого условия; не public-anonymous endpoint, а own workspace response после access check.
- [submission.json](../../contracts/mvp-v1/submission.json): 202 metadata; statuses QUEUED/RUNNING/RETRY_WAIT/FINISHED/INFRA_FAILED/CANCELLED, verdict nullable.
- [draft.json](../../contracts/mvp-v1/draft.json): private response собственного черновика, revision.
- [public-match.json](../../contracts/mvp-v1/public-match.json): оба игрока, все задачи, score/rules/clock/lastEventId; без code/email/CE.
- [score-event.json](../../contracts/mvp-v1/score-event.json): normalized browser event после разбора SSE, authoritative score.changed. SSE id/type берутся из envelope; data — JSON, пользовательский текст не вставляется в строки протокола.

Submission POST: Idempotency-Key + `{runId, problemId, languageId, source}`; тот же key/body возвращает ту же запись, другой body даёт 409. Draft PUT: `{runId, source, expectedRevision}` с languageId в query. Ошибка `{error:{code,message,fields?},requestId}`, message отображается как text. SSE: snapshot cursor, afterEventId первый connect, Last-Event-ID reconnect, dedupe; старый cursor → resync. При новом run старые events не двигают current map.

Команды configure/start/ready сохраняют квитанции со scope `(match, actor, SHA-256(Idempotency-Key))`. Action и каноническое проверенное тело хешируются вместе; точный повтор возвращает исходный ответ, а повтор ключа с другим телом или action даёт `409 idempotency_conflict`. Изменение состояния матча и квитанция фиксируются одной транзакцией. Тела ready и start не принимают полей.

## Изоляция разработки и подключение

Backend consumer принимает порт через constructor/factory, pure core не импортирует соседние models. Свои test settings добавляют только реализованные apps. Test doubles лежат в tests, никогда не выбираются production env/config. Незаполненная production factory выдаёт 503/integration_unavailable/readiness error, start/submit закрыты; не возвращает разрешение или verdict.

Frontend `ApiTransport` имеет HTTP implementation и отдельный dev fixture entrypoint. Production build не включает fixtures и не переключается на них при HTTP ошибке. Ещё отсутствующий endpoint показывает loading/error/unavailable; development scenario помечается в UI как разработка. Реальные auth и roster доступны сейчас, подключить сразу.

Если include optional field или отдельный endpoint не определён, зафиксировать предложение потребителя в contract request и продолжать готовые экраны; не заменять уже описанные DTO несовместимыми формами. Raw invite/share credential в dev примере synthetic и не работает, в runtime выдаётся только разрешённой admin операции. Share link и invite token не взаимозаменяемы.

При подключении достаточно одного готового provider: merge develop в свою ветку, реализовать тонкий adapter, выполнить contract + smoke checks, audit/PR. Владелец app добавляет её AppConfig и URL include в общие settings/API root в том же PR с модулем — это явно разрешённая минимальная передача, ожидание агента 1 не нужно. Для CompetitionConfig рецепт: строка `backend.apps.competition.apps.CompetitionConfig` в INSTALLED_APPS и `path("", include("backend.apps.competition.urls"))` в common/api_urls.py. Новые apps A3 регистрируются аналогично вместе с собственным кодом. Если provider не готов, продолжить свою независимую очередь. Нужное изменение контракта фиксировать отдельным файлом `context/contracts/<agent>-<topic>.md`: поля, причина, совместимость, затронутые потребители и fallback; это сообщение в Git, не разрешение автоматически писать другим агентам/людям.

## Передача runtime после повторной ревизии

[Runtime handoffs](runtime-handoffs.md) задаёт production owners/queue receipt adapters, immutable job snapshots и отдельный additive infrastructure failure port. Core не заменяет provider. #7 lifecycle и #16 SOLVED.lastVerdict требуют исправлений; детали — [отчёт](../reviews/2026-10-09-integration-review.md). Старые ссылки a89b8fc выше фиксируют происхождение serializer/rank, не последний HEAD (#7 сейчас 1952244).

Обновление 2026-10-09T23:54+03:00: исправления #7 `1a2b54a` и #16 `a0b1dcc` проверены в новой coordinator integration feature. #34/#38/#41 дают pure readiness/ledger/command receipts; #37 даёт worker/common adapters и local technical-failure outbox. Существующий common v1/HTTP contract не менялся; production providers и additive common failure port ещё нужны. После фактического MERGED integration PR продолжать CONNECT по [STATE](../../context/STATE.md); исторические blockers выше не выполнять повторно.

## Передача владельцев и уточнения 2026-10-10

ROADMAP v4 передаёт events/public HTTP/SSE A4, frontend A5; competition/run/ledger A2. [Принятые MVP boundaries](../../context/contracts/2026-10-10-mvp-boundaries.md) фиксируют GET draft runId/404, additive accepted-run snapshot provider/failure sink и per-claim container fencing. Это target contracts, не утверждение готовности adapters. Source #53 snapshot остаётся OPEN с двумя correctness blockers; старый event store #16 integrated.
