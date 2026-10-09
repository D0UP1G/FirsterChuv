# Агент 1: платформа и запуск

Карточку перепланировал координатор по запросу команды 2026-10-09; это наблюдаемый статус и назначения, не новая рабочая сессия владельца.

- Реализация: bootstrap/auth/roles/tournament/roster срезы A1-01/02/03 интегрированы PR #2/#5/#8; state sync #4/#6/#9 тоже merged.
- Приёмка: полные T01/T02/T03/T05/T20 ещё открыты; 37 backend tests повторены координатором на develop 146b2cb.
- Новое первое задание: **P1-01 READY**, feature/tournament-invites. Известный отдельный checkout этой ветки уже существует; использовать свой занятый checkout, не создавать дубликат и не менять чужую ветку.
- База перед edits: fetch и актуальный origin/develop; последний проверенный SHA 146b2cb. Обновить этот пункт своим фактическим SHA.
- Пути: backend/config, common, accounts, tournaments; tooling/CI/Compose/proxy. Свои миграции и fixtures roster.json.
- Очередь: P1-01 приглашения → P1-02 CI/короткие подключения → P1-03 proxy/share access → P1-04 Compose → P1-05 release gate.
- Если ждёт интеграция: делать CI/proxy/Compose; не ждать весь A2/A3/A4. STATE sync не блокирует начало задачи.
- Исторические подтверждения: [A1-03 review](../audits/2026-10-09T154714+0300-agent-1-A1-03-4-case-cross-check.md), [integration](../audits/2026-10-09T155025+0300-agent-1-A1-03-integration-state-sync.md), PR #8/#9.
- Следующий шаг: принять P1-01 в своей карточке, записать IN_PROGRESS/branch/base/paths, реализовать expiry/maxUses/revoke/atomic accept на уже готовом roster. Не открывать заново merged STATE PR #9.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
