# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-01` — `IN_REVIEW` (реализация завершена; интеграция в `develop` ожидает PR); ветка `feature/frontend-shell-auth`, база `ae0846b22953527d74835febf963169e2093238d` (`origin/develop`).
- Подзадачи: (1) React/TypeScript scaffold, lockfile, production build, router и API client; (2) реальный CSRF bootstrap/rotation и register/login/logout/me; (3) роль participant/admin в навигации, anonymous public route без login redirect и состояния loading/error/retry/empty; (4) проверить сборку и auth-сценарии, описать результат аудитом.
- Планируемые пути: `frontend/**`, эта карточка и `context/audits/2026-10-09T201024+0300-agent-4-P4-01.md`.
- Проверка среза: implementation — готова; browser/auth acceptance — частичная; полный T02/T20 не закрывается этим UI-срезом.

- Первое READY P4-01: React/TS/lockfile/build/router и real csrf/register/login/logout/me. API доступен сейчас, не ждать A1/A2/A3. Register всегда participant, role navigation, public без redirect, logout чистит private user cache.
- Следующее READY P4-02: real CRUD/directory/roster/seed/cap/invites/create/copy/revoke/preview/register/accept. Backend #12 merged, не заменять его mock transport. Проверить сценарий admin + два participant в browser.
- Резерв READY: P4-03 match/action components по v1 dev transport, P4-04 editor/safe Markdown/TeX/local drafts/reload/task switching, P4-05 map/projector/reducer/dedupe/reconnect. Это можно делать до future endpoints.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Пока ни browser flow, ни editor/drafts/map/full demo не проверены. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
