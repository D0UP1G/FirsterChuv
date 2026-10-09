# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-02` — `DONE` по интеграции: [PR #24](https://github.com/D0UP1G/FirsterChuv/pull/24) merged commit `505a2bc0cee82281becb431996bf3a62827edac8`; merge checkpoint — `context/audits/2026-10-09T210237+0300-agent-4-P4-02-merge.md`. Полный T03–T05 остаётся частично принят по ограничениям implementation audit.

- `P4-03` — `DONE` по интеграции: PR [#27](https://github.com/D0UP1G/FirsterChuv/pull/27) влит merge commit `15e3edf4fdfe7910f0984f97f26eee8589d5319b`; merge checkpoint — `context/audits/2026-10-09T212320+0300-agent-4-P4-03-merge.md`. Полные M04–M08/T06–T11 и API/browser CONNECT остаются частичными до runtime integration.
- P4-03 правило подключения: PR #7 bracket runtime и provider PR не входят в `develop`; admin catalog PR #26 также открыт. Реальный `GET /problems`/bracket/match CONNECT выполнять по одному endpoint и exact SHA после интеграции; до этого использовать contracts v1/dev transport и показывать missing-endpoint error.

- `P4-04` — `IN_REVIEW`; PR [#28](https://github.com/D0UP1G/FirsterChuv/pull/28), ветка `feature/participant-workspace`, база `15e3edf4fdfe7910f0984f97f26eee8589d5319b` (`origin/develop`), head при публикации `a2e93cafd30c50468af3b10612a43c3eef06c49d`. UI slice собран, проверки `12 files / 47 tests`, typecheck/build проходят; lint exit 0 с 5 set-state-in-effect warnings. Implementation audit: [2026-10-09T214806+0300-agent-4-P4-04.md](../audits/2026-10-09T214806+0300-agent-4-P4-04.md); publication audit: [2026-10-09T214919+0300-agent-4-P4-04-publication.md](../audits/2026-10-09T214919+0300-agent-4-P4-04-publication.md). Подзадачи выполнены на UI/dev fixture уровне: (1) safe match workspace/task status/timer, Markdown/TeX/tables/examples, allowlisted images и закрытие до старта; (2) CodeMirror с подсветкой/отступами/скобками/hotkey и только языками из API; (3) local drafts по user/run/problem/language/revision и восстановление после task switch/reload; (4) server CAS/conflict UI с обеими версиями; (5) async submission/status/history/CE UI и API client без фиктивных verdicts; (6) security/API/local state tests и browser dev scenario. Полные P01–P03/E01–E04 acceptance и runtime/API CONNECT не объявляются завершёнными.
- P4-04 зависимости: PR #21 private drafts, #15 submission queue, #25/#26 problem API/catalog и match runtime пока не вошли в `develop`. Их ветки не использовать как production dependency. До интеграции API работать через явно включаемый dev scenario/local persistence; production показывает недоступность endpoint и не рисует mock verdict. CONNECT делать по одному endpoint после merge и проверки contract на exact SHA.

- `P4-01` — `DONE` по integration: [PR #22](https://github.com/D0UP1G/FirsterChuv/pull/22) merged merge commit `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`; CI прошёл. Полный T02/T20/browser acceptance остаётся частичным; результат зафиксирован в `context/audits/2026-10-09T202939+0300-agent-4-P4-01-merge.md`.

- P4-02 использует существующий реальный CRUD/directory/roster/invite API, не заменяет его mock transport. Полный браузерный сценарий admin + два participant выполняется на disposable SQLite и синтетических адресах; данные доступа не сохранять в репозитории/аудитах.
- Следующая READY после P4-04: P4-05 anonymous map/projector/reducer/event dedupe/resync/reconnect. UI slice можно делать до SSE/PublicAccess API на изолированных dev fixtures; production не подменяет HTTP/SSE fixture-данными.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Для P4-02 созданы implementation/publication/merge audits; подробные границы browser CONNECT указаны в P4-02 audit. P4-03 UI slice интегрирована в `develop` на `15e3edf`; P4-04 начата от этого exact SHA. Реальный CONNECT, P4-05 map и полный demo остаются открытыми. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
