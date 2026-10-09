# Состояние интеграции

Снимок ревизии 2026-10-09, Europe/Moscow. Текущая база кода: `origin/develop=cad34ea4ddf1171779dc22139f2e1533160b5015`, merge commit PR #12. Ответственный за дальнейшие снимки — координатор интеграции, агент 1 по умолчанию; новый отдельный STATE PR не блокирует работу после подтверждённого code merge.

Документационная ревизия [PR #10](https://github.com/D0UP1G/FirsterChuv/pull/10) и invite backend P1-01 [PR #12](https://github.com/D0UP1G/FirsterChuv/pull/12) merged. PR #12 интегрирован `2026-10-09T14:15:55Z`, merge SHA `cad34ea4ddf1171779dc22139f2e1533160b5015`. Перед каждым следующим срезом проверять свежие refs; исторические аудиты сохраняют свой исходный SHA.

## Компоненты

| Компонент | Реальное положение | Доказательство/оставшаяся работа |
|---|---|---|
| PDF/архитектура/контекст | Integrated PR #1 | SHA PDF сверён, все 8 страниц прочитаны; план обновлён отдельной ревизией |
| Backend/common/User | Integrated PR #2 | Bootstrap/SQLite/API; Compose полный runtime не готов |
| Auth/CSRF/roles/bootstrap admin | Integrated PR #5 | Account tests; full T02/T20 открыты |
| Tournament CRUD/roster/freeze | Integrated PR #8 | Nullable seed/cap/role/rollback; 37 backend tests повторены на этой базе; full T03/T05 открыты |
| Приглашения | Integrated PR #12 | Invite/accept API, hashed token, pagination/revoke, use/cap/freeze/idempotency; 47 backend tests прошли на PR code head. Полный T04 ждёт browser flow P4-02 |
| Competition core | Open PR #7 (`1952244`), #11 (`28d6cda`) и #13 (`19bbf88`) | Bracket, clock/start и deterministic scoring остаются в отдельных owner branches; в develop ещё не integrated |
| Problem catalog | Open PR #14 (`9234951`) | Normalized catalog/storage; P1-02 сверил public/private DTO структурно, app ещё не в develop |
| Submission queue | Open PR #15 (`7d76d0b`) | Durable queue/outbox остаются отдельной feature; local receipts добавляют `match_id`, а узкий ResultSink возвращает bool — при CONNECT нужен adapter к неизменённому v1. `LanguageRegistry.is_supported` совпадает с общим additive port; production adapters ещё отсутствуют |
| Public event store | Open PR #16 (`8340014`) | Durable `score.changed` store без public HTTP/SSE и без production EventWriter adapter; не входит в develop |
| Sandbox harness | Open PR #3 (`6950f10`) | Автор обновил branch; свежий PR HEAD проверен, исходный audit выявлял invalid PID mode/F01 и протокольную границу/F07. Unit CI и real Docker security gate остаются разными проверками |
| LocalJudge/official importer/queue/drafts | Не integrated | P3-02–06, реальные verdicts/recovery ещё не доказаны |
| Frontend/public SSE/карта | Не integrated | P2-06/P4-01–06; frontend публичная ветка не обнаружена |
| CI/review gate | Не настроен | PR #12 не получил status checks; branch protection отключён в предыдущей проверке; P1-02 добавляет workflow и рекомендации, но не включает GitHub policy |
| Официальный package/README | Не получены | Только P3-06/final T12/T14/T21 ждут внешние материалы, другая разработка продолжается |
| Full demo/video/release | Не готовы | T01–21 в целом NOT_RUN, main bootstrap, тегов/release нет |

## Git / PR

- main `e9fc0ef97dcb83d2beffa41f42cb873ebcde71bc`: пустой bootstrap, не релиз.
- develop `cad34ea4ddf1171779dc22139f2e1533160b5015`: PR #1/#2/#4/#5/#6/#8/#9/#10/#12 merged.
- Open #3 `feature/sandbox-proof`: `6950f10464ad6a0849accea12ed959a6c2d1ee60`.
- Open #7 `feature/bracket-runtime`: `1952244df7c60fecabaea7f3829054017a0efb19`.
- Open #11 `feature/match-clock-start`: live PR; consumers/tests остаются в owner branch до merge.
- Open #13 `feature/match-scoring-results`: `19bbf88bcecf2153ca60128946d0abc21052d271`.
- Open #14 `feature/problem-storage-import-core`: `9234951b4fd67bdb231149c24d4d276bbe48964e`.
- Open #15 `feature/submission-queue-core`: `7d76d0b1bf85c7a707de72ebaa1cb8364b4c9207`.
- Open #16 `feature/public-events-sse`: `83400143324db7bc6b6de5255076487b0cbe8eb0`.
- Feature refs/история сохранены. Все опубликованные merges используют merge commits; force push ревизия не делала.

Полный список PR/замечаний/аудитов/команд — [отчёт проверки](../docs/reviews/2026-10-09-repository-audit.md). Снимок требует fetch/GitHub проверки перед новым merge, не заменяет актуальные refs.

## Следующая работа одновременно

1. A1: P1-02 CI/contracts; затем P1-03 proxy/share access, P1-04 Compose, P1-05 release gate. P1-01 backend merged; P4-02 ещё подключит браузерный invite flow.
2. A2: P2-01 штатное подключение PR #7 и текущего clock/start PR #11 (минимальная передача общих файлов), P2-02 F08/HTTP pairing/reset; затем scoring/events. Не менять чужие ветки и не ждать A1-03.
3. A3: P3-01 исправить Docker argv и протокольную границу, real tests; параллельная очередь storage/queue/drafts без ожидания A1/A2 или package.
4. A4: P4-01 React + real auth/roster, остальные экраны по v1 dev fixtures; CONNECT по одному готовому endpoint.

[ROADMAP v2](../ROADMAP.md) и [контракт v1](../docs/architecture/parallel-contracts.md) задают конкретные выходы. Полная системная интеграция нужна для финальной приёмки, отдельный mocked consumer её не закрывает. Runtime без реального provider/access port отказывает, не подделывает данные.
