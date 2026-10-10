# Agent 4 · P1-01.1 · invite acceptance concurrency

- Время: 2026-10-10, Europe/Moscow.
- Ветка: `feature/a4-p1-01-1-invite-concurrency`.
- База: `origin/develop` `ee755af6ed93e7c3996cb5e70edd8d21e527c56a`.
- Требования: M02; backend checks T04; invite participant/auth gate S02.
- Статус: реализация проверена; публикация PR ожидает commit/push.

## Цель и сверка

P1-01.1 устраняет временный `database_busy` при конкурентном принятии приглашений в SQLite, не ослабляя лимит активаций, вместимость состава или идемпотентность участника. Кейс на стр. 5, блок 1 требует ссылку-приглашение со сроком либо лимитом активаций, отзыв и попадание участника в список соревнования. Матрица требований связывает это с M02/T04. Основные invite API и ledger уже интегрированы PR #12; полный browser T04/S02/T20 остаётся вне этого среза.

Начальный regression воспроизвёл ошибку: при лимите состава 2 из 3 параллельных участников принялся только один, остальные получили `database_busy`. Старый capacity test проверял только верхний предел использования и разрешал временную lock error; это не подтверждало доступность двух свободных мест.

## Изменения

- `backend/apps/tournaments/services.py`: acceptance берёт write reservation до чтения invite/acceptance state в SQLite, предотвращая deferred read→write upgrade race. Для БД с `select_for_update` блокируется invite row. Транзакционные ошибки `locked` повторяются с ограниченным exponential backoff (до 8 попыток); другие `OperationalError` не маскируются.
- `backend/apps/tournaments/tests.py`: file-backed `TransactionTestCase` больше не считает `database_busy` допустимым исходом. Для трёх конкурентных участников с лимитом состава 2 проверяются ровно два accept и один `capacity_reached`; добавлен одновременный retry тем же пользователем, который должен создать один acceptance и списать один use.
- Документация синхронизирована с PR #84 и описывает границы invite concurrency evidence. Чужие A3/A5 paths не менялись.

Лимиты и assertions не ослаблялись. `used_count` увеличивается только в исходной conditional update после idempotency/use checks; rollback состава сохраняет прежнее поведение.

## Проверки

| Проверка | Результат |
|---|---|
| До фикса: `InviteAcceptanceConcurrencyTests` | FAIL воспроизведён: один accept и два `database_busy` на capacity race |
| `InviteAcceptanceConcurrencyTests`, 10 последовательных запусков после фикса | PASS 10/10, всего 30 сценариев; use limit, roster cap, same-participant retry |
| `DJANGO_DEBUG=true uv run --locked --env-file .env.example python manage.py test backend.apps.tournaments.tests --noinput --verbosity 1` | PASS: 34 tests, без skips |
| `DJANGO_DEBUG=true uv run --locked --env-file .env.example python manage.py check` | PASS, 0 issues |
| `DJANGO_DEBUG=true uv run --locked --env-file .env.example python manage.py makemigrations --check --dry-run` | PASS, no changes detected |
| `uv run --locked --env-file .env.example python -m compileall -q backend` | PASS |
| `git diff --check` | PASS |

## Границы и следующий шаг

Этот срез устраняет и покрывает SQLite invite acceptance race; он не меняет schema/API contract и не доказывает browser registration/join, proxy logging или полное T04/T20. Следующий GitFlow шаг — feature commit/push, PR в `develop` с exact-head CI и карточкой A4 в `IN_REVIEW`. После публикации остановиться: это последняя задача A4 в Wave 1; Wave 2 не начинать.
