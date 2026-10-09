# Агент 2: сетка и live backend

Перепланировано координатором по поручению команды 2026-10-09; audit history владельца сохранена.

- Проверены/integration feature: pure clock #11 `28d6cda` и score #13 `19bbf88`, по 12 tests. Доступность в develop — после MERGED общего integration PR; cores не заменяют persistence/API.
- P2-01/P2-02.1: bracket runtime/lifecycle guard отправлены в PR #7; не переписывать эти изменения в event ветке.
- Статус: `IN_REVIEW` — P2-06.1 correction опубликована в существующем [PR #16](https://github.com/D0UP1G/FirsterChuv/pull/16); все четыре GitHub checks прошли после rerun, merge state `CLEAN` на head `6eac91f`.
- База: `origin/develop` `ed14416fee0d1cccbd0b9a202e563d49f062572a`, включена merge-коммитом в feature.
- Планируемые пути: `backend/apps/events/public_payloads.py`, `backend/apps/events/tests.py`, при подтверждении условного ограничения — `contracts/mvp-v1/schemas.json`, эта карточка и новый audit. Сохранить строгие status/verdict allowlists и запрет приватных полей.
- Граница: исправить публичную проекцию после последовательности OK→WA/CE так, чтобы статус задачи оставался `SOLVED`, а `lastVerdict` отражал последнюю попытку; добавить тесты пути score→event. Не добавлять producer, HTTP/SSE, snapshots или auth fallback.
- Следом P2-03 persisted MatchRun/config/manual/both_ready/gateway/workspace/clock command и P2-04 accepted ledger/results/FINALIZING/downstream/failure sink. Не писать готовые clock/score cores повторно.
- Резерв во время CONNECT: P2-05 pure guards `8f5b762` включены в integration feature → command store/effects; P2-06 projector/snapshot/SSE tests остаются следующими срезами. Не ждать живого judge/importer/frontend для независимых domain/DB/API slices.
- Пути общей интеграции менять только при необходимости, сохраняя все app registrations, CI и чужие audits. Runtime без реального catalog/access provider отказывает.
- Источники: `ROADMAP.md` P2-06, `docs/architecture/realtime.md`, `docs/architecture/parallel-contracts.md`, `contracts/mvp-v1/score-event.json`, `contracts/mvp-v1/public-match.json`; V01–03, S02, T16/T17/T20.
- Audit исходного event store: [P2-06.1](../audits/2026-10-09T173634+0300-agent-2-P2-06-1-event-store.md). Новый аудит фиксирует этот corrective slice.
- Локальная проверка correction: event app 11 tests, весь backend 117 tests, domain suites 36 tests, 9 контрактных fixtures и migration drift check прошли.
- Audit correction: [SOLVED/lastVerdict roundtrip](../audits/2026-10-09T225633+0300-agent-2-P2-06-1-solved-verdict-roundtrip.md).

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
