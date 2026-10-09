# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-02` — `DONE` по интеграции: [PR #24](https://github.com/D0UP1G/FirsterChuv/pull/24) merged commit `505a2bc0cee82281becb431996bf3a62827edac8`; merge checkpoint — `context/audits/2026-10-09T210237+0300-agent-4-P4-02-merge.md`. Полный T03–T05 остаётся частично принят по ограничениям implementation audit.

- `P4-03` — `IN_PROGRESS`; ветка `feature/admin-match-ui`, база `505a2bc0cee82281becb431996bf3a62827edac8` (`origin/develop`). Пути: `frontend/**`, эта карточка, P4-02 merge checkpoint и audit P4-03. Подзадачи: (1) typed bracket/match/config/action DTO и изолированный dev transport без production fixtures; (2) bracket admin view для полных пар, BYE и WAITING; (3) task selection и pre-start config; (4) start/manual/both_ready, readiness и admin actions с reason/idempotency; (5) tests и browser verification dev transport.
- P4-03 правило подключения: PR #7 bracket runtime и остальные provider PR не merged в develop; строить на contracts v1/dev transport, production путь показывает понятный missing-endpoint error. CONNECT выполнять после интеграции API по одному endpoint и exact SHA.

- `P4-01` — `DONE` по integration: [PR #22](https://github.com/D0UP1G/FirsterChuv/pull/22) merged merge commit `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`; CI прошёл. Полный T02/T20/browser acceptance остаётся частичным; результат зафиксирован в `context/audits/2026-10-09T202939+0300-agent-4-P4-01-merge.md`.

- P4-02 использует существующий реальный CRUD/directory/roster/invite API, не заменяет его mock transport. Полный браузерный сценарий admin + два participant выполняется на disposable SQLite и синтетических адресах; данные доступа не сохранять в репозитории/аудитах.
- Резерв READY: P4-03 match/action components по v1 dev transport, P4-04 editor/safe Markdown/TeX/local drafts/reload/task switching, P4-05 map/projector/reducer/dedupe/reconnect. Это можно делать до future endpoints.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Для P4-02 созданы implementation/publication/merge audits; подробные границы browser CONNECT указаны в P4-02 audit. P4-03 начата от подтверждённого `origin/develop` `505a2bc`; P4-04 editor/drafts, P4-05 map и полный demo остаются открытыми. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
