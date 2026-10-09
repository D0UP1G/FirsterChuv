# Аудит координатора: новая проверка PR и безопасная интеграция

- Поручение: повторно проверить новые PR и слить готовые, сохранив работу активных агентов.
- Время: 2026-10-09T23:44+03:00 — 2026-10-09T23:54:34+03:00, Europe/Moscow.
- Статус: IN_REVIEW; combined code проверен, remote CI/merge — следующий шаг.
- Ветка: feature/mvp-integration-review-3; начальная база `623a17912efa55fd00550565fdfc0ac06d41607a`.
- Последняя включённая база: `e1fb156a8d6a711967fe1284ce37b36b956763b5` (A4 #42).
- Проверенный code HEAD: `b465e1ebb6caaa56a000bebfe6b5095a92ede7a8`; последующие изменения — документация.

## Решения по исходным PR

| PR | Точный проверенный head | Scope и решение |
|---|---|---|
| #7 | `1a2b54a12d2070c39c1c47ef67d37396c345a064` | Bracket/ORM/private generate/read; draft/scheduled guard первым conditional UPDATE. B01 исправлен, объединён в feature. HTTP reset/pairings — P2-02.2. |
| #16 | `a0b1dcc682fac8f2fb1285743a62758310feeaa3` | Durable score.changed/cursor, SOLVED после OK→WA/CE. B03 исправлен, строгий private allowlist сохранён. Producer/HTTP/SSE отсутствуют. |
| #34 | `730edd827236a42d98b3efe85551f6277a1d5d97` | Pure manual/both_ready policy: membership, два distinct ready, server time, idempotency. Persistence/API отдельно. |
| #37 | `d3319275eb32c27e45c8a7316bb321cb16b83927` | Worker heartbeat/DB recovery/common adapters/result+failure outboxes. Exhausted infra не выдаёт verdict; без production factory/providers worker закрыт. |
| #38 | `92af1d666f539b5fdc9e694444e389eb373692a1` | Immutable acceptance/result identity, duplicate/conflict/out-of-order/stale run, pending-aware finalization. Pure core; DB gateway отсутствует. |
| #41 | `c8b80430707e51faa83619a0ccf41e749ac51b9e` | Intent fingerprint match/key/actor/action/reason/arguments; True отличается от 1; exact retry возвращает plan. Durable command/effects/API отдельно. |
| #21 | `1706ecfb8d16a693a462b3f3b7f379caeedc0060` | Не включён: SHA не изменился после подтверждённого SQLite CAS busy→uncaught error. Доказательство — предыдущий coordinator audit; probe здесь повторно не запускался. P3-05.1 READY владельцу. |

Все выбранные source heads имели 4 SUCCESS CI checks. CI исходных веток дополняется обязательным CI combined HEAD перед merge.

## GitFlow и сохранность

Source PR объединены merge commits: #7 `de8c225`, #16 `ea80379`, #34 `82645d2`, #38 `1acb049`, #41 `d2b5cd4`, #37 `33f76d4`; #42 включён `b465e1e`.

Конфликты кода только в AppConfig/includes: сохранены accounts/tournaments/problems/judge/submissions, добавлены competition/events. Все URL includes сохранены; event HTTP route не открывался. Конфликт карточки A2 разрешён поздним авторским snapshot; последовательные snapshots/helpers и все исходные аудиты сохранены. A3 card пришла с #37. Активные задания авторов не присваивались.

Git object check: ancestry всех 6 heads, 136 исходных аудитов byte-for-byte, 40 изменённых code paths (кроме разрешённого union registrations) совпадают с авторами. Frontend/A4 card идентичны свежему #42. Main `e9fc0ef97dcb83d2beffa41f42cb873ebcde71bc` неизменён. Чужие refs/checkout не переключались; force push и удалений branches нет.

## Выполненные проверки

| Команда/проверка | Фактический результат |
|---|---|
| DJANGO_DEBUG=true uv run --locked python manage.py test backend.apps -v 1 | PASS: 230 tests, 2 skips, 124.731 s; повтор не потребовался |
| File-backed submissions, own test_settings и отдельный /tmp SQLite path | PASS: 49/49, 31.610 s |
| scripts/check_domain_suites.py | PASS: bracket 8, clock/readiness 19, score/ledger 21, admin/commands 20 = 68 |
| Sandbox unittest | PASS: 15/15 |
| Strict schemas/common imports | PASS: 9 fixtures, private-field rejection, imports без optional apps |
| Django check/makemigrations --check --dry-run | PASS: 0 issues, no changes detected |
| npm test -- --run | PASS: 18 files / 80 tests, 11.21 s |
| npm run build | PASS: TypeScript/Vite; предупреждение о размере editor chunk |
| Production JS inspection | PASS: 5 JS artifacts без rust/offline fixtures и dev workspace transport |
| run_judge_worker --once без configured factory | Ожидаемый integration error: SUBMISSION_WORKER_FACTORY |
| git diff --check/source/audit/frontend integrity | PASS |
| Case PDF SHA-256 | Без изменений: `8d0d0a843b00ac4d35845fabf02963f793ee3115870fa5f3b108176f809bd008` |

Skips: file-backed-only probe (отдельный file-backed suite прошёл) и opt-in real Docker LocalJudge smoke. Real Docker/browser/official/full T01–21 не выполнялись. Миграции проверены на test DB; production DB не мигрировалась. Прежняя Docker проверка LocalJudge — в coordinator audit PR #32.

## Кейс, безопасность и следующая работа

Роли/CSRF/object guards сохранены; bracket read разрешает admin либо joined active participant. Event whitelist исключает source/email/CE diagnostics. Anonymous HTTP/SSE не открывался. Worker требует trusted executor и оба реальных sinks; инфраструктура не начисляет verdict, failure receipt не содержит source. ORM использует параметры; shell/SQL interpolation клиентского ввода не добавлена.

Срезы покрывают части M03–08/J04/E03/V01–02; full acceptance остаётся системной. DB recovery не доказывает container cleanup после process kill: нужен own owner/claim fencing. Version/checksum должны быть из исходного accepted run; latest catalog не подходит. Contract requests сохранены; common failure port и production A2 gateway ещё нужны.

STATE/ROADMAP уточняют следующие подпункты: A1 public access/failure typing/wiring; A2 persisted run/gateway/ledger/effects и pairing/projector reserve; A3 import/CAS fix, snapshot/executor/cleanup CONNECT; A4 реальные endpoint CONNECT. При WAITING продолжать READY своей зоны.

## Следующий шаг публикации

Integration PR → develop, CI на точном combined HEAD, fresh refs перед merge и повтор затронутых проверок при новых develop changes. Merge commit с exact-head guard; затем проверить GitHub source PR states, remote ancestry, исходные heads/main/latest frontend/A4. Отдельный STATE PR не prerequisite после MERGED.
