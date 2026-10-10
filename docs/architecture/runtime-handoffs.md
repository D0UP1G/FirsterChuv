# Runtime handoffs: ближайший рабочий сценарий

Спецификация повторной ревизии 2026-10-09, ADOPTED планом команды. [Common v1](parallel-contracts.md) уже материализован в backend/apps/common/contracts.py; CompetitionGateway интегрирован PR #77, public-only PublicAccess provider/snapshot endpoint находятся в текущей P4-07 feature, unlisted share provider ещё не интегрирован; production worker factory не подключена. LocalJudge core реализован, его наличие не означает готовый production worker. Этот документ фиксирует передачу между тремя активными владельцами A3/A4(прежний A1)/A5; наличие Protocol не означает runnable provider.

## Владельцы и независимые выходы

| Граница | Производитель | Потребитель | Что писать до CONNECT |
|---|---|---|---|
| PublicAccessV1 | A4: public/unlisted token/expiry/revoke | A4: public snapshot/SSE | Store/projector/transport с test access; production без provider закрыт |
| CompetitionGatewayV1 | A4: trusted actor/run/time/workspace/ledger/result | A3: submissions/drafts/problem views | A4 tests с typed receipts; A3 queue/draft services с injected ports |
| ProblemCatalogV1 | A3: normalized immutable catalog | A4: task snapshots/start; A3 judge | Catalog core уже в #14; verified compiler остаётся runtime gate |
| JudgeProvider + LanguageRegistry | A3: реальный compile/test/checker | A3 worker/startup | Нормализованная программно импортированная smoke-задача, настоящие verdicts |
| EventWriter | A4: allowlisted durable events | A4 lifecycle/result, A3 queue | Event store/validation tests; source/CE запрещены |
| Browser transport | A5: typed client + real available endpoints | Все UI | Auth/CRUD/invites подключать сейчас; будущие fixtures только dev/test |

Владельцы apps сами добавляют AppConfig/URL include в своих PR, сохраняя все ранее integrated apps/CI. Остальное shared factory/config wiring — A3 и принимающий владелец коротким срезом. Не ждать всю дорожку соседа.

## Admission/result transaction

1. API извлекает trusted authenticated User; server received_at фиксируется один раз до bounded SQLite retry. Клиент не задаёт actor/elapsed/scoring version.
2. A3 queue в одной SQLite transaction вызывает gateway authorize_submission(actor UUID, match/run/problem/received), сохраняет source/submission/capacity, register_accepted(common AttemptReceipt), allowlisted accepted event. Commit предшествует 202; callback не пишет вне этой transaction.
3. Queue local receipts имеют дополнительный match_id. Adapter оставляет его на стороне queue, проецирует неизменённый common v1 receipt; не переименовывает обязательные поля под локальную модель.
4. Worker получает version/checksum из immutable snapshot того run, в котором submission была принята (`submission.run_id`), а не нового current run матча или active latest catalog. После rematch старая очередь продолжает проверяться по своему snapshot; apply_result не меняет score нового run. Проверяет checksum/allowlist, создаёт TrustedJudgeJob и вызывает настоящий provider. Не выполняет присланный код или package scripts на host.
5. Queue durable result/outbox → gateway apply_result(ResultReceipt). ResultApplication.applied=false означает уже применённый/устаревший результат, доставка может считаться выполненной; exception означает retry. Duplicate/late result не удваивает score.
6. Gateway решает score/FINALIZING/winner/downstream/event атомарно. Последняя WA после OK не отменяет SOLVED: score/event projector сохраняет first OK и честный lastVerdict.

SQLite DEFERRED read→write race #15 требует bounded busy/locked retry всей transaction либо write-first serialization. Arbitrary DB errors не маскировать QueueFull; exhausted contention → retryable 503, original server received_at сохраняется. File-backed concurrent tests обязательны.

## Additive infrastructure failure handoff

Проблема #15: exhausted infra retries освобождают queue capacity без contestant result; accepted ledger A4 иначе может навсегда ждать отсутствующий receipt. Нельзя выдавать infra failure за WA/RE/поражение. Принят отдельный additive внутренний port, будущая реализация P1-02.5/P2-04/P3-04.4; существующий ResultReceipt и verdict enum v1 неизменны.

```python
@dataclass(frozen=True, slots=True)
class InfrastructureFailureReceipt:
    submission_id: UUID
    run_id: UUID
    reason_code: str  # server allowlist, bounded, без diagnostics/secrets
    retryable: bool

class InfrastructureFailureSink(Protocol):
    def record_infrastructure_failure(self, receipt: InfrastructureFailureReceipt) -> None: ...
```

A4 добавляет DTO/Protocol/import tests и реализует idempotent ledger transition для известного accepted submission/run: pending → technical failure; такой run не получает автоматического победителя, текущий FINALIZING показывает необходимость восстановления/ручного решения. Повторная доставка не дублирует effect, superseded run не меняет текущий score. A3 хранит durable failure outbox и доставляет его после exhausted retries; startup требует реальный failure sink вместе с result sink.

P2-04 implementation в Agent 4 feature добавляет per-accepted durable failure row, allowlist из четырёх reason codes и safe private match projection. Повтор с тем же receipt — no-op; conflicting receipt отклоняется. `retryable=true` оставляет accepted работу pending, пока не придёт реальный result; terminal failure при deadline удерживает матч в FINALIZING с `resolutionRequired=true` и не публикует финальное score event с winner. Реальный verdict отмечает failure resolved и продолжает финализацию. Gateway CONNECT в A3 worker/API и GitFlow merge этой feature остаются отдельными checkpoint.

Восстановление/повтор проверки использует тот же accepted submission и original received_at/elapsed, а не создаёт новую выгодную позднюю попытку. Администратор может выполнить документированное техническое завершение/rematch с reason; infrastructure failure сам не выбирает победителя. A4/A3 проверяют requeue/terminal/manual policy tests до runtime wiring.

Это новая отдельная граница, не изменение обязательных полей старого v1. Новые public DTO/events по технической ошибке требуют явной версии/schema/fixtures; до этого private API показывает понятную техническую ошибку, public event не содержит diagnostics. Исполнители записывают фактическую реализацию/выбранный retry policy в audit/decisions.

## Проверка готовности и milestones

- R0: cores совместно imports/migrate/tests/CI; отсутствующие providers не подделываются.
- M0 (уточняет R1): реальный React → API → persisted run → queue → isolated judge → durable receipt → score/promotion на программно импортированной smoke-задаче. Synthetic здесь — данные задачи, verdict реально вычисляется. Это не official acceptance.
- M1 (обязательные блоки 1–3) и M2 (public): обязательные actions/code persistence/recovery/privacy и public map/SSE.
- M2 (уточняет R3): official package/README/checkers, T01–21, hostile probes, одна команда и demo/видео/release.

Короткий CONNECT содержит producer SHA, consumer SHA, adapter path/config, реальный сценарий и следующий независимый подпункт. WAITING относится к подключению, не ко всей роли. [ROADMAP v5](../../ROADMAP.md) задаёт порядок.

## Принятые уточнения 2026-10-10

[Ответы координатора](../../context/contracts/2026-10-10-mvp-boundaries.md): immutable RunProblemSnapshot/Provider отдельным additive портом, snapshot version/checksum сохраняется при admission; InfrastructureFailureReceipt/Sink без изменения verdict enum; GET draft runId selector и missing404; registry owner/submission/claim-token/lease для own orphan cleanup. A4 материализует common typing, producer run/gateway/ledger/public transport; A3 actual executor/consumer/config/startup/system acceptance, A5 весь frontend. Tests до CONNECT используют typed injections; production без реального provider отказывает.
