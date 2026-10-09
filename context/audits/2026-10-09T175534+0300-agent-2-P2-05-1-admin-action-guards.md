# P2-05.1 — чистые guards админских действий

## Цель

Подготовить независимый domain-срез проверок ручных административных действий матча, чтобы следующий слой мог применять решения атомарно. Общий `context/STATE.md` не менялся: до merge результат принадлежит feature-ветке.

## Изменения

- Добавлен `backend/apps/competition/domain/admin_actions.py` с неизменяемыми снимками доверенного контекста, проверкой активной роли admin и участника, UUID, причины и command key.
- Добавлены pure planners для pause/resume, ограниченного продления, технического результата, rematch и замены участника. Проверяются допустимый run status, существование run там, где оно требуется, участники матча и факт старта downstream.
- Rematch и замена в ходе игры планируют supersede старого run и новый run без переноса счёта. Замена до старта сохраняет текущий статус и меняет только заданный слот.
- Добавлены 12 unit-тестов на разрешённые переходы и отказные случаи.
- Добавлен `test_admin_actions.py` в список standalone suite интегрированного CI runner `scripts/check_domain_suites.py`, чтобы P2-05.1 регрессии запускались в CI.
- Обновлена карточка агента 2. Ветка начиналась от `origin/develop` `cad34ea4ddf1171779dc22139f2e1533160b5015`; после появления PR #17 в develop ветка синхронизирована merge-коммитом, включающим `origin/develop` `1f60aa9ad93a818d12c0b04b94cacec3f25b8d4e`.

## Контракты и границы

Руководствовался P2-05 в `ROADMAP.md`, требованием M08 и сценариями T11/T20, разделом «Ручные действия» в `docs/architecture/match-engine.md` и admin routes в `docs/architecture/api.md`. API, DTO, события, ORM, миграции, persistence и wiring не менялись. `command_id` проверяется и попадает в план, но дедупликация пока не реализована. Максимум продления передаётся вызывающей стороной из политики турнира. Снимки actor/participant/match должны создаваться сервером из доверенных данных: эти pure проверки сами по себе не устанавливают подлинность клиента.

## Проверки

- `python3 -m unittest discover -s backend/apps/competition/tests -p 'test_admin_actions.py' -v` — 12 тестов пройдены.
- `python3 -m compileall -q backend/apps/competition/domain/admin_actions.py backend/apps/competition/tests/test_admin_actions.py` — завершилась успешно.
- `python3 scripts/check_domain_suites.py` — runner обнаружил и запустил `test_admin_actions.py`, все 12 тестов пройдены. Bracket/clock/scoring suite files отсутствуют в текущем develop и этим запуском не проверялись.
- `git diff --check` — замечаний нет.
- Проверка длины строк через `awk 'length($0) > 100 ...'` для новых Python-файлов — строк длиннее 100 символов нет.

Это не проверка HTTP/прав в реальном API, транзакционных гонок, сохранения аудита, command-idempotency или browser flow; полная приёмка M08/T11/T20 остаётся открытой.

## GitFlow и статус

Ветка `feature/match-admin-actions` создана от `cad34ea4ddf1171779dc22139f2e1533160b5015`, затем обычным merge синхронизирована с новым `origin/develop` `1f60aa9ad93a818d12c0b04b94cacec3f25b8d4e`. PR #17 уже интегрирован в develop; открытые PR #7, #11, #13, #15 и #16 и их ветки не изменялись. Реализация и этот аудит будут опубликованы отдельным PR в `develop`; PR link и итоговый head SHA будут добавлены publication-записью после создания PR.

## Ограничения и дальнейшая интеграция

P2-05.1 закрывает только чистые решения/guards. Полный P2-05 остаётся незавершённым: последующий владелец persistence-интеграции должен хранить actor/reason/command receipt, атомарно сохранять run transitions/events и защищать downstream-start от гонки, сохраняя старую историю. Эта работа в данном срезе не начиналась.
