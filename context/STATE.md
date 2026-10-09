# Состояние интеграции

Снимок ревизии 2026-10-09, Europe/Moscow. База кода: origin/develop `146b2cb64a6273472c2de9cae04bfad21acd1782` (PR #9). Ревизионная документация подготовлена через feature/parallel-agent-roadmap; этот SHA — база изученного кода до её документационного PR. Статус её слияния проверяется отдельно в GitHub и не меняет состав приложения. Ответственный за дальнейшие снимки — координатор интеграции, агент 1 по умолчанию; ожидание STATE PR не блокирует работу после подтверждённого code merge.

## Компоненты

| Компонент | Реальное положение | Доказательство/оставшаяся работа |
|---|---|---|
| PDF/архитектура/контекст | Integrated PR #1 | SHA PDF сверён, все 8 страниц прочитаны; план обновлён отдельной ревизией |
| Backend/common/User | Integrated PR #2 | Bootstrap/SQLite/API; Compose полный runtime не готов |
| Auth/CSRF/roles/bootstrap admin | Integrated PR #5 | Account tests; full T02/T20 открыты |
| Tournament CRUD/roster/freeze | Integrated PR #8 | Nullable seed/cap/role/rollback; 37 backend tests повторены на этой базе; full T03/T05 открыты |
| Приглашения | Не integrated | P1-01; существующая ветка/checkout agent 1 может быть начата, опубликованного результата нет |
| Алгоритм сетки | Open draft PR #7, a89b8fc | ORM/run models/generate/reset/pairing service появились; 58 tests с временной app registration прошли. Clock/score/штатное подключение отсутствуют; F08 archived reset открыт |
| Sandbox harness | Open PR #3, 3a0d865 | 8 unit tests, image build успешен; исходный runner FAIL invalid PID mode. Diagnostic fix проходит 4 smoke cases, не исходный PR |
| LocalJudge/official importer/queue/drafts | Не integrated | P3-02–06, реальные verdicts/recovery ещё не доказаны |
| Frontend/public SSE/карта | Не integrated | P2-06/P4-01–06; frontend публичная ветка не обнаружена |
| CI/review gate | Не настроен | Все 9 PR без checks/reviews; main/develop protected=false; P1-02 |
| Официальный package/README | Не получены | Только P3-06/final T12/T14/T21 ждут внешние материалы, другая разработка продолжается |
| Full demo/video/release | Не готовы | T01–21 в целом NOT_RUN, main bootstrap, тегов/release нет |

## Git / PR

- main `e9fc0ef97dcb83d2beffa41f42cb873ebcde71bc`: пустой bootstrap, не релиз.
- develop `146b2cb64a6273472c2de9cae04bfad21acd1782`: PR #1/#2/#4/#5/#6/#8/#9 merged.
- Open #3 feature/sandbox-proof: `3a0d86503b22b95b5004625ef8998cd1cc4c11c3`.
- Open draft #7 feature/bracket-runtime: `a89b8fc8d5dce0657f44a559c302ae97c5b0a5b4`.
- Feature refs/история сохранены. Все опубликованные merges используют merge commits; force push ревизия не делала.

Полный список PR/замечаний/аудитов/команд — [отчёт проверки](../docs/reviews/2026-10-09-repository-audit.md). Снимок требует fetch/GitHub проверки перед новым merge, не заменяет актуальные refs.

## Следующая работа одновременно

1. A1: P1-01 invites; во время review — CI/proxy/access/Compose.
2. A2: P2-01 штатное подключение PR #7 (минимальная передача общих файлов), P2-02 F08/HTTP pairing/reset; затем clock/scoring/events. Canonical rank и package import уже реализованы. Не ждать A1-03.
3. A3: P3-01 исправить Docker argv и протокольную границу, real tests; параллельная очередь storage/queue/drafts без ожидания A1/A2 или package.
4. A4: P4-01 React + real auth/roster, остальные экраны по v1 dev fixtures; CONNECT по одному готовому endpoint.

[ROADMAP v2](../ROADMAP.md) и [контракт v1](../docs/architecture/parallel-contracts.md) задают конкретные выходы. Полная системная интеграция нужна для финальной приёмки, отдельный mocked consumer её не закрывает. Runtime без реального provider/access port отказывает, не подделывает данные.
