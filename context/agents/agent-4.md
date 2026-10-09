# Агент 4: React и пользовательские сценарии

Перепланировано координатором 2026-10-09. В опубликованных refs/PR и develop frontend не найден; неопубликованная работа другого checkout этим не исключается.

- Исполнитель: пока не подтверждён опубликованной карточкой.
- Первое задание: **P4-01 READY**, feature/frontend-shell-auth от актуального origin/develop (последний проверенный SHA 146b2cb).
- Пути: frontend, UI/browser tests; backend config и соседние apps не менять.
- Реальный API доступен сейчас: auth/csrf/register/login/logout/me, tournament CRUD/directory/roster. Сразу подключить его.
- Будущие match/problem/submission/draft/public DTO: parallel-contracts + contracts/mvp-v1. UI разрабатывается через отдельный dev transport, без ожидания backend branches; production не содержит fallback fixtures.
- Очередь: P4-01 shell/auth → P4-02 CRUD/invites → P4-03 admin match UI → P4-04 workspace/editor → P4-05 anonymous map/projector → P4-06 browser CONNECT по одному готовому API.
- Во время ожидания CONNECT: следующая страница/components, local draft/reducer/dedupe/XSS tests. Не ждать весь A1/A2/A3.
- Приёмка: UI/browser checks ещё не выполнены. Fixtures не подтверждают real verdict/official task/security/demo.
- Следующий шаг: проверить, нет ли своего начатого checkout, записать фактический task/branch/base/status, сделать React build и auth; каждый готовый endpoint подключать маленьким срезом.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
