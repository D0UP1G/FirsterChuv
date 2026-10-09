# Агент 2: сетка и ход матча

- Статус: `IN_PROGRESS` — A2-01 реализована в PR #7 (draft); A2-02 начата автономным pure-domain срезом clock rules, без task/API/ORM интеграции.
- Назначенный исполнитель: Codex в роли агента 2 по поручению команды, сессия 2026-10-09.
- Текущая задача/ветка/база: `A2-02.1 clock domain` / `feature/match-clock` / `146b2cb` (`origin/develop`). A2-01 продолжает жить в отдельной ветке `feature/bracket-runtime`, PR #7.
- Рабочие области: отдельные checkout `work/FirsterChuv-agent2-clock` и `work/FirsterChuv-agent2`.
- Задачи: `A2-01`–`A2-05` из `ROADMAP.md`.
- Владеет: `backend/apps/competition/`, `backend/apps/events/`, их тестами и миграциями по согласованной цепочке.
- Следующий шаг: после координации с агентами 1/3 связать clock rules с persisted MatchRun и task run; затем добавить атомарный submit guard и лёгкую management-команду clock.
- Зависимости: A2-02 task association требует A3-02; штатные app/URL integration и общая DB/API инфраструктура принадлежат агенту 1; verdicts и events приходят от агента 3.
- Передача: функции допуска посылки и регистрации результата, публичный snapshot, события и SSE для агентов 3–4.
- Последний аудит/PR/проверки: [A2-02.1 clock domain](../audits/2026-10-09T164411+0300-agent-2-A2-02-clock-domain.md); PR [#7](https://github.com/D0UP1G/FirsterChuv/pull/7) draft; clock domain: 12 tests passed, compileall и diff check чистые.

Обновлять фактические поля после каждой рабочей сессии; не удалять предыдущие аудиты.
