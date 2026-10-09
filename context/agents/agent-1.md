# Агент 1: платформа и интеграция

- Статус: `IN_PROGRESS` — начата задача `A1-01`.
- Назначенный исполнитель: Codex, agent 1.
- Текущая задача/ветка/база: `A1-01` / `feature/platform-bootstrap` / `e5f421b` (`origin/develop`).
- Пути текущего среза: `backend/config/`, `backend/apps/common/`, `backend/apps/accounts/`, `backend/apps/tournaments/`, `manage.py`, `pyproject.toml`, `uv.lock`, `backend/Dockerfile`, `compose.yaml`, `.env.example`, `scripts/`, `deploy/nginx/`.
- Задачи роли: `A1-01`–`A1-06` из `ROADMAP.md`.
- Последний аудит/PR/проверки: [A1-01 audit](../audits/2026-10-09T134327+0300-agent-1-A1-01.md) и follow-up; PR ещё не создан.

## Разбивка задач на малые шаги

Статусы отражают только эту карточку и не означают интеграцию в `develop`.

### A1-01 · `feature/platform-bootstrap` · `IN_PROGRESS`

- [x] A1-01.1 Создать Python/Django структуру и зафиксировать зависимости; установка и clean run ещё не подтверждены.
- [x] A1-01.2 Настроить env, настройки безопасности, UTC и SQLite с timeout/WAL; runtime-поведение не проверено.
- [x] A1-01.3 Создать custom User с UUID и глобальной ролью; initial migration создана, применение не проверено.
- [x] A1-01.4 Создать общие типы и интерфейсы MatchPort, JudgeProvider и EventWriter без реализации чужих доменов.
- [x] A1-01.5 Настроить ASGI, `/api/v1` без slash redirect, единый формат ошибок и безопасный `/health`; endpoint не запущен.
- [x] A1-01.6 Добавить образ backend и каркас Compose для web, API, match-clock и judge-worker с общим SQLite volume; worker-команды пока placeholders.
- [x] A1-01.7 Добавить фактические `.env.example` и локальные dev-команды; сценарий не acceptance-tested.
- [ ] A1-01.8 Сверить diff и выполнить согласованные проверки; непроверенное оставить явно `NOT_RUN`.

### A1-02 · `feature/account-roles` · `TODO`

- [ ] A1-02.1 Реализовать register/login/logout/me и явную защиту CSRF для auth mutations.
- [ ] A1-02.2 Назначать участнику роль только сервером; закрыть admin actions role/object permissions.
- [ ] A1-02.3 Добавить защищённую management command для начального admin без пароля в argv/logs.
- [ ] A1-02.4 Сверить T02/T20 и обновить контракт, если реализация выявит расхождение.

### A1-03 · `feature/tournament-roster` · `TODO`

- [ ] A1-03.1 Реализовать модель и admin-only CRUD турнира с датами, форматом, visibility и cap.
- [ ] A1-03.2 Реализовать назначение, список, удаление и числовой seed участников.
- [ ] A1-03.3 Защитить cap/уникальность и согласовать roster freeze с агентом 2 до API изменений.
- [ ] A1-03.4 Сверить T03/T05; не удалять историю сыгравшего участника.

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
- Следующий шаг: завершить подзадачи `A1-01.1`–`A1-01.7` в этой feature-ветке и записать результаты/непроверенное в аудит.
