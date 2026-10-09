# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-02` — `DONE` по интеграции: [PR #24](https://github.com/D0UP1G/FirsterChuv/pull/24) merged commit `505a2bc0cee82281becb431996bf3a62827edac8`; merge checkpoint — `context/audits/2026-10-09T210237+0300-agent-4-P4-02-merge.md`. Полный T03–T05 остаётся частично принят по ограничениям implementation audit.

- `P4-03` — `IN_REVIEW`; реализация в `feature/admin-match-ui` от базы `505a2bc0cee82281becb431996bf3a62827edac8` (`origin/develop`); PR [#27](https://github.com/D0UP1G/FirsterChuv/pull/27), head `a8cae222d9b04b9e2ccd788251ab28dce6087ea0`; audits: `context/audits/2026-10-09T212030+0300-agent-4-P4-03.md` и `context/audits/2026-10-09T212113+0300-agent-4-P4-03-publication.md`. Добавлены typed bracket/match/config/action DTO, изолированный dev transport, bracket admin view (полные пары/BYE/WAITING), task selection/pre-start config, start/manual/both_ready, readiness, reasoned/idempotent admin actions, UI/API tests и browser verification сценария. Production transport не включает fixtures и показывает ошибки отсутствующих endpoints. CI проверяется на PR; задача не интегрирована до merge в develop.
- P4-03 правило подключения: PR #7 bracket runtime и provider PR не входят в `develop`; admin catalog PR #26 также открыт. Реальный `GET /problems`/bracket/match CONNECT выполнять по одному endpoint и exact SHA после интеграции; до этого использовать contracts v1/dev transport и показывать missing-endpoint error.

- `P4-01` — `DONE` по integration: [PR #22](https://github.com/D0UP1G/FirsterChuv/pull/22) merged merge commit `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`; CI прошёл. Полный T02/T20/browser acceptance остаётся частичным; результат зафиксирован в `context/audits/2026-10-09T202939+0300-agent-4-P4-01-merge.md`.

- P4-02 использует существующий реальный CRUD/directory/roster/invite API, не заменяет его mock transport. Полный браузерный сценарий admin + два participant выполняется на disposable SQLite и синтетических адресах; данные доступа не сохранять в репозитории/аудитах.
- Следующие READY после merge P4-03: P4-04 editor/safe Markdown/TeX/local drafts/reload/task switching; P4-05 map/projector/reducer/dedupe/resync/reconnect. Их можно делать до future endpoints на изолированных dev transports, не выдавая fixtures за production.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Для P4-02 созданы implementation/publication/merge audits; подробные границы browser CONNECT указаны в P4-02 audit. P4-03 implementation завершена и передана на review от подтверждённого `origin/develop` `505a2bc`; интеграционный CONNECT, P4-04 editor/drafts, P4-05 map и полный demo остаются открытыми. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
