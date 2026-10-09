# Агент 1: платформа и интеграция

- Статус: `IN_PROGRESS` — A1-02 интегрирована и STATE синхронизирован; начата A1-03.
- Назначенный исполнитель: Codex, agent 1.
- Текущая задача/ветка/база: `A1-03` / `feature/tournament-roster` / `3b2b0ad` (`origin/develop`).
- Пути текущего среза: `backend/config/`, `backend/apps/common/`, `backend/apps/accounts/`, `backend/apps/tournaments/`, `manage.py`, `pyproject.toml`, `uv.lock`, `backend/Dockerfile`, `compose.yaml`, `.env.example`, `scripts/`, `deploy/nginx/`.
- Задачи роли: `A1-01`–`A1-06` из `ROADMAP.md`.
- Последний аудит/PR/проверки: [A1-03.1 tournament CRUD](../audits/2026-10-09T152726+0300-agent-1-A1-03-1-tournament-crud.md) — локальный feature-only срез; [PR #6](https://github.com/D0UP1G/FirsterChuv/pull/6) merged at `3b2b0ad`; предыдущий A1-02 integration/state-sync audit — [файл](../audits/2026-10-09T151339+0300-agent-1-A1-02-integration-state-sync.md).

## Разбивка задач на малые шаги

Статусы отражают только эту карточку и не означают интеграцию в `develop`.

### A1-01 · `feature/platform-bootstrap` · `DONE` — merged PR #2 at `2484d86`

- [x] A1-01.1 Создать Python/Django структуру и зафиксировать зависимости; `uv sync --frozen --all-groups` выполнен.
- [x] A1-01.2 Настроить env, UTC и SQLite timeout/WAL; smoke подтвердил WAL/5000 ms. Deploy check оставил только ожидающие TLS reverse proxy предупреждения HSTS/HTTPS.
- [x] A1-01.3 Создать custom User с UUID и глобальной ролью; `0001_initial` применена.
- [x] A1-01.4 Создать общие типы и интерфейсы MatchPort, JudgeProvider и EventWriter без реализации чужих доменов.
- [x] A1-01.5 Настроить ASGI, `/api/v1` без slash redirect, JSON error envelope и минимальный `/health`; покрыто тремя common tests.
- [x] A1-01.6 Собрать backend image, проверить Compose со всеми профилями и API health/restart с общим SQLite volume; `web` и runtime-процессы не запускаются до вкладов агентов 2–4.
- [x] A1-01.7 Проверить `.env.example`, `scripts/manage.sh check` и реальный `scripts/dev.sh` startup/health.
- [x] A1-01.8 Diff reviewed; common tests, Django checks, migration checks, Compose config/build и API smoke выполнены. Полные T01/T02/T20 остаются `NOT_RUN`.

### A1-02 · `feature/account-roles` · `DONE` — merged PR #5 at `c64555c`

- [x] A1-02.1 Реализовать register/login/logout/me и явную CSRF protection; тесты покрывают session, token rotation, ошибки, inactive user и rate limit.
- [x] A1-02.2 Добавить `IsApplicationAdmin`/`IsParticipant` по active global role; проверено, что `is_staff`/`is_superuser` не заменяют роль. Турнирные actions и object ownership останутся владельцам A1-03/A2.
- [x] A1-02.3 Добавить защищённую management command для начального admin без пароля в argv/logs; TTY prompt/confirmation, secret injection, idempotency, refusal to promote и отсутствие Django superuser покрыты тестами.
- [x] A1-02.4 Сверить все критерии T02/T20 с PDF кейса, requirements, API/security contracts и фактическими тестами; непокрытые domain/UI/sandbox сценарии оставлены явно открытыми.

### A1-03 · `feature/tournament-roster` · `IN_PROGRESS`

- [x] A1-03.1 Модель и admin-only CRUD турнира: поля M01, strict input, config, даты/status, безопасный delete/archive; API contract и миграции. Feature-only, audit attached to implementation; not merged.
- [ ] A1-03.2 Participant directory и roster: список active accounts, назначение, список, числовой seed, удаление/логическое снятие.
- [ ] A1-03.3 Capacity/uniqueness: транзакционный условный счётчик, ограничения БД, inactive/admin/duplicate guards; `freeze_roster(tournament_id)` вызывается при создании bracket в той же внешней atomic transaction согласно `docs/architecture/match-engine.md` и API contract. Решение пользователя: следовать docs; ответ получен 2026-10-09.
- [ ] A1-03.4 Сверить M01/M03 и T03/T05 с PDF, проверить историю played entrants, записать аудит с фактическими ограничениями сценариев.

Подшаги исполнения: .1 contract/model → migration → CRUD/security; .2 participant model → admin directory → roster API; .3 concurrency/freeze/replacement boundary → API tests; .4 case cross-check → feature review/audit/PR. После каждого завершённого среза сверить `ROADMAP.md`, API/data-model docs и кейс. `context/STATE.md` меняется только после подтверждённой интеграции в `develop`.

### A1-04 · `feature/tournament-invites` · `TODO`

- [ ] A1-04.1 Реализовать invite token generation/hash, просмотр metadata и отзыв.
- [ ] A1-04.2 Реализовать истечение, maxUses и атомарный accept после регистрации.
- [ ] A1-04.3 Защитить повторный/concurrent accept и tournament cap.
- [ ] A1-04.4 Сверить T04 и записать ограничения формата/ссылок.

### A1-05 · `feature/mvp-integration` · `TODO`

- [ ] A1-05.1 Интегрировать готовые feature PR в порядке зависимостей, не подменяя чужое владение.
- [ ] A1-05.2 Сверить миграции, API/DTO, события, OpenAPI и один origin с владельцами модулей.
- [ ] A1-05.3 Проверить сквозной сценарий полуфинал → продвижение в финал и фиксировать только фактические результаты.
- [ ] A1-05.4 Обновить `context/STATE.md` только после подтверждённой интеграции в `develop`.

### A1-06 · `feature/demo-readiness`, затем `release/0.1.0` · `TODO`

- [ ] A1-06.1 Подготовить одну проверенную команду старта, env, ожидание readiness и однократные миграции.
- [ ] A1-06.2 Обеспечить bootstrap admin, официальный package import и безопасное восстановление worker.
- [ ] A1-06.3 Совместно пройти T01/T18–T21, подготовить demo и видео до пяти минут.
- [ ] A1-06.4 Создать release branch/tag и выполнить обратную интеграцию по GitFlow после полного release gate.

## Владение и передача

- Владею: `backend/config/`, `backend/apps/common/`, `backend/apps/accounts/`, `backend/apps/tournaments/` (включая invites/participants), root tooling, Compose/CI, общей цепочкой миграций, интеграцией и релизом.
- Не менять пути агентов 2–4 без согласованной передачи. Общие контракты и миграции сверять с потребителями до изменения.
- Передача агентам 2–4: стабильные пути, auth dependency, ID-модели, конфигурация, миграционная база и локальный запуск.
- Следующий шаг: A1-03.2 — active participant directory, participant model и admin roster API; затем .3 implement the agreed `freeze_roster` service without editing Agent 2 paths.
