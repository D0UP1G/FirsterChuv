# Три активных владельца

Последнее прямое уточнение команды 2026-10-10 имеет приоритет над историческими карточками: A3, A4 (прежний A1/координатор) и A5. [ROADMAP v5](../../ROADMAP.md) сохраняет старые P-ID и готовые реализации.

| Агент | Зона | Первое READY | Карточка |
|---|---|---|---|
| 3 | problems/submissions/drafts/judge/sandbox + startup/config/Compose/CI/system acceptance | admission contention + actual LocalJudge executor/import | [agent-3.md](agent-3.md) |
| 4, прежний 1 | API/accounts/tournaments/competition/events/common contracts | additive ports + persisted run/gateway, ledger | [agent-4.md](agent-4.md) |
| 5 | весь frontend/design/editor/typed clients/map/browser UI | real auth/invite/admin/bracket CONNECT → workspace submit/result | [agent-5.md](agent-5.md) |

[Agent 1](agent-1.md) — исторический alias текущего A4, не четвёртый исполнитель. [Agent 2](agent-2.md) — выбывшая роль; competition задачи принял A4, ветки/аудиты не удалять. [Design](design.md) — источник reference; runtime frontend принадлежит A5, отдельная активная дорожка ему не назначена. [Координатор](coordinator.md).

READY/IN_PROGRESS/WAITING_CONNECT/WAITING_EXTERNAL/IN_REVIEW/DONE фиксируются отдельно для implementation/integration/acceptance. При конкретной зависимости записать route/port/producer/consumer/SHA и в той же сессии брать другой READY подпункт. Нельзя останавливать всю назначенную дорожку, пока есть независимая работа; явный стоп человека имеет приоритет. Назначение в Git не запускает чужую сессию и не делает чужие незакоммиченные файлы свободными.

Own isolated checkout, feature/* от fresh develop, PR→develop, ordinary merge, собственный append-only audit. Координатор добавляет датированную передачу владения с сохранением истории; текущие author IN_PROGRESS/final evidence выставляет сам владелец. Границы, [M0](../../docs/quality/m0-demo.md).
