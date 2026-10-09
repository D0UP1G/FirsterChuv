# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-02` — `DONE` по интеграции: [PR #24](https://github.com/D0UP1G/FirsterChuv/pull/24) merged commit `505a2bc0cee82281becb431996bf3a62827edac8`; merge checkpoint — `context/audits/2026-10-09T210237+0300-agent-4-P4-02-merge.md`. Полный T03–T05 остаётся частично принят по ограничениям implementation audit.

- `P4-03` — `DONE` по интеграции: PR [#27](https://github.com/D0UP1G/FirsterChuv/pull/27) влит merge commit `15e3edf4fdfe7910f0984f97f26eee8589d5319b`; merge checkpoint — `context/audits/2026-10-09T212320+0300-agent-4-P4-03-merge.md`. Полные M04–M08/T06–T11 и API/browser CONNECT остаются частичными до runtime integration.
- P4-03 правило подключения: PR #7 bracket runtime и provider PR не входят в `develop`; admin catalog PR #26 также открыт. Реальный `GET /problems`/bracket/match CONNECT выполнять по одному endpoint и exact SHA после интеграции; до этого использовать contracts v1/dev transport и показывать missing-endpoint error.

- `P4-04` — `IN_PROGRESS`; ветка `feature/participant-workspace`, база `15e3edf4fdfe7910f0984f97f26eee8589d5319b` (`origin/develop`). Пути: `frontend/**`, эта карточка, P4-03 merge checkpoint и audit P4-04. Подзадачи: (1) безопасная страница матча: task navigation/status/timer, Markdown/TeX/tables/examples и allowlisted images, условие закрыто до старта участнику; (2) редактор с подсветкой/отступами/скобками/hotkeys и только реально доступными языками/templates; (3) локальные drafts по user/run/problem/language/revision, сохранение при reload/task/language switch; (4) server draft CAS/conflict UI, сохраняющий обе версии; (5) async submit/status/verdict/CE/history только при реальном API; (6) tests и browser dev scenario.
- P4-04 зависимости: PR #21 private drafts, #15 submission queue, #25/#26 problem API/catalog и match runtime пока не вошли в `develop`. Их ветки не использовать как production dependency. До интеграции API работать через явно включаемый dev scenario/local persistence; production показывает недоступность endpoint и не рисует mock verdict. CONNECT делать по одному endpoint после merge и проверки contract на exact SHA.

- `P4-01` — `DONE` по integration: [PR #22](https://github.com/D0UP1G/FirsterChuv/pull/22) merged merge commit `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`; CI прошёл. Полный T02/T20/browser acceptance остаётся частичным; результат зафиксирован в `context/audits/2026-10-09T202939+0300-agent-4-P4-01-merge.md`.

- P4-02 использует существующий реальный CRUD/directory/roster/invite API, не заменяет его mock transport. Полный браузерный сценарий admin + два participant выполняется на disposable SQLite и синтетических адресах; данные доступа не сохранять в репозитории/аудитах.
- Следующая READY после P4-04: P4-05 anonymous map/projector/reducer/event dedupe/resync/reconnect. UI slice можно делать до SSE/PublicAccess API на изолированных dev fixtures; production не подменяет HTTP/SSE fixture-данными.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Для P4-02 созданы implementation/publication/merge audits; подробные границы browser CONNECT указаны в P4-02 audit. P4-03 UI slice интегрирована в `develop` на `15e3edf`; P4-04 начата от этого exact SHA. Реальный CONNECT, P4-05 map и полный demo остаются открытыми. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
