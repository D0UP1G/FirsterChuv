# Агент 2: сетка и live backend

Перепланировано координатором 2026-10-09 по ROADMAP v2; старые A-ID — только исторические ссылки.

- Статус: `IN_PROGRESS` — P2-03.1 pure clock core; persisted lifecycle/start/clock command и MatchPort ещё впереди.
- Исполнитель: Codex в роли агента 2.
- Текущая задача/ветка/база: `P2-03.1` / `feature/match-clock-start` / актуальная `origin/develop` `d9488e3`. Чистый clock commit `c6789a7` сохранён, выполняется sync с новой документацией.
- Рабочий checkout: `work/FirsterChuv-agent2-clock`.
- Пути текущего среза: `backend/apps/competition/domain/clock.py`, `backend/apps/competition/tests/test_clock.py`, эта карточка и аудит.
- P2-01: bracket algorithm/ORM/generation/read slice опубликован в PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7), HEAD `1952244`, OPEN/ready/CLEAN; штатная suite 58 passed, migration check чистый.
- Выполнено в P2-03.1: aware UTC timestamps, elapsed ms без учёта pause intervals, READY→RUNNING, pause/resume arithmetic, строгий `< deadline` admission, idempotent RUNNING→FINALIZING, validation времени/параметров; 12 pure unit tests прошли до sync.
- Дорожка: P2-02 persistence/lifecycle HTTP, P2-03 clock/start, P2-04 scoring/ledger, P2-05 admin actions, P2-06 events/SSE. Pure clock/score/event store разрешены без ожидания judge/importer/UI.
- Следующий шаг: завершить merge актуальной develop и публикацию проверяемого P2-03.1 slice; затем расширить clock/start state machine по `match.json` с immutable task/rule config и `manual`/`both_ready`. DB MatchRun wiring требует merge P2-01 и отсутствующие MatchRun lifecycle fields.
- Порты: использовать `ProblemCatalogV1.describe_ready`, `CompetitionGatewayV1.authorize_submission/register_accepted/apply_result`, `EventWriter` только по v1. Отсутствующий runtime provider должен fail closed; test catalog допустим только в tests.
- Владеет: `backend/apps/competition/`, `backend/apps/events/`, собственными migrations/tests; общие настройки и другие apps не менять без разрешённого узкого wiring.
- Последние аудиты: [A2-02.1 clock core](../audits/2026-10-09T164411+0300-agent-2-A2-02-clock-domain.md); аудит sync/publication этого P2-03 среза будет добавлен после проверки.

Разделять implementation, integration и full acceptance. Общий `context/STATE.md` обновляет координатор после merge.
