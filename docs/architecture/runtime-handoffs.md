# Runtime handoffs: ближайший рабочий сценарий

Спецификация повторной ревизии 2026-10-09, ADOPTED планом команды. [Common v1](parallel-contracts.md) уже материализован в backend/apps/common/contracts.py, но реализаций CompetitionGateway/PublicAccess/JudgeProvider пока нет. Этот документ фиксирует передачу между четырьмя владельцами; наличие Protocol не означает runnable provider.

## Владельцы и независимые выходы

| Граница | Производитель | Потребитель | Что писать до CONNECT |
|---|---|---|---|
| PublicAccessV1 | A1: public/unlisted token/expiry/revoke | A2: public snapshot/SSE | Store/projector/transport с test access; production без provider закрыт |
| CompetitionGatewayV1 | A2: trusted actor/run/time/workspace/ledger/result | A3: submissions/drafts/problem views | A2 tests с typed receipts; A3 queue/draft services с injected ports |
| ProblemCatalogV1 | A3: normalized immutable catalog | A2: task snapshots/start; A3 judge | Catalog core уже в #14; verified compiler остаётся runtime gate |
| JudgeProvider + LanguageRegistry | A3: реальный compile/test/checker | A3 worker, A1 startup | Нормализованная программно импортированная smoke-задача, настоящие verdicts |
| EventWriter | A2: allowlisted durable events | A2 lifecycle/result, A3 queue | Event store/validation tests; source/CE запрещены |
| Browser transport | A4: typed client + real available endpoints | Все UI | Auth/CRUD/invites подключать сейчас; будущие fixtures только dev/test |

Владельцы apps сами добавляют AppConfig/URL include в своих PR, сохраняя все ранее integrated apps/CI. Остальное shared factory/config wiring — A1 и принимающий владелец коротким срезом. Не ждать всю дорожку соседа.

## Admission/result transaction

1. API извлекает trusted authenticated User; server received_at фиксируется один раз до bounded SQLite retry. Клиент не задаёт actor/elapsed/scoring version.
2. A3 queue в одной SQLite transaction вызывает gateway authorize_submission(actor UUID, match/run/problem/received), сохраняет source/submission/capacity, register_accepted(common AttemptReceipt), allowlisted accepted event. Commit предшествует 202; callback не пишет вне этой transaction.
3. Queue local receipts имеют дополнительный match_id. Adapter оставляет его на стороне queue, проецирует неизменённый common v1 receipt; не переименовывает обязательные поля под локальную модель.
4. Worker получает version/checksum из immutable текущего run snapshot, а не active latest catalog. Проверяет checksum/allowlist, создаёт TrustedJudgeJob и вызывает настоящий provider. Не выполняет присланный код или package scripts на host.
5. Queue durable result/outbox → gateway apply_result(ResultReceipt). ResultApplication.applied=false означает уже применённый/устаревший результат, доставка может считаться выполненной; exception означает retry. Duplicate/late result не удваивает score.
6. Gateway решает score/FINALIZING/winner/downstream/event атомарно. Последняя WA после OK не отменяет SOLVED: score/event projector сохраняет first OK и честный lastVerdict.

SQLite DEFERRED read→write race #15 требует bounded busy/locked retry всей transaction либо write-first serialization. Arbitrary DB errors не маскировать QueueFull; exhausted contention → retryable 503, original server received_at сохраняется. File-backed concurrent tests обязательны.

## Additive infrastructure failure handoff

Проблема #15: exhausted infra retries освобождают queue capacity без contestant result; accepted ledger A2 иначе может навсегда ждать отсутствующий receipt. Нельзя выдавать infra failure за WA/RE/поражение. Принят отдельный additive внутренний port, будущая реализация P1-02.5/P2-04/P3-04.4; существующий ResultReceipt и verdict enum v1 неизменны.

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

A1 добавляет DTO/Protocol/import tests. A2 реализует idempotent ledger transition для известного accepted submission/run: pending → technical failure; такой run не получает автоматического победителя, текущий FINALIZING показывает необходимость восстановления/ручного решения. Повторная доставка не дублирует effect, superseded run не меняет текущий score. A3 хранит durable failure outbox и доставляет его после exhausted retries; startup требует реальный failure sink вместе с result sink.

Восстановление/повтор проверки использует тот же accepted submission и original received_at/elapsed, а не создаёт новую выгодную позднюю попытку. Администратор может выполнить документированное техническое завершение/rematch с reason; infrastructure failure сам не выбирает победителя. A2/A3 проверяют requeue/terminal/manual policy tests до runtime wiring.

Это новая отдельная граница, не изменение обязательных полей старого v1. Новые public DTO/events по технической ошибке требуют явной версии/schema/fixtures; до этого private API показывает понятную техническую ошибку, public event не содержит diagnostics. Исполнители записывают фактическую реализацию/выбранный retry policy в audit/decisions.

## Проверка готовности и milestones

- R0: cores совместно imports/migrate/tests/CI; отсутствующие providers не подделываются.
- R1: реальный React → API → persisted run → queue → isolated judge → durable receipt → score/promotion на программно импортированной smoke-задаче. Synthetic здесь — данные задачи, verdict реально вычисляется. Это не official acceptance.
- R2: обязательные actions/code persistence/recovery/privacy и public map/SSE.
- R3: official package/README/checkers, T01–21, hostile probes, одна команда и demo/видео/release.

Короткий CONNECT содержит producer SHA, consumer SHA, adapter path/config, реальный сценарий и следующий независимый подпункт. WAITING относится к подключению, не ко всей роли. [ROADMAP v3](../../ROADMAP.md) задаёт порядок.
