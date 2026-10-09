# M0: первый работающий матч

Целевой промежуточный результат по ROADMAP v5. Статус всех полных строк: NOT_RUN/NOT_ACCEPTED. Часть компонентов уже проверена, но сквозного evidence на одном integration SHA нет. M0 не является полным хакатонным MVP: обязательные блоки 1–3, public map/SSE/projector и official/hostile/demo требования сохранены в requirements.md и mvp-acceptance.md.

## Сценарий

Одна документированная команда запускает frontend/API/worker/clock/migrations. Programmatic normalized demo import приносит 1–2 задачи с условиями, тестами и лимитами; приватные artifacts не в браузере. Реальный compiler probe выбирает доступный язык. Admin создаёт турнир/invite; две отдельные participant sessions входят по ссылке; admin задаёт набор/правила/duration и manual start. У обоих один frozen run/task/rules snapshot и server timer. Участники отправляют OK/WA/CE решения, API202 с durable source/queue, настоящий Docker compile/test. Собственная история/verdict/CE/draft и score обновляются без reload. После deadline FINALIZING ждёт accepted jobs; winner определяется сервером, следующий slot при наличии продвигается атомарно. Anonymous snapshot/map — следующий малый CONNECT; до SSE это не PASS T17.

## Результаты, которые нужно записать

| Gate | Владелец | Evidence / ожидаемое |
|---|---|---|
| G01 запуск/import/compiler | A3 | clean clone + exact SHA/env/image digest/одна команда; реальный compiler/bundle checksum, no fixture verdict |
| G02 invite/run/start/access | A4 + A5 | admin и две participant sessions, real HTTP, immutable participants/version/checksum/rules, denied чужой workspace/submit, CSRF |
| G03 accepted/job/result | A3 + A4 | server received_at один раз, queue/source после202, actual isolated compile/test→OK/WA/CE, durable result+failure delivery; duplicate не даёт новый effect |
| G04 UI/clock/winner/drafts | A5 + A4/A3 | condition/language/editor/own history/author CE/score безreload, server deadline, reload draft, FINALIZING→winner; delayed accepted OK считается |
| G05 safety/restart | A3 + A4/A5 | compiler/runner без сети/хоста/secrets/Docker socket; bounded limits; worker restart не теряет accepted source; no private leak/IDOR; controlled SQLite contention |
| G06 первый spectator CONNECT | A4 + A5 | anonymous public snapshot→existing map, no login wall/private fields; polling явно interim, SSE separately NOT_RUN |

## Независимые PR и CONNECT

1. A4 additive ports + safe run/config/start/read/gateway; A3 actual executor/normalized import/compiler и admission fix; A5 существующие auth/invite/admin/bracket typed clients. Все три READY сейчас.
2. A4 immutable run/snapshot/result+failure sinks + durable clock; A3 snapshot admission/outboxes/worker factory и startup Compose; A5 config/start/statement/language/draft/submit endpoints по одному.
3. A3 disposable M0 harness + одна команда; A5 real multi-session browser; A4 score/finalizing/winner/public access fixes. Missing один endpoint → exact WAITING_CONNECT + другой READY подпункт, не остановка роли.

Перед CONNECT читать docs/architecture/api.md, parallel-contracts.md, runtime-handoffs.md и contracts/mvp-v1. Поля/права не переопределять этой инструкцией. Existing real endpoints публикуются отдельно от UI. Незаполненная factory — fail-closed readiness/503, не mock fallback.

## Ограничения и следующие этапы

M1: both_ready, manual pairings/byes, pause/extend/rematch/technical/replacement с корректным downstream, rich official conditions/assets/checker, все verdicts, autosave/reconnect/privacy/security/recovery. M2: public SSE/map/projector/animation/resync, official package/hostile/full T01–21, repo/README/env/вариант Б/demo или video≤5min. Basic safety из G05 обязательна до M0. Official package пока отсутствует; normalized import не доказательство exact official support.

Каждый evidence file содержит exact integrated SHA, команды, результат PASS/FAIL/NOT_RUN, реальные ports/provider/image и ограничения. Не записывать пароли/tokens/source/закрытые tests. Tests с DI полезны для разработки, но не закрывают G01/G03/browser/hostile самостоятельно. Следующий шаг после этой ревизии: владельцы выполняют первые READY пункты v5, а не ждут все соседние PR.
