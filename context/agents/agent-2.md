# Агент 2: сетка и ход матча

- Статус: `IN_PROGRESS` — A2-01.4c–.5 реализованы в `competition`; ожидаю регистрации app и URL include в общих настройках, которыми владеет агент 1.
- Назначенный исполнитель: Codex в роли агента 2 по поручению команды, сессия 2026-10-09.
- Текущая задача/ветка/база: `A2-01.4c–.5` / `feature/bracket-runtime` / `b8947165ac08792751aa34e8a97c9c38ae11b17c` (`origin/develop`, PR #8 A1-03).
- Рабочая область: отдельный Git worktree `work/FirsterChuv-agent2`; планируемые пути `backend/apps/competition/` и эта карточка/аудит.
- Задачи: `A2-01`–`A2-05` из `ROADMAP.md`.
- Владеет: `backend/apps/competition/`, `backend/apps/events/`, их тестами и миграциями по согласованной цепочке.
- A2-01 breakdown:
  - [x] A2-01.1 Зафиксировать независимый входной контракт по активным участникам и уникальным числовым seed.
  - [x] A2-01.2 Построить детерминированную single-elimination раскладку с нормализацией seed и состояниями BYE/WAITING.
  - [x] A2-01.3 Проверить составы 2/3/4/5 участников, повторы генерации и некорректные roster.
  - [x] A2-01.3b Проверить отсутствие повторного появления игрока в нескольких слотах одного раунда для размеров сетки 2–16.
  - [x] A2-01.4a Сверить seed contract A1-03: null seed допустим, freeze возвращает канонический roster; builder назначает позиции по canonical order без записи фиктивных seed.
  - [x] A2-01.4b Сверить freeze boundary A1-03: вызов внутри общей atomic transaction при генерации; состав/seed после freeze неизменяемы; reset сетки не снимает freeze.
  - [x] A2-01.4c Добавить собственные модели match/slot/run со связями к tournament roster и первую competition migration; не менять модели/миграции владельца A1.
  - [x] A2-01.5a В одной транзакции заморозить roster и сохранить сетку; повторная генерация возвращает существующие матчи.
  - [x] A2-01.5b Реализовать service-level явный reset и атомарное редактирование пар до старта; пересобирать downstream slots/byes и валидировать уникальность по всему первому раунду.
  - [x] A2-01.5c Проверить constraints, persistence, rollback freeze, повторную генерацию, reset, ручные пары и API доступ.
  - [ ] A2-01.5d Согласовать и добавить HTTP DTO/route для ручного редактирования пар по общему API contract.
  - [ ] A2-01.5e Дождаться регистрации app и URL include в A1-owned settings/API root, затем перепроверить штатный запуск без test-only settings.
- Сверка: `origin/develop` `b894716` включает PR #8 A1-03. `freeze_roster` возвращает seed-ascending roster, null seed last по `userId`, revalidates active role и поддерживает rollback во внешней транзакции. PR #3 принадлежит агенту 3; его зона не менялась.
- PR #7 `feature/bracket-runtime` → `develop` остаётся draft. Агенту 1 задан вопрос о регистрации `CompetitionConfig` в `INSTALLED_APPS` и включении competition urls в root API URLs, т.к. эти файлы принадлежат A1; до ответа они не редактировались.
- Зависимости: A1-03 интегрирована; A2-02 далее требует A3-02 для связи задач.
- Передача: функции допуска посылки и регистрации результата, публичный snapshot, события и SSE для агентов 3–4.
- Последние аудиты: [основной A2-01](../audits/2026-10-09T135408+0300-agent-2-A2-01.md), [публикация PR #7](../audits/2026-10-09T152022+0300-agent-2-A2-01-publication.md), [сверка и контракт A1-03](../audits/2026-10-09T153228+0300-agent-2-A2-01-coordination.md), [проверка раундовой уникальности](../audits/2026-10-09T154602+0300-agent-2-A2-01-round-invariant.md), [persistence и API сетки](../audits/2026-10-09T162433+0300-agent-2-A2-01-persistence.md). Локальная feature-ветка синхронизирована merge-коммитом A1-03 `b894716`; PR #7 открыт в draft.
- Проверка A2-01.3b: `uv run --env-file .env.example python -m unittest discover -s backend/apps/competition/tests -p test_bracket.py -v` — 8 доменных тестов успешно; отдельный инвариант проверен для всех размеров 2–16.
- Проверка persistence/API текущей сессии: полный `manage.py test` через временные settings с `CompetitionConfig`/urls — 58 passed; `makemigrations --check --dry-run` — no changes; штатные `INSTALLED_APPS` и API include пока ждут владельца A1.

Обновлять фактические поля после каждой рабочей сессии; не удалять предыдущие аудиты.
