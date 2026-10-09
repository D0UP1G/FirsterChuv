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
| #54 | 94d42a0026c1b9c0c3b61ddf4ce3c25ac1ff4f8b | APPROVE как design reference после собственной correction auth preview; static HTML/CSS не React runtime |
| #55 | 95b1cec06836cab0501f033ad6f8aa6eca732c30 | APPROVE publication docs; current author sections сохранены вместе с #50/#51 |
| #56 | 3e99ae5368fd177f8342d49878ef137cd31974d9 | APPROVE Markdown brandbook reference; дополнительные идеи не расширяют MVP |
| #57 | 0073fbd96d38f657368ffa318d6ca23bff5f8a2d | REQUEST_CHANGES configured-run SQLite read→write race; HTTP/gateway пока нет |
| #58 | 733acc6c6d5928b219125fdbb817da1391418ef7 | REQUEST_CHANGES accepted/result SQLite races; FINALIZING/promotion добавлены, historical participant fix только в leaf #59 |
| #59 | 9eb394c88c64b1d22d90685c2eb44d946f91d755 | REQUEST_CHANGES SQLite races и downstream after rematch; participant snapshot исправлен в этом leaf |

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

## Последнее обновление авторов перед merge, 01:29 +03:00

#59 обновлён до 9eb394c: participant_user_ids закреплён на run и копируется в rematch/replacement; ledger больше не читает mutable slots. Historical probe теперь PASS: old result stored=True, current score не меняется (apply_result=False). Замечание к #58 original head остаётся верным, но в общем leaf #59 оно исправлено; сохранить этот fix, не реализовывать повторно.

19/19 runtime/ledger/admin tests PASS (19.276s). Все четыре настоящие SQLite race probes по-прежнему дают один успех и один uncaught lock error. Новый последовательный probe: technical winner полуфинала → rematch до начала финала. Upstream становится READY, downstream slot остаётся PLAYER со старым победителем; новый победитель rematch не может пройти: AdminCommandPersistenceError(downstream slot is no longer available for winner advancement). Нужен атомарный revoke/reopen downstream projection при допустимом rematch и новые advancement tests; после фактического downstream start пересмотр запрещён. Код #59 в coordinator feature не включён.

#54 обновлён до 94d42a0: добавлены горизонтальные уровни текста 24/12px и reference docs/audit. Все HTML изменения механически проверены: только CSS classes; CSS19 строк прочитан, own auth correction сохранена. Source head объединён обычным merge. Source scope не затрагивает React/runtime. Дальнейшие updates автора после этого снимка проверяются отдельно.

Первый remote CI [#60 run37999339340](https://github.com/D0UP1G/FirsterChuv/actions/runs/37999339340) на 014c98f: 5/5 SUCCESS. После latest design/docs checkpoint CI повторяется на новом опубликованном exact head до merge. [Новый publication audit](../../context/audits/2026-10-10T012946+0300-coordinator-readiness-publication.md).

A5 завершил первый UI срез локально: auth returnPath/query/hash и84 tests заявлены в его новой задаче; coordinator этот код не интегрировал и не выдаёт его за own verified PASS. Он ожидает handoff card в develop. После merge #60 его доступная очередь P5-01/02/03 продолжается на fresh develop; это конкретный unblock, не backend prerequisite.

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

## Итог слияния и последний source checkpoint

2026-10-10T01:36:20+03:00: #60 MERGED в develop723985f, final head9d7996d иCI37999734345 5/5 SUCCESS. #21/#50–52/#54–56 source PR такжеMERGED, original refs/main/audits сохранены. #53/#57–59 OPEN; base57–59 исправлен на develop без изменения source heads. #58/#59 имеют docs conflicts с новым handoff и должны ordinary merge fresh develop, сохранив author/coordinator sections. Слияние #60 снимает ожидание совместимой базы.

Latest #58 733acc6, полученный после snapshot01:29: добавлены deadline→FINALIZING, ожидание accepted pending, persisted winner/downstream и public-safe score event. Exact export runtime/ledger13 tests PASS (11.679s). Реальные file-backed probes снова: config/accepted/result — один success и один OperationalError(database is locked); old result после modeled replacement не сохранён, LedgerPersistenceError. Participant fix из9eb394c ветки#59 не входит в733acc6. Обе ветки нужно sync вместе с этими исправлениями, не считать feature branch base безопасной заменой GitFlow.

A5 follow-up о merge доставлен, compact wait подтверждает active: агент обновляет refs и продолжает local auth slice/card→PR, затем brand/responsive CONNECT по ROADMAP. A1–A4 получили назначения в документации; их внешние checkout/сессии coordinator не переключал. [Closing audit](../../context/audits/2026-10-10T013620+0300-coordinator-readiness-merge-verification.md). Working MVP по кейсу ещё не объявляется готовым.


## Последнее уточнение команды: три владельца и M0

2026-10-10T01:56:32+03:00. Активны A3, A4 (прежний A1/координатор), A5. A4 принимает весь competition backlog выбывшего A2 и API/common/events, A3 runtime/queue/tasks/judge и config/Compose/CI/system acceptance, A5 весь frontend. ROADMAP v5 сохранил все 30 parent P-ID; v4 сохранён в docs/history. 37 требований/21 сценарий остаются открыты в части полной acceptance. Чужие ветки/checkout/старые audit blobs не изменяются.

### Доступные и проверенные изменения

- #61 docs closeout MERGED (develop f327fbc), #62 auth safe-return-path MERGED (develop 85e0cd0), source abdc12e, CI38000494517 пять SUCCESS. Exact frontend source62:84 tests/18files PASS, type/lint/build PASS.
- #63 e116c03 reference conditions/assets/table/task attempts/manual pairs/visibility и уточнение ADR18: case p6 допускает commentary code после матча как optional, проект сохраняет author-only MVP. Runtime backend/frontend source не меняется. CI38000623798 attempt1 backend FAIL в concurrent same-key admission, sqlite3.OperationalError: database table is locked: submissions_queuecounter; attempt2 пять SUCCESS. Сбой сохранён и назначен A3 P3-04.1, rerun не fix.
- #64 dc124bcc React CSS/tokens/header/footer/metadata, 9 files including own card/3audits. Сохранены editor/router/auth safe next/HTTP permissions/DTO, Google Fonts имеет CSS fallbacks. CI38001142045 пять SUCCESS. Ordinary merge source63/source64 сохранён в coordinator feature/three-agent-mvp от85e0cd0. Combined frontend typecheck/lint/test/build exit0; 5 existing lint warnings/612.88kB editor chunk warning. New browser/layout/contrast acceptance NOT_RUN.
- #65 c735e67 basic responsive/focus: полный diff прочитан, source CI38001939464 пять SUCCESS. Backend/auth/API/editor behavior не меняет. В первом head own audit отсутствует, автору отправлено уточнение добавить его; после фактического merge/new audit результат фиксируется отдельным checkpoint.

### Runtime branches остаются на исправлении

#57 5ae4af5 — ordinary sync с develop, runtime.py unchanged относительно0073fbd, найденный configure race остаётся. #58 dc884e6 и #59 dcc9997 — последующие source checkpoints; actual admin_runtime.py unchanged относительно9eb394c, same-key replay и rematch/downstream finding не сняты. #59 содержит frozen participants плюс new clock/finalization, сохранить при исправлении. Это не утверждение о новых full suites: проверены incremental diff/unchanged affected source, прежние reproduced failures остаются evidence. #53 fd79038 cursor/equal-payload findings не исправлен. Ни один из этих failed runtime heads не включён.

### Остаток до первого реального матча

A4 safe persisted run/start/gateway/original participant+task snapshot/result+failure sinks/durable clock/winner; A3 actual compiler/import/executor/queue stability/factories/one-command runtime; A5 real endpoint CONNECT в существующий UI. M0 normalized tasks с настоящим verdict — промежуточный working slice, не полный обязательный MVP. Next M1: все management/both_ready/admin interventions/rich tasks/verdicts/drafts/recovery/security; M2: public SSE/map/projector/official/hostile/demo. Базовая безопасность обязательна до M0. [План](../../ROADMAP.md), [M0 gates](../quality/m0-demo.md), [source case](../source/Кейс_Платформа_соревнований.pdf).

Новому A5 отправлен explicit follow-up с тремя ролями и приоритетом M0, compact wait подтверждает active. Остальные владельцы получили назначение в Git; coordinator не утверждает, что автоматически запустил их внешние sessions. Individual WAITING_CONNECT записывается per port/route/SHA и сменяется independent READY task в той же сессии; полный roadmap task не заканчивается после одного PR при наличии разрешённой независимой работы.


### Source65 и целостность плана: checkpoint 2026-10-10T02:01:38+03:00

#65 updated head881d535 содержит новый own append-only audit P5-02; incremental diff только card/audit, responsive code идентичен c735e67 с source CI5/5 SUCCESS. Обычный merge выполнен без conflicts; App.tsx сохраняет одновременно бренд #64, safe auth return path #62 и responsive import #65. Автор сообщил DEV-only 320/390px/Tab checks, их не выдаём за independent real multi-session M0 или full visual acceptance на combined SHA.

Integrity PASS: все30 parent task headings v4=v5; все37 requirement IDs и21 T-ID сохранены;170 base context/audits files и4 incoming #63/#64 exact blobs неизменны; source65 audit будет добавлен в final check. Исторический v4 сохранён byte-for-byte; PDF SHA-256 неизменен; backend/scripts/config/CI/contracts diff относительно85e0cd0 zero. Frontend после65 проходит отдельный combined rerun, final exact-head CI требуется перед merge. Никакие unsafe runtime heads53/57–59 не включены.


Combined #63/#64/#65 frontend final rerun:18 files/84 tests PASS(28.53s), typecheck/lint/build PASS;5 прежних lint warnings и612.88kB chunk warning. Final integrity:170 base context/audits files +5 incoming source audits exact, all3 source heads ancestors; unsafe53/57–59 latest heads excluded; backend/config/CI/scripts/contracts diff zero. Полный browser/hostile/official M0 NOT_RUN.
