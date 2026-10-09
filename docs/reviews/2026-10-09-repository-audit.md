# Ревизия репозитория, PR и координации

Дата проверки: 2026-10-09, Europe/Moscow. Репозиторий [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv). Снимок до документационного PR этой ревизии: `main=e9fc0ef97dcb83d2beffa41f42cb873ebcde71bc`, `develop=146b2cb64a6273472c2de9cae04bfad21acd1782`. Последующее движение refs проверяется повторно, отчёт не является live dashboard.

## Объём и результат

Проверены опубликованные refs/history, все 9 PR со списками файлов/коммитов/комментариями/reviews/checks, 30 уникальных аудитов в context из develop и двух открытых веток, карточки и документация. Выполнено чтение ключевых реализаций auth/CSRF/roles/serializer/error/roster/freeze/SQLite/proxy/contracts, алгоритма A2 и всего launcher/container runner A3; существующие suites повторены. Незакоммиченная/неопубликованная работа вне известных checkout и фактическое состояние будущего demo-хоста не подтверждаются этой ревизией.

GitFlow в опубликованной истории соблюдён: main — bootstrap, feature PR имеют базу develop, слияния сохраняют merge commits. 7 PR merged, 2 open; релизов/тегов/issues/actions runs нет на момент проверки. У всех девяти PR formal reviews и status checks пустые; main/develop `protected=false`. Это означает отсутствие технического review/check gate, не отсутствие всех проверок: часть команд записана в аудитах и повторена ниже.

Общая проблема: большой A-ID одновременно означает реализацию и полную сквозную приёмку. Поэтому агент продолжает ждать уже слитые модели, а готовый domain slice держится draft до завершения соседнего модуля. В новом плане implementation slice, CONNECT и финальная acceptance разделены.

## Все PR

| PR | Состояние / head / merge | Проверенный результат и следующий шаг |
|---|---|---|
| [#1](https://github.com/D0UP1G/FirsterChuv/pull/1) | MERGED; edd10ea → e5f421b | Контекст, архитектура, кейс. PDF checksum совпал; исходный ROADMAP уже устарел относительно кода. Сохранён в history и заменён v2. |
| [#2](https://github.com/D0UP1G/FirsterChuv/pull/2) | MERGED; ccf8eea → 2484d86 | Bootstrap/custom User/common API/Compose scaffold. Аудит подтверждает только API container, runtime/web profiles не готовы. |
| [#3](https://github.com/D0UP1G/FirsterChuv/pull/3) | OPEN; 3a0d865; не draft | Docker harness, без official importer/worker. **P1: container create падает из-за --pid=private.** Нужен P3-01 перед принятием runnable slice. |
| [#4](https://github.com/D0UP1G/FirsterChuv/pull/4) | MERGED; 7e10d0d → be0323c | A1-01 STATE sync; исторически верен, не новый runtime результат. |
| [#5](https://github.com/D0UP1G/FirsterChuv/pull/5) | MERGED; 3b1be0c → c64555c | Session auth/CSRF, global roles, bootstrap admin. Role injection закрыт; full domain/browser/security acceptance ещё нет. |
| [#6](https://github.com/D0UP1G/FirsterChuv/pull/6) | MERGED; 5885984 → 3b2b0ad | A1-02 STATE sync. Нельзя считать этот SHA последней базой A2: PR #8/#9 уже merged. |
| [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) | OPEN draft; первоначально db67be4, обновился до a89b8fc | Последний HEAD: ORM/atomic generate/reset/pairing services, 58 tests с временной registration прошли. Package import исправлен. Remaining: штатные app/URL registration, HTTP pairing/reset/lifecycle/idempotency; clock/score ещё нет. |
| [#8](https://github.com/D0UP1G/FirsterChuv/pull/8) | MERGED; 5163f6c → b894716 | CRUD/roster/nullable seed/atomic cap/freeze. Основная зависимость A2 уже доступна. History с настоящим сыгранным Match ещё не проверена. |
| [#9](https://github.com/D0UP1G/FirsterChuv/pull/9) | MERGED; e9ad812 → 146b2cb | A1-03 STATE sync. Карточка и STATE ещё предлагали открыть уже merged sync PR; исправлено в этой ревизии. |

Открытые PR принадлежат их авторам. Ревизия не меняла их refs, draft/status/body и не сливала код. Все выводы относятся к перечисленным head SHA, а не к будущему исправлению.

## Замечания с приоритетом

### F01 · P1 · sandbox не запускается на доступном Docker

`feature/sandbox-proof:sandbox/runner.py`, `build_docker_create_args`, строка с `--pid=private`: Docker 29.8.2 возвращает exit 125, `docker: --pid: invalid PID mode`. Образ успешно собран; неизменённый `sandbox/smoke.py --case all` даёт exit 2 `NOT_VERIFIED: Docker could not create the sandbox container`. 8 unit-тестов проходят, поскольку проверяют состав argv/подменённый subprocess, а не действительность Docker options.

Диагностическая временная копия без этого одного флага дала настоящие OK/WA/TIME_LIMIT/OUTPUT_LIMIT. Чужая ветка не исправлена, эти результаты не означают PASS исходного PR или полной изоляции. **Владелец A3, P3-01:** корректное отдельное PID namespace, regression/runtime checks, audit; memory/pids/network/host/secrets/cleanup и official package ещё не доказаны.

### F02 · P1 для координации · актуальная база и статусы не доходят до потребителя

На первом снимке PR #7/card A2 ожидали A1-03 и ответ на nullable seed/freeze. PR #8 уже содержит User/TournamentParticipant/freeze и canonical ordering, а PR #9 в develop. Freeze не назначает DB seed; A2 должен превратить canonical order во временный rank 1..N. Это явно следует реализованному сервису и match-engine, не требует изменения roster A1. Reset не снимает freeze. **Владелец A2, P2-01/02.** Во время ревизии a89b8fc уже реализовал rank/freeze/persistence; новая очередь продолжает эту работу и не пишет её повторно.

Карточки A2/A3 в develop всё ещё TODO, хотя есть PR/аудиты в их feature branches; основной ROADMAP говорил «приложение не написано, всё TODO». README/docs index/API/acceptance называли roster несмерженным. Исправлено в этой документационной ветке; historical audits сохранены.

### F03 · P2 · package import исправлен в новом HEAD, нужна штатная регистрация

На первоначальном db67be4 тесты импортировали domain.bracket и зависели от discover/PYTHONPATH. В опубликованном во время ревизии a89b8fc автор исправил import на полный backend.apps.competition.domain.bracket. Координатор повторил 58 tests с временным включением CompetitionConfig и URL; suite прошла, migration drift отсутствует. **Первоначальный дефект закрыт кодом a89b8fc**, не integrated merge.

Общая конфигурация app/URLs ещё не включает. Новое правило AGENTS/ROADMAP явно разрешает владельцу app минимальную регистрацию в том же feature PR с модулем, не ждёт отдельного ответа A1. После этого P2-01 проверяет обычный запуск/tests. Другие shared настройки остаются у A1.
### F04 · P2 · качество не закреплено GitHub checks

Reviews/checks отсутствуют во всех PR; branch protection выключена. Audits не являются CI. **A1/P1-02:** backend/domain/contract checks, отдельный real Docker smoke gate и рекомендации protection. Не запускать runtime mock вместо Docker; настройку GitHub policy делать только в рамках разрешённого управления репозиторием и подтверждать фактическое применение.

### F05 · P2 · public access и proxy ещё требуют отдельного доказательства

Tournament model/API уже разрешает visibility=unlisted, но share-token storage/reader пока не реализованы; anonymous endpoints отсутствуют, текущего public leak этим не установлено. **A1/P1-03 + A2/P2-06:** hashed read token/guards перед публикацией. `NUM_PROXIES=1` сочетается с открытым local API port; независимая проверка direct/proxied forwarded headers нужна перед demo. Это риск конфигурации, обход лимита в этой ревизии не воспроизводился.

### F06 · обязательная незавершённая работа

На последнем feature HEAD a89b8fc появилась persisted сетка/Run models, но она не integrated и ещё не зарегистрирована штатно. Нет clock/scoring, invite flow, ProblemCatalog/official adapter, LocalJudge всех verdicts, durable queue/drafts, React/SSE/карты, единой команды полного запуска. Harness fixed limits не заменяют time/memory limits каждой задачи. Common Protocol не является реализованным provider. Это задачи MVP, не дефекты уже обещанной demo: README честно не заявляет готовность. Полные T01–21 и release gate остаются открытыми.

### F07 · P1 · solution может писать в stdout supervisor, host capture не ограничен при чтении

В диагностической копии после удаления неверного PID-флага выполнена bounded C++ probe: открыть `/proc/1/fd/1`, записать 30 байт собственного маркера, завершиться. На run phase захваченный response действительно начинается маркером solution (145 байт всего); `parse_response` отклоняет его как invalid protocol. Compile response обычный. Wrapper и solution работают под одним UID, поэтому файл stdout `/work/program.stdout` не является единственным доступным каналом вывода.

В `sandbox/runner.py:_run_docker` `subprocess.run(..., stdout=PIPE, stderr=PIPE)` собирает response целиком; MAX_RESPONSE_BYTES проверяется только позже в parse_response. Следовательно, лимит файла stdout solution не ограничивает прямую запись в supervisor pipe, и потенциальный большой поток сначала расходует память host launcher. **Не выполнялся** бесконечный/большой flood, истощение памяти не проверялось, успешная подделка verdict не установлена: текущий parser отказывает. Но граница bounded host capture требует исправления перед hostile acceptance.

**A3/P3-01:** запретить solution доступ к supervisor protocol descriptors (разные права/изоляция `/proc`/другая защищённая схема), ограничить stdout/stderr во время чтения host-side с остановкой своего контейнера при overflow; не полагаться только на cap после communicate/parse. Добавить bounded regression probe и normal execution после неё. Изолированность контейнера от host не заменяет целостность judge protocol внутри контейнера.

### F08 · P2 · reset изменяет archived tournament

На a89b8fc `competition/services.py:reset_bracket` и set_first_round_pairings проверяют отсутствие played run, но не editable lifecycle турнира. freeze_roster идемпотентно возвращает уже frozen roster независимо от последующей архивации. В отдельной временной SQLite базе: создать 2 entrants → generate → установить ARCHIVED → reset; операция успешно заменила match UUID. Проба целиком откатилась, реальные данные не затронуты.

**A2/P2-02:** lifecycle guard draft/scheduled внутри общей transaction для reset/pairings/generate mutation, regression test; reason/command idempotency и HTTP routes ещё в работе. Пока endpoint reset не зарегистрирован, это service-level дефект и будущая API граница, не подтверждённая атака на публичное demo.

## Обновление во время ревизии

Fetch на 16:30 показал новый `a89b8fc8d5dce0657f44a559c302ae97c5b0a5b4` в PR #7. Он включает merge b894716 (A1 roster) и 1368 additions/17 deletions собственного среза. Прочитаны новые models/services/serializers/views/urls/tests/migration и [audit persistence](https://github.com/D0UP1G/FirsterChuv/blob/a89b8fc8d5dce0657f44a559c302ae97c5b0a5b4/context/audits/2026-10-09T162433+0300-agent-2-A2-01-persistence.md). Исходный F03 исправлен; static/DB review выявил F08.

Bracket fixture/DTO v1 обновлён к фактическому serializer `{matches,slots.participant:{id,userId,...}}`, не навязывает конкурирующий nodes DTO. Internal builder использует entrant row UUID, внешний actor — User UUID. Full first-round PUT pairings DTO зафиксирован, adapter преобразует User IDs в row IDs. Minimal AppConfig/URL registration владелец делает в этом же feature PR, сохраняя GitFlow и атомарную поставку модуля. Следующий clock/catalog consumer разрабатывается по DI, не ждёт A3 importer.

## Повторённые проверки

| Среда / SHA | Команда | Результат и граница |
|---|---|---|
| Изолированный worktree от develop 146b2cb, Python 3.14.7 | `uv sync --frozen` | Успех, locked dependencies установлены; uv.lock не изменён |
| Та же база, DJANGO_DEBUG=true, SQLITE_PATH во временном каталоге | `uv run --no-sync python manage.py test backend.apps --verbosity 1` | **37 passed**, 23.576s; тестовая SQLite, не live browser/demo |
| Та же база | `manage.py check`; `makemigrations --check --dry-run` | 0 issues; No changes detected |
| Начальная архивная копия PR #7 db67be4 | `PYTHONPATH=backend/apps/competition python3 -m unittest discover -s backend/apps/competition/tests -v` | **8 passed**, domain only; отдельная попытка без path получила ImportError, см. F03 |
| Изолированная архивная копия PR #7 | `python3 -m unittest discover -s backend/apps/competition -v` | **8 passed**, авторская команда; не ORM/API/T06 целиком |
| Изолированная архивная копия PR #3 3a0d865 | `python3 -m unittest discover -s sandbox/tests -v` | **8 passed**, протокол/flags/fail-closed unit only |
| Та же копия | `g++ -std=c++20 -Wall -Wextra -Werror -fsyntax-only sandbox/container_runner.cpp` | Успех, не execution |
| Docker Engine 29.8.2, образ 994c2401d940, base digest закреплён PR | `docker build --platform=linux/amd64 --tag firsterchuv/sandbox-cpp:0.1.0 sandbox` | Сборка прошла |
| Неизменённый PR #3 | `python3 sandbox/smoke.py --case all` | **FAIL/NOT_VERIFIED**, exit 2; create argv exit 125 invalid PID mode |
| Только временная диагностическая копия: удалён --pid=private | Тот же real smoke | **4 cases passed**: OK, WA, TIME_LIMIT, OUTPUT_LIMIT. Не исходный SHA, не официальный пакет, не full T18 |
| Та же diagnostic copy, только ограниченный marker write | C++ open `/proc/1/fd/1` + write 30 bytes; Python observation перед parse | Solution marker подтверждён в supervisor response; fail-closed invalid protocol. Unbounded flood не запускался; см. F07 |
| Новая архивная копия PR #7 a89b8fc, свои временные settings/URL, тот же Python/locked deps | `manage.py test --settings=review_a2_settings`; migration drift | **58 passed**, 47.187s; app включена только test settings, штатное подключение/clock не проверены |
| a89b8fc, отдельная временная SQLite, rollback всей пробы | generate → ARCHIVED → reset | **F08 воспроизведён:** reset разрешён, UUID заменены; не browser/API |
| PDF в develop | `sha256sum`, чтение всех 8 страниц | Совпадает с источником: 8d0d0a843b00ac4d35845fabf02963f793ee3115870fa5f3b108176f809bd008 |

Docker запускал решения только в отдельных контейнерах, никакой solution не исполнялся на host/API. Созданные harness containers удалены launcher-ом; image сохранён для повторной проверки владельцем. Локальная venv и временные базы/архивы не коммитятся. Повторный полный Compose/browser/security/official-package scenario не выполнялся; 37+8+8 не считаются T01–21.

## Сверка аудитов

- A1: последовательность 3 → 16 → 37 tests соответствует развитию code slices. Частичные T02/T03/T05/T20 не выданы за full PASS. Ранние NOT_RUN относятся к тому времени, их не следует переписывать.
- A2: начальные audits правильно описывают pure algorithm/8-й invariant test и исторический blocker. Новый аудит 16:24–16:27 описывает ORM, test registration и 58 tests; этот результат повторён координатором. Остаётся ожидание common registration/pairing DTO, которое снимается явной минимальной передачей и контрактом v1. PR body ещё описывал прежний scope — обновить владельцу, старые audits сохранять.
- A3: честно фиксировал недоступный Docker/NOT_RUN, не заявлял isolation pass. Сейчас Engine доступен, но выявлен дефект argv. README/card о недоступности Engine нельзя использовать как нынешнюю причину остановки.
- Семантика DONE местами относится к feature-only подшагу. Новый план отделяет «срез выполнен», IN_REVIEW/DONE integration и full requirement acceptance. Наличие карточки в open feature не означает код в develop.
- Три отдельные STATE sync PR полезны как история, но ожидание их слияния перед новой задачей создало дополнительный барьер. Новое правило: продолжать после реального code merge, snapshot обновлять отдельно на рубеже, не делать из него prerequisite.

## Покрытие кейса и порядок продолжения

| Кейс | Фактический статус | План |
|---|---|---|
| Управление, стр. 5 | M01/M03 backend частично; grid ORM появился в a89b8fc feature, нет invites/played history/runtime | P1-01, P2-01–05, P4-02/03 |
| Условия, стр. 5 | Official package/README не получены, нет importer/UI | P3-02/06, P4-04; internal kernel не ждёт внешний mapping |
| Редактор, стр. 6 | Нет UI/source/draft/queue/полного judge | P3-03–05, P4-04 |
| Зритель, стр. 6 | Нет public endpoints/SSE/map/projector | P2-06, P4-05 |
| Изоляция/устойчивость/права, стр. 7 | Auth/role/roster guards есть; sandbox PR не запускается; full security не доказана | P1-02/03, P3-01/04, проверки всех владельцев |
| Запуск/сдача, стр. 7 | Только API scaffold/частичный smoke, без release/demo | P1-04/05, P4-06 |

Блоки 1–3 обязательны. Блок 4 отдельно оценивается, команда включает его в MVP. Все ручные вмешательства, автоматический both_ready start, explicit tie/rematch, odd entrants, сохранность кода и delayed judging остаются в плане. Яндекс только импорт после основной local цепочки. Цель working slice: четыре участника, полуфиналы → финал с настоящим verdict и anonymous map; он не заменяет полную приёмку кейса.

Новый ROADMAP даёт четырём агентам READY очередь, конкретные пути/выходы/проверки и fallback задачи. Контракты/fixtures позволяют разработать consumer отдельно; подключение и итоговая демонстрация имеют реальные системные зависимости. Никакое ожидание пакета или чужого PR не разрешает fake-verdict runtime.
