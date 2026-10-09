# Повторная ревизия проекта и интеграция MVP

Дата: 2026-10-09, Europe/Moscow. Начальная проверенная база develop `dd80c933083eea8ac234a17593a6a54a09ded53d` (PR #19), main `e9fc0ef` bootstrap. Репозиторий [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv). Это датированный отчёт, не live PR dashboard.

## Объём и итог

Повторно получены все 19 PR (files/commits/body/comments/reviews/checks/base/head/merge status), опубликованные refs, CI и 53 уникальных исторических аудита из develop и восьми рабочих веток. Одинаковых audit filenames с разным содержимым не найдено. Старые аудиты не переписываются. Кейс сверён по всем 8 страницам и checksum `8d0d0a843b00ac4d35845fabf02963f793ee3115870fa5f3b108176f809bd008`; копия в репозитории совпадает с исходной Downloads.

Обновлены независимые review auth/invites/common CI, bracket/clock/scoring/events, catalog/queue и весь sandbox. Использованы три read-only reviewers, изолированные copies и временные SQLite; исходные feature refs и чужие незакоммиченные checkout не изменялись. Неопубликованная работа/фактический будущий demo-host этим не подтверждаются.

На исходном снимке 12 PR merged и 7 open. Четыре среза прошли review: #3 harness, #11 pure clock, #13 pure scoring, #14 normalized catalog. Они объединены merge commits в coordinator-owned feature/mvp-integration-review-2; общий PR в develop проходит CI на совместном коде. Их исходные commits сохранены в ancestry. #7/#15/#16 не включены из-за воспроизведённых дефектов ниже. Полный MVP ещё не работает: нет frontend, persisted match runtime/gateway, LocalJudge/worker/drafts/production SSE.

## Все PR на исходном снимке

| PR | HEAD / состояние | Сверка и решение |
|---|---|---|
| [#1](https://github.com/D0UP1G/FirsterChuv/pull/1) | edd10ea, MERGED | Кейс/context/architecture, PDF сохранён; не новый runtime |
| [#2](https://github.com/D0UP1G/FirsterChuv/pull/2) | ccf8eea, MERGED | Bootstrap/API/SQLite, полный Compose остаётся target |
| [#3](https://github.com/D0UP1G/FirsterChuv/pull/3) | 6950f10, OPEN | F01/F07 исправлены, actual image/smoke/isolation/cleanup/recovery пройдены; включён как harness slice |
| [#4](https://github.com/D0UP1G/FirsterChuv/pull/4) | 7e10d0d, MERGED | Исторический A1 STATE sync |
| [#5](https://github.com/D0UP1G/FirsterChuv/pull/5) | 3b1be0c, MERGED | Auth/roles/CSRF, register participant; full security/browser acceptance открыт |
| [#6](https://github.com/D0UP1G/FirsterChuv/pull/6) | 5885984, MERGED | Исторический auth STATE sync |
| [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) | 1952244, OPEN non-draft | Ordinary registration есть, F08 lifecycle остаётся. Не включать до P2-02.1 |
| [#8](https://github.com/D0UP1G/FirsterChuv/pull/8) | 5163f6c, MERGED | CRUD/roster/freeze/canonical rank input; full history/browser ещё нет |
| [#9](https://github.com/D0UP1G/FirsterChuv/pull/9) | e9ad812, MERGED | Исторический roster STATE sync |
| [#10](https://github.com/D0UP1G/FirsterChuv/pull/10) | 192a625, MERGED | ROADMAP v2 снял старые ожидания, v3 продолжает его P-ID |
| [#11](https://github.com/D0UP1G/FirsterChuv/pull/11) | 28d6cda, OPEN | 12 pure clock tests, strict deadline/pause; включён как core, не persisted clock/API |
| [#12](https://github.com/D0UP1G/FirsterChuv/pull/12) | a0b3252, MERGED | Invite backend/hash/cap/expiry/revoke/atomic join; browser T04 остаётся |
| [#13](https://github.com/D0UP1G/FirsterChuv/pull/13) | 19bbf88, OPEN | 12 deterministic scoring tests; включён как core, не ledger/finalization/downstream |
| [#14](https://github.com/D0UP1G/FirsterChuv/pull/14) | 9234951, OPEN | Normalized immutable catalog/archive safety/private split; включён, compiler verified=false/full importer/HTTP ещё нет |
| [#15](https://github.com/D0UP1G/FirsterChuv/pull/15) | 7d76d0b, OPEN | Queue/lease/outbox, runtime 503 без adapters; SQLite admission race → 500. Не включать до P3-04.1 |
| [#16](https://github.com/D0UP1G/FirsterChuv/pull/16) | 8340014, OPEN | Durable store, но SOLVED/lastVerdict WA отвергается вопреки score/v1. Не включать до P2-06.1 |
| [#17](https://github.com/D0UP1G/FirsterChuv/pull/17) | 1925329, MERGED | 4 CI jobs pass, common ports/schemas/import isolation; checks не заменяют real Docker/E2E |
| [#18](https://github.com/D0UP1G/FirsterChuv/pull/18) | e4969a1, MERGED | Docs STATE sync, 4 CI jobs pass; application code не меняет |
| [#19](https://github.com/D0UP1G/FirsterChuv/pull/19) | b1a5aa9, MERGED | Docs completion, 4 CI jobs pass; агенту 1 был дан отдельный стоп после P1-02 |

У исходных PR formal reviews отсутствуют. #17/#18/#19 имеют четыре SUCCESS jobs, старые открытые heads без checks. Проверено API: develop protected=false, rulesets=[]; не заявлять обязательный gate включённым. Manual real-smoke workflow находится в develop, default main не содержит его; в этой ревизии выполнен локальный real build/smoke. Обходить GitFlow ради workflow_dispatch не нужно.

Дополнительная опубликованная feature/match-admin-actions 8f5b762 имеет pure guards и 12 passed tests, но PR нет; напрямую не слита. Не приписывать ей HTTP/ORM/idempotency/effects. Веток/PR с frontend не обнаружено.

## Блокирующие замечания

### B01 / прежний F08 / P2 — lifecycle сетки, #7

services.py generate 125–137 возвращает existing bracket до status guard; reset 186–197 и full pairing 213–226 не проверяют draft/scheduled. На временной DB generate → archive/running/completed → reset/pairing заменяет Match UUIDs, HTTP generate возвращает 200. Первый start отсутствует, поэтому существующий started guard не помогает.

P2-02.1: общий editable guard внутри transaction до reads/existing-return/freeze; SQLite conditional write сериализует archive/start. Closed lifecycle → 409 без изменения matches/roster/freeze. Regression всех services и HTTP generate. Ordinary registration/import/rank прежних замечаний уже исправлены, их не выполнять заново.

### B02 / P2 — SQLite concurrent admission, #15

services.py:273 SELECT existing внутри DEFERRED transaction, затем :279/_reserve_capacity:164–166 read→write. Два обычных concurrent keys: один QUEUED, второй OperationalError database locked. views.py:95–102 не ловит эту ошибку → HTTP 500. Source/counter rollback сохранён, но доступность queue нарушена. Existing 66 tests проходят и race не покрывают.

P3-04.1: bounded retry whole transaction только busy/locked с неизменным original received_at, либо согласованный write-first подход; exhausted contention → понятный retryable 503. File-backed TransactionTestCase разных/одинаковых keys, no 500, counters/ledger/event rollback. Сервисные callbacks только в общей transaction. Не маскировать arbitrary DB defect QueueFull.

### B03 / P2 — событие отвергает законный score, #16

public_payloads.py:136–138 требует SOLVED.lastVerdict==OK. Pure score #13 после OK→WA выдаёт SOLVED/attempts2/lastVerdict WA; v1 schema принимает, event store выбрасывает PublicEventInputError. В общей transaction ошибка может откатить legitimate score/event update.

P2-06.1: SOLVED требует attempts>0/non-null normalized verdict, не обязательный последний OK. First-OK факт сохраняет ledger/projector. Roundtrip score→event OK→WA/CE; whitelist/private rejection не ослаблять. Не переписывать lastVerdict в OK.

## Остаток и неблокирующие замечания

- B04: #14 bundle.py:334 artifact language ID list/dict → TypeError вместо ProblemBundleError. HTTP import отсутствует, нет execution/path bypass; P3-02.3 strict type validation перед external import.
- B05: queue exhausted infra retries не имеют contestant ResultReceipt/outbox; полный CONNECT требует additive failure sink/ledger policy, иначе FINALIZING ждёт отсутствующий результат. [Runtime handoffs](../architecture/runtime-handoffs.md) задаёт отдельный порт, v1 verdict/result не подменяется.
- B06: README/card A2/A3/requirements ещё содержали старые 146b2cb/a89b8fc/3a0d865 и no-CI/no-invites. В этой ревизии обновлены как current snapshot, исторический отчёт/аудиты сохранены. Три docs closeout PR не являются prerequisite другой дорожки.
- Proxy X-Forwarded-For topology/unlisted access/log token redaction пока не проверены как полный deployed path; P1-03 остаётся READY. Это не воспроизведённая утечка.

## Фактические проверки

| База / проверка | Результат | Ограничение |
|---|---|---|
| develop dd80c93, locked dev sync, manage.py test | 48 passed / 46.127s | API/backend, не browser/demo |
| develop contracts/common imports/migration drift | 9 fixtures pass/import pass/no changes | Не production providers |
| #7 1952244 suite | 58 passed | B01 дополнительно воспроизведён |
| #11/#13 pure suites | 12 + 12 passed | Не run/ledger persistence |
| #16 8340014 suite | 57 passed | B03 отдельно воспроизведён |
| Temporary dd80c93+#7/#11/#13/#16 | 103 passed, migration/import/schema clean | B01/B03 всё ещё есть, не слит в develop |
| #14 9234951 suite | 68 passed, check/drift clean | В его старой базе; current joint suite ниже |
| #15 7d76d0b suite | 66 passed, check/drift clean | B02 отдельный bounded two-thread probe, code source не исполнялся |
| Собранный integration feature #3/#11/#13/#14 | 93 Django tests passed / 32.121s; check чист, no migration drift | Actual совместный код, core scope |
| Integration standalone clock/score + sandbox units | 24 + 12 passed | Не суммировать как уникальное покрытие Django suite |
| Rebuilt sandbox image на #3 | 01612130490586197d5f03f834dd590042d6ac6f17eababbea11f4053dfd5fbc | Старый образ 994c240 не использован для proof |
| Exact #3 real smoke/isolation/recovery | 5 smoke pass, UID65534/NNP1/seccomp2/caps0, no host/env/socket, fd0/1/2 EACCES, net ENETUNREACH, bounded PID/memory/compile/output/watchdog cleanup + next OK | Full official hostile/expert acceptance не выполнена; ML без OOM не заявлена |

Root дополнительно собрал стандартный image tag из объединённого checkout и выполнил existing real smoke; результат/CI итогового PR фиксируются в coordinator audit при публикации. Solution code никогда не исполнялся на host; bounded probes не являлись бесконечным flood, real secrets не использовались. Новые production tests не добавлялись к четырём принятным branches, выполнены существующие suites и временные reproductions.

## GitFlow и передача

Интеграционный feature основан на актуальном develop dd80c93. Четыре source heads объединены обычными --no-ff merge commits; только conflicts карточек A2/A3 разрешены consolidated status. CI/common ports/dev lock/P1 audits сохранены; application code принят без изменения алгоритмов. После MERGED общего PR проверить develop remote/ancestry и state исходных PR; только тогда эти cores считаются integrated. Source refs не переписываются, force push не используется.

[ROADMAP v3](../../ROADMAP.md) сохраняет 24 P-ID и вводит конкретные runtime subtasks/резервные очереди: A1 access/proxy/Compose/additive common, A2 lifecycle fixes/persisted gateway/ledger/actions/SSE, A3 queue fix/LocalJudge/worker/drafts/import, A4 реальный React/auth/invites/editor/map. На зависимости роль не заканчивает сессию, продолжает другой доступный подпункт; явный user stop имеет приоритет.

R1 — working pipeline на programmatically imported smoke bundle с настоящими verdicts. R2 — обязательные функции/сохранность/сбои/public visual. R3 — официальный пакет, полные T01–21, hostile checks, одна команда/demo/video/release. R1 не является полной сдачей кейса. Старый [первый отчёт](2026-10-09-repository-audit.md) остаётся evidence прежних SHA, не current status.
