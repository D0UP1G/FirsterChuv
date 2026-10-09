# Агент 2: сетка и live backend

Перепланировано координатором 2026-10-09; старые A-ID сохраняются только в истории и прежних аудитах.

- Статус: `IN_PROGRESS` — P2-01: код и штатные проверки готовы локально; остаются commit/push и актуализация PR #7.
- Назначенный исполнитель: Codex в роли агента 2 по поручению команды.
- Текущая задача/ветка/база: `P2-01` / `feature/bracket-runtime` / актуальная `origin/develop` `d9488e3`; локальный код сохранён на `a89b8fc`; PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) открыт как draft.
- Пути P2-01: `backend/apps/competition/`, `backend/config/settings.py`, `backend/apps/common/api_urls.py`, `context/agents/agent-2.md`, аудит и PR body.
- Задачи: P2-01–P2-06 из `ROADMAP.md`; собственные пути — `backend/apps/competition/`, `backend/apps/events/` и тесты/миграции этих apps.
- P2-01: сохранить bracket algorithm/ORM/atomic generate/reset/pairing services из `a89b8fc`; merge актуального develop выполнен merge-коммитом `086ebdc`; свой AppConfig и URL include подключены; штатная suite — 58 passed, migration check — no changes. Остаются commit/push и обновление PR body. HTTP pair/reset поверхность и F08 guard остаются P2-02.
- Следующий срез после P2-01: P2-02 — lifecycle guard для archived reset и HTTP full pairings/reset по v1; затем P2-03 clock/start, P2-04 score/ledger, P2-05 admin actions, P2-06 event store/snapshots/SSE.
- Зависимости по портам: начать core без соседних веток по `docs/architecture/parallel-contracts.md`; реальный start закрыт, если READY problem catalog отсутствует. Для P2-03/04 использовать typed локальные test receipts/catalog, не подменять production adapters.
- Отдельная ранее написанная pure-clock работа: локальный commit `c6789a7` в checkout `work/FirsterChuv-agent2-clock`, первоначальная база `146b2cb`; по v2 перепроверить и вести как P2-03.1 после обновления от `origin/develop`. Пока не опубликована.
- Передача: CompetitionGatewayV1 для A3 admission/result/workspace; PublicAccessV1 и EventWriter для публичного чтения/событий; fixtures в `contracts/mvp-v1/`.
- Последние аудиты: [P2-01 sync/wiring](../audits/2026-10-09T165701+0300-agent-2-P2-01-sync-wiring.md), собственные A2-01 audits и [ревизия координатора](../audits/2026-10-09T163805+0300-coordinator-parallel-roadmap.md). P2-01 проверен локально; commit/push/PR body ещё ожидают.

Сверять P2 implementation, integration и full acceptance раздельно. Не менять чужие ветки, migrations или принадлежащие другим агентам apps. `context/STATE.md` обновляет интеграционный координатор после merge.
