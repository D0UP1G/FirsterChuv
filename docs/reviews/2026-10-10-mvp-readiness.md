# Ревизия PR, готовность по кейсу и новый frontend owner

Снимок 2026-10-10T01:15:16+03:00, Europe/Moscow. База develop cc204e62a060eb2ceb16067a1b0693a2e083d9ab (через #49). Ветка координатора feature/mvp-readiness-handoff. Результаты ниже доступны в develop только после подтверждённого MERGED integration PR; не требовать отдельный STATE sync после code merge. [ROADMAP v4](../../ROADMAP.md).

## Exact heads и решения

| PR | Проверенный head | Решение и scope |
|---|---|---|
| #21 | 620f58e67ba0ad310ba0c65b41aface1bc3eaea2 | APPROVE private draft/CAS slice; прежний SQLite500 исправлен; real WorkspaceAccess ещё нет |
| #50 | 99d933e847e814e85352c16af35cf29bd9cdcf1a | APPROVE admin full pairings/reset HTTP, actor/reason/CSRF/idempotency/lifecycle/SQLite first-write; actual match runtime не добавлен |
| #51 | c7492a045ab0529c50310990b4579244d06be1ee | APPROVE append-only correction ошибочного полного SHA; исходные audits сохранены |
| #52 | 512d46e1a6d11b8d37ebd9dd5e2affd671568ec0 | APPROVE locked frontend CI; coordinator дополняет maxWorkers=1 для повторяемой resource concurrency |
| #53 | fd79038847a23b38bb8a444c028b87ce75ed9571 | REQUEST_CHANGES; snapshot concurrency/equal cursor correctness; не включён |
| #54 | 86208d54846377bba1f61f079081edf011f6a711 | APPROVE как design reference после собственной correction auth preview; static HTML/CSS не React runtime |
| #55 | 95b1cec06836cab0501f033ad6f8aa6eca732c30 | APPROVE publication docs; current author sections сохранены вместе с #50/#51 |
| #56 | 3e99ae5368fd177f8342d49878ef137cd31974d9 | APPROVE Markdown brandbook reference; дополнительные идеи не расширяют MVP |
| #57 | 0073fbd96d38f657368ffa318d6ca23bff5f8a2d | REQUEST_CHANGES configured-run SQLite read→write race; HTTP/gateway пока нет |
| #58 | 1f3fae5fc3ee70ab4e2bff713fd3a6cd7439d6a8 | REQUEST_CHANGES accepted/result SQLite races и mutable participants старого run |
| #59 | 7465a9c3ca0110a93bb5f8e5a4c63aecf80b42b8 | REQUEST_CHANGES same-command SQLite race; новые technical/rematch функции не включены |

#48/#49 после прежней ревизии меняют только A4 card/новые audits; входят в cc204e6, production/tests не меняли. Избранные source heads объединены ordinary merge commits; единственный docs conflict A2 card разрешён сохранением обеих секций. Shared app/include additions сохранили все существующие apps, drafts добавлена отдельно. Чужие feature refs/checkout не менялись, main bootstrap. Исторические docs/audits не считаются актуальным кодом.

## Снятый draft blocker

В #21 retry только SQLite primary/extended BUSY/LOCKED; максимум3, delays25/75ms, вся CAS transaction rollback до следующей попытки и re-read revision. Winning source не затирается: stale expectedRevision→409 currentDraft; exhausted→503 draft_busy без DB текста и с no-store. File-backed first-create/update races выполнены, history/revision exactly once. Реальный удержанный BEGIN IMMEDIATE с timeout20ms дал HTTP503 и0/0 draft/history, не mock OperationalError. Полный source review [перенесён в новый evidence audit](../../context/audits/2026-10-10T011516+0300-coordinator-mvp-readiness-review.md); подробности нового outcome audit ниже.

GET selector runId/404 принят координатором в [boundary decision](../../context/contracts/2026-10-10-mvp-boundaries.md). Это снимает ожидание API-решения, но не закрывает production workspace provider или полный T15.

## Оставшийся blocker #53

services.py:110–119 использует select_for_update, которое SQLite не даёт row lock. Два первых save_snapshot с barrier после обоих обычных SELECT: cursor8 True, cursor9 OperationalError(database is locked), stored cursor8. Более новый snapshot теряется. Отдельный probe: new run/cursor7 True; late old run/cursor7 True; stored run оказался old. Equal cursor другого run/payload нельзя считать безопасной повторной доставкой.

Root повторил probe на exact fd79038 в disposable file-backed export: оба дефекта подтверждены; внешний event+snapshot rollback PASS. Старые13 tests не покрывают эти interleavings. Нужны write-first/bounded full transaction retry, clear transient policy, равный курсор только identical snapshot идемпотентен; concurrent first-create/update/stale/equal conflicting tests. Это первое READY A4 P4-07, оно не требует PublicAccess/A2 judge/frontend. #53 остаётся открытым до fix/combined CI, branch автора не меняется.

## Поздние runtime PR #57–59: проверены, не включены

Снимок 01:24 +03:00. #57 направлен в feature/bracket-runtime, #58 в feature/a2-p2-03-readiness-runtime, #59 в feature/a2-p2-04-result-persistence. Это цепочка с base feature, source CI не запускается. По GitFlow PR должны идти в develop. После доступности #50 в develop retarget не требует переписывать source refs, но не исправляет код.

- #57 `backend/apps/competition/runtime.py:105–125`: configure_match_run открывает atomic, затем catalog может читать ORM до первого Match UPDATE. Probe с настоящим DB read внутри test catalog синхронизирует обе транзакции: одна создаёт run, другая получает uncaught OperationalError(database is locked). У mark/start свой first write имеется; это отдельный configure дефект. Нужен короткий write-first transition с повторной проверкой либо bounded retry всей завершившей rollback транзакции. Не держать DB lock при Docker/compiler probe.
- #58 `ledger_persistence.py:118–129,201–209`: accepted/result SELECT предшествует write claim. Два различных accepted и два результата на файловой SQLite дают по одному успеху и одному uncaught lock error; сохранена только одна строка каждого вида. `48–54` восстанавливает participant IDs из mutable MatchSlot, а не frozen participants original run. После моделирования замены игрока late result старой принятой посылки отвергнут: LedgerPersistenceError(stored receipts violate run ledger invariants), result не сохранён. Нужны immutable участники каждого run, bounded full retry и сохранение historical result без влияния на current score.
- #59 `admin_runtime.py:119–150` latest head: actor/receipt/current_run SELECT до первого UPDATE. Одновременная доставка одного extension command: один receipt/effect, второй uncaught lock error вместо exact replay/transient policy. Technical result/rematch добавлены поздним 7465a9c; старые snapshots/admin history не удаляются, но этот concurrency blocker остался и повторён на latest. Полная приёмка downstream/rematch/replacement ещё не выполнена.

Исходные tests #57–59: сначала 13/13 PASS; после обновления #59 — 16/16 PASS (19.122s). Это happy-path evidence, не доказательство конкурентной безопасности. Root повторил все четыре race probes и historical replacement probe на exact #57/#58 + latest #59 в disposable file-backed DB, timeout0.2: FAIL как выше. Пробы используют synthetic users/receipt и настоящий SQL; participant code не исполняется. Первый повтор tests без DJANGO_DEBUG/secret остановился на settings guard, повтор probe с прежним disposable DB — на duplicate fixture; свежий DB и test settings дали перечисленные результаты, эти setup ошибки не выдаются за product bugs.

Первое READY A2: исправить эти конкретные persistence slices и направить их в develop; готовые cores не переписывать. В резерве независимые HTTP permissions/serializers, run-scoped gateway/resolver/failure sink/finalization. Ни один source head #53/#57/#58/#59 не находится в coordinator ancestry. Подробный новый [closing audit](../../context/audits/2026-10-10T012406+0300-coordinator-late-pr-review.md).

## Design correction и handoff

#54 добавляет palette/tokens/13 HTML screens, own card/audit/ADR18; runtime/backend/contracts не меняет. Arena/spectator desktop screenshots просмотрены: отдельный editor/условие, arbitrary solved C без A/B, leader/penalty/time/projector, anonymous view, private source только workspace. Ресурсы — local CSS и Google Fonts CSS, JS/iframe/external executable отсутствуют. Layout не является реальным состоянием API.

02-auth.html native forms без method/action могли GET-submit password[name=password] в URL/history/logs. В integration correction все5 auth fields disabled, обе кнопки type=button; HTMLParser checks PASS. README объясняет React перенос через существующий session/CSRF client, preview disabled в production не переносить. Все исходные designer audit blobs сохранены. Последние #54 3f1b5bc/86208d5 переносят сетку с чёрной страницы внутрь карточек и упорядочивают отступы текста; эти изменения сохранены, inert auth correction осталась. #56 добавляет docs/source/brandbook.md. Магазин, чат, подсказки, достижения и показ кода из reference не назначены в MVP и не отменяют author-only privacy. Полная browser/mobile/контраст/real projector acceptance ещё нужна, font fallback входит P5-02.

## Выполненные проверки этой combined feature

- Django backend255 tests PASS с первого запуска,4 ожидаемых skips (125.880s).
- File-backed private draft18/18 PASS, без skips (10.088s); source review также18/18 и backend248/4skips PASS (108.816s).
- File-backed bracket API/persistence24/24 PASS (42.139s), включая same-key concurrency.
- Common9 strict fixtures/import without optional apps, domain68, sandbox unit15, Django check0/migration drift no changes PASS.
- Frontend18 files/82 tests PASS с maxWorkers1 (30.62s); TypeScript/build PASS, lint exit0 с5 прежними warnings; прежний editor chunk612.88kB warning сохраняется.
- Static auth preview structure checks PASS; #53 real file-backed probes FAIL как описано; это причина исключения, не скрытое successful evidence.
- Source #21/#50/#51/#55/#56 CI4/4 SUCCESS; #54 предыдущий 3f1b5bc 4/4 SUCCESS, latest 86208d5 проходит повторный CI; #52 CI5/5 SUCCESS на source SHA. #53 source workflow checks отсутствуют. Combined CI требуется на окончательном publish SHA, результаты будут новым checkpoint.
- Реальные Docker execution/hostile/official full pipeline, demo deployment и новый full browser T01–21 в этой сессии NOT_RUN. Предыдущий actual LocalJudge smoke остаётся историческим evidence неизменного provider, не новым full PASS.

## Готовность по блокам кейса

| Блок | Есть | До работающего требования |
|---|---|---|
|1 управление | реальные роли/auth/CRUD/roster/invites/bracket generate/read; новые pairs/reset | configured run/get/start/ready/clock persistence, durable ledger/finalization/promotion, persisted admin interventions |
|2 задачи | immutable normalized catalog/private split, safe Markdown/TeX UI, admin ready catalog | programmatic upload/import management, run-pinned workspace statement/assets/lang access, confirmed compiler readiness, official adapter |
|3 редактор/проверка | CodeMirror/editor/local recovery, draft CAS server core, queue/worker/outboxes, LocalJudge/sandbox cores | actual providers/factory/accepted version/checksum, real API→worker→judge→result→UI/history, server draft browser CONNECT |
|4 зрители | карта/projector React UI, public-safe store/projector schema, brandbook reference | snapshot fix #53, PublicAccess, producers/coherent snapshot+SSE, browser reconnect/resync |
|техника/сдача | ORM/strict inputs/CSRF/roles/privacy/sanitization, audit/history, CI | runtime hostile/injection/IDOR/leak acceptance, restart own-container fencing, one-command full build/start, official package/README, demo/video/release |

Исходный PDF: блоки1–3 обязательны; блок4 отдельно даёт до15 баллов, без него принимается с0 за визуализацию. Команда сохраняет карту в MVP. ВариантБ требует собственный isolated executor, настоящий verdict и реакцию на hostile code; generic mock не допускается. Official package содержит Markdown/TeX/assets/tests/limits/checkers/validators/reference, формат задаёт его README, которого агентам пока не предоставили. Не угадывать формат и не исполнять package scripts на host. Demo/video≤5мин и одна команда обязательны для сдачи. Яндекс только optional import после local working path.

Полного рабочего MVP пока нет: находятся проверенные модули на этапеR0, R1 ещё не accepted. Процент/срок до полного выполнения нельзя достоверно объявить по числу PR/unit tests. Приоритет — публиковать минимальные actual adapters и короткие CONNECT; новые pure cores/вне-MVP дизайн не должны отнимать его время.

## Новый агент и назначение остальных

A5 создан отдельной Codex задачей «Агент 5 — frontend и дизайн BLITZ_ARENA», thread01a122b2-27f9-7af0-ab77-dd282807d489, active snapshot подтверждает own checkout/feature отcc204e6. Весь frontend передан ему; историческиеP4-01–06 сохранены. A1 common/access/build, A2 fix #57–59/run/gateway/ledger/promotion, A3 actual judge/worker/workspace, A4 events fix/SSE/system evidence. Координатор обновил собственные и owner cards с датированным назначением, не переключал их checkout. Одно WAITING_CONNECT не завершает роль, у каждой свой READY резерв.
