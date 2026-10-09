# Аудит: Agent 1 / A1-03.3 / roster freeze и concurrency

- Автор/роль агента: Codex, agent 1.
- Начало и окончание: первый рабочий checkpoint после A1-03.2 `2026-10-09T15:36:01+03:00` — `2026-10-09T15:42:43+03:00`.
- ID задач: `A1-03.3`, частичная evidence для `T05`.
- Ветка: `feature/tournament-roster`.
- Базовый SHA: `8b3e5cb` (A1-03.2 в feature; upstream `develop` остаётся `3b2b0ad`).
- Статус: `DONE` для A1-03.3; feature-only, не интегрировано. A1-03.4 cross-case review ещё впереди.
- PR / последующие коммиты: PR ещё не создан; текущий feature продолжает A1-03.

## Цель и исходное состояние

Проверены `AGENTS.md`, карточка Agent 1, A1-03 и A2-01 в `ROADMAP.md`, API/data-model/system/match-engine/security contracts, требования M03/T05 и PDF кейса. Пользователь явно подтвердил следовать уже записанному docs contract: roster freeze выполняется при создании сетки и входит в ту же внешнюю atomic transaction. A2 card не назначала исполнителя; чужие пути/ветки не тронуты. PDF checksum совпадает с сохранённым значением. База feature среза — `8b3e5cb`; интегрированный `develop` — `3b2b0ad`.

## Выполненные изменения

- Добавлен `backend.apps.tournaments.services.freeze_roster(tournament_id)`: active count и DB rows сверяются, требуется минимум два активных участника, турнир должен быть draft/scheduled; повторный freeze возвращает тот же roster.
- Freeze возвращает canonical order: заданный seed по возрастанию, участники без seed в конце, затем UUID пользователя по возрастанию. Freeze не назначает/не переписывает seed.
- Заморозка начинается условным SQL UPDATE, защищённым status и `roster_frozen_at IS NULL`. Это сериализует переход с conditional add/remove в SQLite. При inconsistent active count/row count сервис отклоняет построение и транзакция откатывается.
- Сервис предназначен для вызова из внешнего `transaction.atomic()` bracket generator агента 2. Его собственный atomic block становится savepoint; тест доказал, что последующая ошибка внешней bracket generation откатывает `roster_frozen_at`.
- Добавлены bounded retry (до трёх попыток) для transient SQLite locked errors на add/remove/seed/freeze; исчерпание возвращает 503 и не маскирует другие DB errors.
- Укреплены гонки: active seed update и tournament PATCH используют условные status/freeze/version filters; DELETE draft сначала условно переводит запись в archive как write guard, затем hard-deletes только внутри той же транзакции.
- В `TransactionTestCase` проверены параллельное добавление трёх пользователей при cap=2 и гонка третьего assignment с freeze: результат либо вошёл в неизменяемый roster, либо получил отказ.
- Обновлены API/data-model/system/match-engine/security/acceptance и README contracts. `context/STATE.md` не изменён, так как feature не в `develop`.

## Сверка с кейсом

Кейс стр. 5, блок управления соревнованием, требует состав игроков и олимпийскую систему с обработкой неполного состава. `M03`/`T05` требуют cap, уникальность seed и сохранение истории уже игравшего игрока. Freeze закрывает изменения roster до начала bracket generation и входит с сеткой в единый commit boundary; удаление строки участника никогда не используется для roster removal, применяется `REMOVED`. Post-freeze replacement оставлен отдельным match action агента 2.

Полный `T05` всё ещё `NOT_RUN`: нет интегрированного bracket runtime, реального played Match reference, UI/browser сценария и consumer от A2. Concurrency tests подтверждают поведение Django services в SQLite test database, но не заменяют end-to-end run с A2.

## Проверки

| Команда или сценарий | Результат | Ограничения |
|---|---|---|
| `uv run --env-file .env.example python manage.py test backend.apps.tournaments.tests.RosterFreezeTests backend.apps.tournaments.tests.RosterCapacityConcurrencyTests backend.apps.tournaments.tests.TournamentAPITests.test_admin_can_create_list_read_and_patch_a_tournament backend.apps.tournaments.tests.TournamentAPITests.test_delete_draft_removes_it_but_delete_after_freeze_archives` | Exit 0; 8 targeted freeze/concurrency/CRUD cases passed | Не запускается настоящий A2 bracket consumer |
| `RosterCapacityConcurrencyTests.test_simultaneous_assignments_never_exceed_capacity` | Exit 0; 3 concurrent assignments при cap 2 дали ровно 2 активных записи, count совпал | In-memory SQLite shared test DB; actual production WAL/process topology не проверена |
| `RosterCapacityConcurrencyTests.test_assignment_racing_freeze_is_either_in_roster_or_rejected` | Exit 0; frozen roster совпал с active database rows/count | Конкурентный тестовый harness, не API/browser |
| `RosterFreezeTests.test_outer_bracket_transaction_rollback_also_rolls_back_freeze` | Exit 0; simulated exception сняла freeze после outer transaction rollback | Тестовая имитация границы, не реальная bracket generation |
| `uv run --env-file .env.example python manage.py test` | Exit 0; 35 tests passed | Feature suite; не полный T05/T20 |
| `uv run --env-file .env.example python manage.py check` | Exit 0; no issues | Static Django check |
| `uv run --env-file .env.example python manage.py makemigrations --check --dry-run` | Exit 0; no changes detected | Схема согласована с migrations 0001/0002 |
| `./scripts/manage.sh check` | Exit 0; no issues | Не проверяет Compose/demo runtime |
| `git diff --check` | Exit 0 | Patch whitespace |
| `sha256sum docs/source/Кейс_Платформа_соревнований.pdf` | SHA совпал с `docs/source/README.md` | Проверяет первичный PDF, не acceptance |

В первой targeted попытке concurrency test упал с SQLite `database table is locked`; conditional update сохранял cap, но exception не был обработан. Добавлен ограниченный retry transient lock, после чего обе race проверки прошли. Это поведение зафиксировано, а не скрыто.

## Решения и отклонения

- Bracket integration contract полностью опирается на docs и подтверждение пользователя; специальный ответ не назначенного A2-исполнителя не требовался.
- Canonical fallback для неуказанного seed определён сервисом как user UUID ascending после всех явно seeded entrants; `seed` в DB не меняется автоматически.
- Реальный release/demo/acceptance статус не повышен. PR отсутствует; feature-код недоступен в `develop`.
- Не редактировались `backend/apps/competition/`, `backend/apps/events/`, `context/STATE.md` и чужие branches.

## Блокеры и риски

Нет блокера для A1-03.3. До интеграции A2 вызов сервиса не подтверждён реальным consumer. SQLite concurrency проверена на shared in-memory test DB; deployment с file-backed WAL и отдельными API process не запускался. T03/T05/T20 полными не объявляются.

## Передача следующему агенту

На той же `feature/tournament-roster` выполнить A1-03.4: перечитать PDF M01/M03 и соответствующие T03/T05 acceptance, перепроверить freeze/no-delete history boundary и все audits/API/data-model, затем final review feature diff. После A1-03.4 создать PR в `develop`; только после подтверждённого merge обновить `context/STATE.md`.
