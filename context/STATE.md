# Состояние проекта после повторной ревизии

Снимок 2026-10-09, Europe/Moscow. Исходный develop `dd80c933083eea8ac234a17593a6a54a09ded53d` (#19), main `e9fc0ef` bootstrap. Проверенный состав текущего coordinator feature/mvp-integration-review-2 включает пять готовых heads #3/#11/#13/#14 и admin guards 8f5b762. Факт общей интеграции определяется MERGED общего PR/remote refs, публикация записана в новом coordinator audit. Документация внутри feature не объявляет будущий merge выполненным.

## Что есть и чего нет

| Компонент | Реализация / интеграция | Остаток до working MVP |
|---|---|---|
| User/common/auth/roles/CSRF | develop #2/#5 | Full browser/object/runtime security acceptance |
| CRUD/roster/seed/freeze | develop #8 | Played-history и browser acceptance |
| Invite backend | develop #12 | A4 реальный browser register/accept flow |
| CI/schemas/common ports | develop #17/#18/#19, 4 jobs pass | Required protection отсутствует; реальных providers ещё нет |
| Sandbox harness | #3 6950f10 включён в integration feature | F01/F07 исправлены; task-specific limits/ML/checker/worker/official full T18 |
| Pure clock/scoring | #11 28d6cda/#13 19bbf88 включены в integration feature | Persisted run/start/API/gateway/ledger/finalization/promotion |
| Normalized catalog | #14 9234951 включён в integration feature | verified compiler/import/workspace HTTP/official adapter |
| Bracket ORM/API | #7 1952244 не включён: lifecycle B01/F08 | Fix draft/scheduled guard, потом full reset/pairing HTTP |
| Queue core | #15 7d76d0b не включён: concurrent admission B02 | Fix busy→503/retry/race, worker/provider/production adapters |
| Event store | #16 8340014 не включён: SOLVED.lastVerdict B03 | Fix OK→WA, producers/access/snapshots/SSE |
| Admin guards | feature/match-admin-actions 8f5b762 включена в общий integration feature | Pure guards; настоящие command store/effects/HTTP отсутствуют |
| Frontend | Опубликованных refs/PR нет | React build/auth/admin/editor/map и CONNECT |
| Official package/README | Не получены | Только adapter/final official acceptance WAITING_EXTERNAL |
| Full one-command demo/release | Не готовы | R1→R2→R3; main не релиз |

Совместная интеграционная сборка: 105 Django tests passed, migration drift нет, 36 clock/score/admin и 12 sandbox unit pass, standard image rebuilt/5 actual smoke pass. Bounded Docker probes подтверждают F01/F07 fixes и isolation/cleanup/recovery на exact #3 HEAD, не всю безопасность официального judge. Полные T01–21 остаются NOT_RUN.

## Следующая работа одновременно

1. A1: P1-03 public/share access и proxy/logging; резерв P1-04 infrastructure + P1-02.5 additive failure handoff. Прежний explicit stop отдельной сессии учитывается, документ не запускает её автоматически.
2. A2: P2-02.1 fix #7, P2-06.1 fix #16; затем настоящий MatchRun/API/gateway/ledger, сохраняя готовые pure cores. Резерв command store/actions/projector.
3. A3: P3-04.1 fix #15, затем LocalJudge/worker/registry. Резерв private drafts/import/assets; только P3-06 ждёт package.
4. A4: P4-01 real React/auth и P4-02 уже готовые CRUD/invites. Резерв editor/local draft/map reducer; будущие APIs через dev transport до CONNECT.

При зависимости WAITING получает подпункт, исполнитель продолжает следующий READY шаг в той же сессии. [ROADMAP v3](../ROADMAP.md), [ревизия всех PR](../docs/reviews/2026-10-09-integration-review.md), [runtime handoffs](../docs/architecture/runtime-handoffs.md). Fetch актуального develop перед стартом; авторские feature refs/старые аудиты сохранены, shared app/CI registrations не заменять старыми полными копиями.
