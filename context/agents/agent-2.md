# Агент 2: сетка и live backend

Перепланировано координатором 2026-10-09 по опубликованному PR #7; собственные прежние аудиты владельца не переписаны.

- Реализация: algorithm/ORM/atomic generate/reset/pairing services готовы в feature/bracket-runtime, HEAD a89b8fc, PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) OPEN draft; пока не integrated.
- Проверки: координатор повторил 58 tests с test-only app/URL registration, no migration drift. Package import F03 исправлен; full T06/clock/played history ещё нет. F08 archived reset воспроизведён.
- Старый BLOCKED по A1-03 снят планом: roster/models/freeze интегрированы PR #8/#9. Новый статус задания **P2-01 READY**, не утверждение, что владелец уже возобновил сессию.
- Первое действие: сохранить a89b8fc и merge актуального develop; минимальные CompetitionConfig/URL добавления явно разрешены владельцу в этом же PR. Не ждать ответ A1. Прочитать обновлённый bracket/pairings DTO v1, ordinary suite/migration check; остальной clock/score писать без ожидания A3.
- Пути: backend/apps/competition, events; свои migrations/tests, fixtures match/public-match/score-event.
- Очередь: P2-01 PR slice → P2-02 persistence → P2-03 clock/start → P2-04 score/ledger → P2-05 admin actions → P2-06 snapshots/SSE. Pure clock/score/event store доступны без judge/importer/UI.
- Во время ожидания CONNECT: продолжить свои pure/domain tests или event store. Не блокировать всю роль из-за очереди посылок A3.
- История аудитов feature: [round invariant](https://github.com/D0UP1G/FirsterChuv/blob/feature/bracket-runtime/context/audits/2026-10-09T154602+0300-agent-2-A2-01-round-invariant.md), [coordination](https://github.com/D0UP1G/FirsterChuv/blob/feature/bracket-runtime/context/audits/2026-10-09T153228+0300-agent-2-A2-01-coordination.md).
- Следующий шаг: обновить свой branch/base/status и stale PR body; штатно зарегистрировать app, исправить F08, сделать HTTP pairing/reset по v1. Сохранить уже выполненные rank/persistence/import изменения, full T05/T06 не объявлять пройденными.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
