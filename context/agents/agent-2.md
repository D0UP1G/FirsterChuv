# Агент 2: сетка и live backend

Перепланировано координатором по ROADMAP v2. Исторические A-ID оставлены в старых аудитах.

- Статус: `IN_PROGRESS` — P2-05.1 pure admin action guards; P2-05 целиком остаётся `IN_PROGRESS`.
- Исполнитель: Codex в роли агента 2.
- Текущая задача/ветка/база: `P2-05.1` / `feature/match-admin-actions` / актуальный `origin/develop` `1f60aa9ad93a818d12c0b04b94cacec3f25b8d4e` включён merge-коммитом в feature.
- Пути: `backend/apps/competition/domain/admin_actions.py`, `backend/apps/competition/tests/test_admin_actions.py`, регистрация suite в `scripts/check_domain_suites.py`, эта карточка и audit [P2-05.1](../audits/2026-10-09T175534+0300-agent-2-P2-05-1-admin-action-guards.md). Код ограничен своими competition paths и одной записью suite в интегрированном CI runner.
- Scope: pure typed permits/guards для pause, resume, positive bounded extension, technical result, rematch и replacement; admin/active role, UUIDs, reason/command key, state/downstream guards, no score carry-over при новом run.
- Граница: без ORM, state mutation, events, command-idempotency store, HTTP или миграций; `command_id` будет проверяться/сохраняться в следующем persistence срезе.
- Отдельные review slices: P2-01 PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7), P2-03 clock PR [#11](https://github.com/D0UP1G/FirsterChuv/pull/11), P2-04 score PR [#13](https://github.com/D0UP1G/FirsterChuv/pull/13), P2-06 event-store PR [#16](https://github.com/D0UP1G/FirsterChuv/pull/16) были OPEN/ready/CLEAN при начале этого среза; ни одна из этих веток не изменяется здесь.
- Integration/acceptance: guards существуют только в этой feature до merge; pure tests не закрывают M08/T11/T20, DB idempotency, downstream transaction, audit logs или browser flow.
- Источники: `ROADMAP.md` P2-05, `docs/architecture/match-engine.md` «Ручные действия», `docs/architecture/api.md` admin action routes, M08/T11/T20.
- Следующий шаг: после P2-01/P2-03 persistence integration хранить command receipts/actor/reason, атомарно выполнять run transitions/events и проверять downstream-start race; при этом old run/history сохраняются.
- Исторические аудиты bracket: [round invariant](https://github.com/D0UP1G/FirsterChuv/blob/feature/bracket-runtime/context/audits/2026-10-09T154602+0300-agent-2-A2-01-round-invariant.md), [coordination](https://github.com/D0UP1G/FirsterChuv/blob/feature/bracket-runtime/context/audits/2026-10-09T153228+0300-agent-2-A2-01-coordination.md).

Общий `context/STATE.md` меняет только координатор после merge.
