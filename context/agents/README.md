# Владельцы проекта после передачи frontend

Перепланировано координатором по прямому поручению команды 2026-10-10. Исторические cards/audits сохранены; новые назначения — ROADMAP v4.

| Агент | Зона | Карточка |
|---|---|---|
| 1 | common contracts/security/PublicAccess/Compose/startup | [agent-1.md](agent-1.md) |
| 2 | competition/configured run/clock/gateway/ledger/promotion/admin effects | [agent-2.md](agent-2.md) |
| 3 | problems/submissions/drafts/judge/sandbox/worker | [agent-3.md](agent-3.md) |
| 4 | events/snapshots/public HTTP/SSE и системная приёмка | [agent-4.md](agent-4.md) |
| 5, новый | весь frontend/design/editor/clients/map/browser UI tests | [agent-5.md](agent-5.md) |
| design | источник брендбука, React runtime не владеет | [design.md](design.md) |

Статусы READY/IN_PROGRESS/WAITING_CONNECT/WAITING_EXTERNAL/IN_REVIEW/DONE. Разделять implementation/integration/acceptance; DONE core не означает full case PASS. При зависимом CONNECT брать следующий независимый пункт, не завершать всю дорожку. Explicit user stop имеет приоритет.

Карточку ведёт её владелец. Координатор по текущему прямому поручению добавляет датированное назначение, сохраняя исторические записи. P4-01–06 функционально остаются UI, переданы A5; P4-07–09 назначены A4. Чужая незакоммиченная работа не становится свободной из-за новой таблицы. Own isolated checkout, feature/* от fresh develop, короткие PR→develop и append-only audits. [Координатор](coordinator.md), [план](../../ROADMAP.md), [границы](../contracts/2026-10-10-mvp-boundaries.md).
