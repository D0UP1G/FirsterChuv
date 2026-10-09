# Агент 2: сетка и live backend

Перепланировано координатором по ROADMAP v2. Исторические A-ID оставлены в старых аудитах.

- Статус: `IN_PROGRESS` — P2-06.1 durable public event store; P2-06 целиком включает ещё snapshots/access/SSE.
- Исполнитель: Codex в роли агента 2.
- Текущая задача/ветка/база: `P2-06.1` / `feature/public-events-sse` / `origin/develop` `cad34ea4ddf1171779dc22139f2e1533160b5015`.
- Планируемые пути: `backend/apps/events/{apps.py,models.py,services.py,public_payloads.py,tests.py,migrations/}`, `backend/config/settings.py`, эта карточка и новый audit. URL registration пока не планируется.
- Scope P2-06.1: durable scoped public events с монотонным event ID, проверкой безопасного allowlisted payload и чтением после cursor; начать с concrete `score.changed` shape из `contracts/mvp-v1/score-event.json`. Не добавлять producer, HTTP/SSE, snapshots или авторизационный fallback.
- Параллельные свои срезы: P2-04.1 [PR #13](https://github.com/D0UP1G/FirsterChuv/pull/13) открыт, ready, последний проверенный статус `CLEAN`; его код не интегрирован и в эту ветку не переносится. P2-01 PR #7 и P2-03.1 PR #11 остаются отдельными открытыми review slices.
- Приёмка текущего подпункта: unit/DB tests на whitelist, private-field rejection, ordering/cursor, scope filtering и rollback. Это не PASS V01–03, S02 или T16/T17/T20.
- Интеграция: app schema/storage может быть включён в проект, но producers, PublicAccessV1 и HTTP/SSE transport отсутствуют; snapshot/cursor consistency будет следующим срезом после Match/Run и auth/access ports.
- Источники: `ROADMAP.md` P2-06, `docs/architecture/realtime.md`, `docs/architecture/parallel-contracts.md`, `contracts/mvp-v1/score-event.json`, `contracts/mvp-v1/public-match.json`; V01–03, S02, T16/T17/T20.
- Следующий шаг: после durable store — согласовать полный per-event v1 payload set, построить consistent public snapshot/projector с `lastEventId` и PublicAccessV1, затем bounded ASGI SSE replay/heartbeat/resync; подключить producers отдельными CONNECT slices.
- Audit: [P2-06.1 event store](../audits/2026-10-09T173634+0300-agent-2-P2-06-1-event-store.md).

Общий `context/STATE.md` меняет только координатор после merge.
