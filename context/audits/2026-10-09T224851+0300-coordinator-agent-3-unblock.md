# Аудит координатора: разблокирование агента 3

- Автор: координатор; дата 2026-10-09, Europe/Moscow (UTC+03:00).
- Первое точное время проверки: 2026-10-09T22:41:16+03:00; checkpoint результатов 22:48:51; запись дополняется фактическими проверками перед публикацией.
- Поручение команды: агент 4 работает, агент 3 ждёт слияния; выяснить нужные ветки и слить безопасные, сохранив активную работу.
- Задачи: P3-02.3, admin sub-slice P3-02.2, P3-04.1, implementation P3-03; найден новый P3-05.1.
- Ветка: `feature/agent-3-merge-unblock`, база `origin/develop` `13cd2d4` (#29).
- Статус этой записи: проверка интеграционной feature до публикации/merge. Результат внешнего слияния определяется GitHub и remote refs.

## Что фактически ждёт агент 3

Последний опубликованный audit A3 P3-02.2 и карточка `feature/problem-catalog-management` прямо называют parser fix PR #25 prerequisite для normalized import management. Фикс действительно отсутствовал в develop. Слияние #25 снимает этот конкретный блокер; весь A3 не обязан ждать остальных providers.

Другие зависимости — production A2 gateway/ledger/result/failure adapters, run-pinned version/checksum в workspace и официальный package README. Merge существующих queue/catalog/provider cores не создаёт эти adapters. READY задачи остаются normalized import/status API, actual worker с DI/lease/recovery/outbox и исправление собственного CAS race #21. При WAITING одного CONNECT продолжать следующую READY задачу в этой же сессии.

Проверены AGENTS/PROJECT/STATE/ROADMAP, карточки A3/A4, аудиты и фактические refs/PR. Новый frontend уже опубликован: #22/#24/#27/#28/#29 MERGED. Во время ревизии A4 также слил #30 `dab4c80` с двумя regression tests; свежий develop `8c6836bed706a166ab3303e07441f51975e67add` включён обычным merge перед публикацией. Его карточка, оба теста и три новых аудита сохранены. Старые STATE/ROADMAP ошибочно продолжали говорить, что frontend нет; текущая запись и обновлённые документы исправляют этот датированный снимок. Продуктовые решения и требования кейса не менялись: DRF/React/SQLite, global participant/admin, anonymous spectators, own sandbox и private source/tests/checkers.

## Решения по веткам

| PR / точный HEAD | Решение | Основание |
|---|---|---|
| #25 `8388117507bbe6140d5180340f9c64082d3d2807` | MERGED отдельно | Узкий typed parser fix; code review, 22 problems tests и зелёные исходные CI |
| #26 `435cef789d7e1f2d69eed4f762dae34bcf506cb0` | Включён в текущую integration feature | Admin-only bounded paginated catalog; DTO совместим с frontend `Page<ProblemCatalogEntry>` |
| #15 `555ca0ee692fdc4472857e3f2350c01819224f1e` | Включён в текущую integration feature | Whole-transaction BUSY/LOCKED retry/503; 29/29 file-backed tests, исходный received_at |
| #23 `942b4f579e69a1d7818a100e0e9661ecf1fe0cbe` | Включён в текущую integration feature | Pinned bundle identity, bounded Docker runner/task policy, actual smoke evidence ниже |
| #21 `1706ecfb8d16a693a462b3f3b7f379caeedc0060` | Не включён: нужен P3-05.1 | Два одновременных первых save дают uncaught SQLite lock → HTTP 500 |
| #7 `1a2b54a12d2070c39c1c47ef67d37396c345a064` | Новый опубликованный fix, вне этого A3 merge | Не подменять ревизию актуального A2 PR старым verdict; его producer/runtime ещё не создаётся этим срезом |
| #16 `83400143324db7bc6b6de5255076487b0cbe8eb0` | Вне этого merge; прежний B03 остаётся | SOLVED + последний WA после OK должен быть допустим в public event |

PR #25 слит обычным GitHub merge commit `ed14416fee0d1cccbd0b9a202e563d49f062572a` в 2026-10-09T19:43:34Z. Проверены `MERGED`, exact source HEAD и remote develop. Он интегрирован отдельно до #26, как предусматривала карточка A3. В новой feature #25 не является новой несмерженной частью общего diff.

Остальные три проверенных HEAD объединены через `git merge --no-ff`, source refs автора не изменялись. Конфликты: карточка A3 (сохранены исторические publication checkpoints с новым актуальным разделом) и `common/api_urls.py` (сохранены оба include problems/submissions). Остальной reviewed code взят из source heads. Common v1 ports/schemas, авторская конфигурация registry и CI workflow не менялись.

## Проверки и пределы доказательств

| Проверка | Фактический результат |
|---|---|
| Parser fix на текущем develop: `manage.py test backend.apps.problems` | PASS, 22 tests |
| File-backed submissions: `SQLITE_TEST_PATH=... manage.py test backend.apps.submissions.tests --settings=backend.apps.submissions.test_settings --noinput` | PASS, 29 tests, 34.311 s |
| Full combined `manage.py test --noinput` первый запуск | FAIL: из 150 tests один существующий P1 invite-concurrency test ожидал 2 accepted, получил 1 accepted и 2 database_busy; 2 ожидаемых skips |
| Повтор full combined suite без изменения code | PASS: 150 tests, 63.179 s, 2 ожидаемых skips (file-backed-only settings check и opt-in real Docker test); actual проверки обоих выполнены отдельно |
| `manage.py check`; `makemigrations --check --dry-run` | PASS; migration drift отсутствует |
| `scripts/check_contracts.py`; `check_contract_imports.py` | PASS, 9 strict fixtures и common import isolation |
| `scripts/check_domain_suites.py` | PASS, 36 clock/score/admin tests (пересекаются с Django, не складывать counts) |
| `unittest discover -s sandbox/tests` | PASS, 15 tests |
| Frontend `npm ci --ignore-scripts`; `npm test` | PASS, 15 files / 61 tests |
| Frontend после включения свежего #30, последовательные `npm test` и `npm run build` | PASS, 16 files / 63 tests, TypeScript/Vite build |
| Frontend `npm run build` | PASS, TypeScript и Vite; предупреждение о размере editor chunk не блокирует build |
| Fresh Docker build exact #23 sandbox | PASS, Engine 29.8.2, отдельный image `firsterchuv/review-local-judge:942b4f5` |
| Actual Docker sandbox fixtures | PASS: OK, WA, TIME_LIMIT, OUTPUT_LIMIT, protocol-write BLOCKED |
| Actual task-specific limit | PASS: sleep 500 ms при time limit 100 ms и memory 64 MiB → TIME_LIMIT |
| Actual LocalJudge smoke | PASS, 1 opt-in Django test: stored immutable synthetic normalized bundle → compiled real solution → OK |
| Runner containers после проверки | Пустой список собственных `firsterchuv-a3-01-*` |
| Source history/audits | 4 accepted source heads — ancestors; после sync #30 повторно проверены все 70 source audit files byte-for-byte |
| Работа A4/P1 | `frontend`, `context/agents/agent-4.md`, accounts/tournaments и CI workflow byte-identical текущему develop; чужие checkout не менялись |
| Whitespace | `git diff --check` PASS |

Существующий P1 concurrency test уже упоминался в исходном #23 как flaky с `database_busy`. Первый локальный FAIL записан, не замаскирован. Код и тест приглашений идентичны develop; frontend install/test/build параллельно с первым backend suite давали дополнительную CPU нагрузку. Это объяснение вероятного влияния нагрузки, не доказательство полного исправления P1. Его стабильность остаётся отдельной задачей владельца P1; запрещено ослаблять тест или выдавать capacity/no-500 acceptance за закрытый.

Дополнительный контроль: тот же одиночный invite-concurrency test на изолированной копии исходного develop `ed14416` прошёл 1/1 за 1.356 s. Полный повтор combined backend прошёл 150 tests без изменения code. Regression/tests исходных accounts/tournaments не модифицировались. Финальный frontend suite после sync #30 выполнен отдельно без одновременного build: 16 files / 63 tests PASS за 11.82 s, затем отдельный build PASS. Sync #30 изменил только frontend tests/card/audits, backend code идентичен проверенному полному повтору.

Fresh image SHA256: `c286514db6256e1e01f262c1a9d01d8851e58f54549f1729408d4567862aaf0a`. Для actual smoke только в отдельном проверочном Python-процессе выбран этот image и test registry с `verified=True` для этого image; исполнялся настоящий C++ только в Docker. Source code PR, production tag `firsterchuv/sandbox-cpp:0.1.0` и `COMPILERS` не изменялись. Это реальный execution evidence synthetic bundle; не production compiler readiness, не официальный checker и не полный hostile T18/T20/T21.

Новый container runner принимает `run <time_limit_ms>`. Worker/deployment должен собрать актуальный image перед CONNECT; старый image с прежним argv несовместим. Registry остаётся `verified=False` до проверки именно deployment worker. При отсутствии real ports HTTP admission закрыт с 503; публичные DTO не получают source/CE/private artifacts.

## Воспроизведение blocker #21 и следующий READY шаг

Изолированная копия exact #21, отдельная file-backed SQLite, два worker threads одного author/run/problem/language. Probe синхронизировал обычные первые `Draft.objects...first()` перед записью, без модификации production исходников. Результат: один `SAVED revision=1`, один `OperationalError: database is locked`, DB содержит ровно 1 Draft и 1 DraftRevision. Данные победителя целы, но exception не перехватывается view и превращается в 500.

P3-05.1: bounded retry всей CAS transaction только SQLite BUSY/LOCKED; после retry повторно читать revision, чужой победивший source → 409/current draft; исчерпание → понятный retryable 503. Проверить concurrent creation и update на файловой DB, ревизии/history/rollback/приватность и сохранность локального конфликтующего текста в UI. Это работа A3 без dependency на A2/A4; PR #21 остаётся открытым на исходной ветке.

## Публикация и передача

Готовится отдельный coordinator integration PR → develop. Перед merge требуются зелёные CI на реально собранном head, свежий develop и проверка сохранности frontend/A4 refs. После подтверждённого merge A3 обновляет свою ветку обычным merge `origin/develop` и начинает normalized import/status API либо actual worker; если production adapter ещё отсутствует, берёт P3-05.1. Активный A4 продолжает свою ветку и подключает catalog по одному endpoint; coordinator не пересоздаёт его UI и не меняет его checkout.

Полный работающий MVP ещё требует persisted match runtime/ledger, worker wiring, реальных API/UI/SSE connections и финальной проверки по кейсу. Полные T01–21 не объявляются завершёнными.
