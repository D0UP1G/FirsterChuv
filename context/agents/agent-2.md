# Агент 2: сетка и live backend

Перепланировано координатором по ROADMAP v2. Исторические A-ID оставлены в старых аудитах.

- Статус: `IN_REVIEW` — P2-04.1 PR [#13](https://github.com/D0UP1G/FirsterChuv/pull/13) открыт, ready, `CLEAN`; P2-04 целиком остаётся `IN_PROGRESS`.
- Исполнитель: Codex в роли агента 2.
- Текущая задача/ветка: `P2-04.1` / `feature/match-scoring-results`.
- База перед публикацией: feature создана от `origin/develop` `d9488e3`, затем синхронизирована обычным fast-forward до `cad34ea` после merge PR #12 (`P1-01`).
- Пути текущего среза: `backend/apps/competition/domain/scoring.py`, `backend/apps/competition/tests/test_scoring.py`, эта карточка и audit.
- Соседние срезы: P2-01 PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) и P2-03.1 clock PR [#11](https://github.com/D0UP1G/FirsterChuv/pull/11) остаются OPEN/ready/CLEAN и основаны на предыдущем `develop` `d9488e3`; P1-01 PR #12 integrated в `cad34ea`. Их файлы и ветки здесь не изменялись.
- P2-04.1 implementation: чистая детерминированная функция результата с typed per-run final verdict receipts; первая OK на задачу; число решённых, penalty и время последней первой OK; одинаковый score → rematch; одинаковый receipt идемпотентен, конфликтующие и чужие receipts отклоняются.
- Интеграция: PR #13 опубликован в `develop`, но код ещё не влит; нет ORM, ledger, ResultSink, HTTP, migrations или atomic downstream/event write. На момент проверки GitHub не сообщал checks для ветки.
- Приёмка: часть M05/M07/T10 на уровне scoring unit tests. Полные M05/M07 и T10 не закрыты; T09/J04/T19 и delayed-result/lease/FINALIZING поведение не проверялись этим срезом.
- Граница: функция принимает уже допущенные реальные final receipts; admission, дедлайн, lease/current-run, инфраструктурные ошибки и момент финализации принадлежат следующему ledger/wiring срезу. Тестовые fixtures используются только в unit tests.
- Контракт: `docs/architecture/match-engine.md`, `docs/architecture/parallel-contracts.md`, `contracts/mvp-v1/match.json`, `contracts/mvp-v1/score-event.json`; требования M05/M07/J04, T09/T10/T19.
- Следующий шаг: P2-04.2 accepted-attempt ledger/ResultSink после согласования с MatchRun/lifecycle P2-01 и clock/state P2-03, а также receipt/admission порта P3-04. Реализовать duplicate/out-of-order/lease/delayed OK/SUPERSEDED guards, ожидание pending accepted submissions и атомарную winner/downstream/event запись.
- Аудит текущего среза: [P2-04.1 score core](../audits/2026-10-09T171844+0300-agent-2-P2-04-1-score-core.md).

Общий `context/STATE.md` меняет только координатор после merge.
