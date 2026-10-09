# Состояние проекта при разблокировании агента 3

Снимок 2026-10-09, Europe/Moscow. На старте проверки develop `13cd2d4` (#29); #25 отдельно MERGED `ed14416`; перед публикацией включён A4 #30 `8c6836b`, перед итоговым merge — A4 #31 `b9c25cb`. Main `e9fc0ef` остаётся bootstrap. PR #20 MERGED: sandbox/clock/score/catalog/admin guards в develop. Также MERGED frontend #22/#24/#27/#28/#29/#30/#31.

В `feature/agent-3-merge-unblock` обычными merge commits объединены проверенные #26 `435cef7` admin catalog, #15 `555ca0e` queue race fix и #23 `942b4f5` LocalJudge. До MERGED её integration PR эти три среза находятся в проверенной feature; после MERGED доступны в develop. Исходные feature refs, аудиты и frontend/карточка активного A4 сохранены. Не ждать ещё одного STATE PR после подтверждённого code merge. [Аудит и конкретные следующие задачи](audits/2026-10-09T224851+0300-coordinator-agent-3-unblock.md).

Integration [PR #32](https://github.com/D0UP1G/FirsterChuv/pull/32) опубликован; первый head получил 4/4 CI PASS, после fresh #31 финальные checks повторяются. [Publication checkpoint](audits/2026-10-09T230104+0300-coordinator-agent-3-publication.md). Этот текст — checkpoint перед операцией; фактический MERGED/remote refs определяют доступность кода.

## Что есть и чего нет

| Компонент | Реализация / интеграция | Остаток до working MVP |
|---|---|---|
| User/common/auth/roles/CSRF | develop #2/#5 | Full browser/object/runtime security acceptance |
| CRUD/roster/seed/freeze | develop #8 | Played-history и browser acceptance |
| Invite backend | develop #12 | A4 реальный browser register/accept flow |
| CI/schemas/common ports | develop #17/#18/#19, 4 jobs pass | Required protection отсутствует; реальных providers ещё нет |
| Sandbox harness | develop #20; обновление task limits из #23 в текущей feature | Fresh image обязателен для нового run argv; ML/checker/worker/official full T18 |
| Pure clock/scoring | develop #20, #11 28d6cda/#13 19bbf88 | Persisted run/start/API/gateway/ledger/finalization/promotion |
| Normalized catalog | develop #20/#25; admin catalog #26 в текущей feature | Normalized import/status API, verified compiler/workspace HTTP/official adapter |
| Bracket ORM/API | #7 обновлён до 1a2b54a, fix опубликован; не включён в эту проверку A3 | Review нового lifecycle fix, потом full reset/pairing HTTP |
| Queue core | #15 555ca0e в текущей feature; SQLite race исправлен, 29 file-backed tests pass | Actual worker/provider/result+failure adapters, runtime CONNECT |
| Event store | #16 обновлён до 6eac91f; новая версия вне текущего A3 review | Проверить новый head; исторический B03 относится к 8340014; producers/access/snapshots/SSE CONNECT |
| Admin guards | develop #20, 8f5b762 | Pure guards; настоящие command store/effects/HTTP отсутствуют |
| LocalJudge | #23 942b4f5 в текущей feature; real Docker/synthetic bundle OK | Worker deployment/readiness, verified compiler, official checker protocol |
| Private drafts | #21 1706ecf OPEN: воспроизведён CAS busy→500 | P3-05.1 bounded retry/revision conflict/503 перед merge |
| Frontend | develop #22/#24/#27/#28/#29/#30/#31, UI P4-01–05 + regression tests | Текущий A4 browser/API CONNECT по endpoint, full acceptance |
| Official package/README | Не получены | Только adapter/final official acceptance WAITING_EXTERNAL |
| Full one-command demo/release | Не готовы | R1→R2→R3; main не релиз |

Текущая проверка: 150 backend tests PASS с 2 ожидаемыми skips после одного записанного P1 concurrency FAIL; отдельно 29 file-backed submissions, 9 strict fixtures/common import, 36 domain и 15 sandbox unit PASS; migration drift нет. Fresh frontend #31: 16 files / 64 tests и TypeScript/Vite build PASS. На отдельном свежем image #23: 5 actual sandbox smoke, task limit 100 ms/64 MiB и 1 real LocalJudge smoke PASS. Production image/tag и compiler readiness не менялись; официальный/полный hostile/browser T01–21 acceptance не закрыт. GitHub CI и publication записаны в publication checkpoint.

## Следующая работа одновременно

1. A1: P1-03 public/share access и proxy/logging; резерв P1-04 infrastructure + P1-02.5 additive failure handoff. Прежний explicit stop отдельной сессии учитывается, документ не запускает её автоматически.
2. A2: P2-02.1 fix #7, P2-06.1 fix #16; затем настоящий MatchRun/API/gateway/ledger, сохраняя готовые pure cores. Резерв command store/actions/projector.
3. A3: P3-02.2 normalized import management (merge-блокер #25 снят), P3-04.2 actual worker; резерв P3-05.1 исправление CAS race #21. Только production ports/version binding подпункт WAITING_CONNECT и P3-06 package WAITING_EXTERNAL.
4. A4: продолжать активный browser/API CONNECT; UI срезы уже опубликованы и интегрированы. Catalog #26 совместим с текущим frontend paginated request; подключение проверить по одному endpoint после merge. Карточка и исходники A4 этой проверкой не менялись.

При зависимости WAITING получает подпункт, исполнитель продолжает следующий READY шаг в той же сессии. [ROADMAP v3](../ROADMAP.md), [ревизия всех PR](../docs/reviews/2026-10-09-integration-review.md), [runtime handoffs](../docs/architecture/runtime-handoffs.md). Fetch актуального develop перед стартом; авторские feature refs/старые аудиты сохранены, shared app/CI registrations не заменять старыми полными копиями.
