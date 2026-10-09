# Решение координатора: границы ближайшего MVP

> Актуальная передача 2026-10-10, ROADMAP v5: A4 (прежний A1) owns API/accounts/tournaments/competition/events/common contracts; A3 owns problems/submissions/drafts/judge/worker + config/Compose/CI/system acceptance; A5 весь frontend. A2 больше не активный producer. Старые датированные назначения ниже — история; поля v1 и принятые additive boundaries не меняются. Missing provider блокирует только CONNECT, не всю роль.

Снимок 2026-10-10T01:11:53+03:00, Europe/Moscow. Принято как архитектурное назначение по прямому поручению команды; материализация DTO/provider/runtime ещё не заявляется выполненной. Это ответы на существующие запросы, исходные author records не переписываются. [ROADMAP v4](../../ROADMAP.md).

## C01: GET private draft selector — ADOPTED

[Запрос A3](agent-3-private-draft-get.md) принят: `GET /matches/{matchId}/problems/{problemId}/draft?runId=...&languageId=...`. Обе UUID/run/match связи и allowed action проверяет real WorkspaceAccess. Missing record — 404 error envelope, не фиктивная revision0. PUT shape unchanged: runId/source/expectedRevision body, languageId query; first create expectedRevision0 → revision1. 409 содержит только собственную winning server draft; 503 означает unavailable/busy. DTO draft.json и strict privacy остаются прежними. A2 реализует production access, A3 route/storage, A5 client/recovery. До providers runtime fail closed. Историческая метка PROPOSED исходного запроса описывает состояние до этого ответа.

## C02: immutable accepted-run problem snapshot — ADOPTED additive boundary

[Запрос A3](agent-3-run-problem-snapshot.md) разрешён отдельным internal портом; обязательные поля SubmissionPermit/AttemptReceipt/ResultReceipt не расширяются.

Целевая frozen dataclass RunProblemSnapshot: run_id: UUID, problem_id: UUID, problem_version: str, problem_checksum: str (SHA-256 normalized bundle). Целевой Protocol RunProblemSnapshotProvider.resolve(run_id, problem_id) возвращает эту immutable пару только из assignment исходного run. Типизацию материализует A1 в common без optional imports; source implementation A2; consumer A3. Локальные структурно совместимые interfaces допустимы до короткого common PR.

После authorize_submission A3 в той же admission transaction получает snapshot для server permit.run_id/problem_id, сверяет returned IDs, сохраняет version/checksum вместе с accepted submission до commit/202. Client version/checksum не принимаются. Снимок run фиксируется при config→READY/start и не меняется; новый rematch — новый run. Worker использует сохранённую пару и проверяет checksum; не запрашивает current run/latest catalog и не подставляет fixture. Startup/admission без реального provider закрыты с integration error. Migration для accepted immutable fields принадлежит A3, run assignment migration A2. Tests независимы с typed trusted snapshots; old accepted после rematch использует old bundle.

## C03: infrastructure failures — ADOPTED existing additive spec

Материализовать уже принятую runtime-handoffs frozen InfrastructureFailureReceipt(submission_id, run_id, reason_code allowlist, retryable) и InfrastructureFailureSink.record_infrastructure_failure. A1 shared typing; A2 idempotent accepted ledger transition; A3 durable outbox/delivery. Не расширять verdict enum, не превращать infra failure в WA/RE/проигрыш. FINALIZING при terminal infrastructure failure требует documented recovery/manual reason, не автоматического победителя. Повторное исполнение сохраняет original received/elapsed/identity. Готовые A3 loop/outboxes/adapters и A2 pure ledger не переписывать.

## C04: sandbox container ownership/fencing — ADOPTED policy, implementation OPEN

[Запрос A3](agent-3-worker-container-recovery.md): выбрать durable per-claim fencing вместо глобального sweep/предположения эксклюзивного процесса. Trusted worker генерирует owner_instance_id и неповторимый claim token; хранит registry container ID/submission ID/owner/claim/lease у себя в trusted DB и ставит эти идентификаторы в labels контейнера. Labels — фильтр поиска, не доказательство, что работу разрешено удалить.

Удалять только own project/instance container по проверенному ID, сопоставленному с registry и durable claim. Подтвердить expiry/revocation того exact claim/fencing token; live matching lease запрещает deletion. Expired old claim не возрождается: новый worker получает новый token; old token не применяет result и не завершает новый claim. Проверку/reclaim/delete guard выполнять так, чтобы heartbeat/live lease не могло быть принято за orphan. Не удалять новый container другого token того же submission, не применять docker prune/rm по общему имени. API/solution не получают Docker authority или секреты. DB lease recovery и container cleanup проверяются отдельно.

A3 owns registry/labels/recovery, A1 trusted deploy/wiring, A4 independent restart evidence. Сначала файловые race/fencing tests, затем bounded real Docker process-kill/restart smoke. Пока этот CONNECT не готов, выполнять real executor/import/own recovery tests; T19 не закрывать одним finally cleanup.

## Владение

PublicAccess A1; competition/run/gateway/ledger/admin A2; judge/workspace/submissions A3; events/public SSE + acceptance A4; весь frontend A5. Все независимые задания определены в ROADMAP. Наличие принятой формы устраняет ожидание решения, но не заменяет production implementation/CI/system acceptance.
