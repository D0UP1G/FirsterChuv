# Агент 4: React и пользовательские сценарии

Перепланировано координатором по поручению команды 2026-10-09. Frontend не найден в опубликованных refs/PR; неопубликованную работу своего checkout проверить перед созданием нового.

## Текущая задача

- `P4-02` — `IN_REVIEW`; ветка `feature/admin-roster-invites-ui`, база `f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (`origin/develop`). Пути: `frontend/**`, эта карточка и audits P4-01 merge checkpoint/P4-02. PR будет направлен в `develop` с merge commit.
- Подзадачи: (1) настоящий API UI для создания/редактирования/списка турниров с пустым, загрузочным и ошибочным состояниями; (2) каталог участников, добавление/снятие, ручной seed и видимые ошибки cap/freeze/role; (3) создание, копирование и отзыв invite; (4) публичный preview, регистрация/вход по invite и accept без ручных SQL/API действий для двух новых участников; (5) UI/API tests и браузерная проверка на изолированной тестовой БД.
- Проверка среза: реальный CRUD/invite CONNECT и browser-сценарий на disposable SQLite проверены, включая двух участников, отзыв, истечение, cap, preview и seed. Два аккаунта проверялись последовательно в одном браузерном профиле; независимые сессии, ручное roster removal и полные T03–T05 остаются частично непроверенными. Статус требований не повышать до подтверждённого merge/приёмки.

- `P4-01` — `DONE` по integration: [PR #22](https://github.com/D0UP1G/FirsterChuv/pull/22) merged merge commit `f7f4e2d42b42170b2169b608d1e86b6eb7af6921`; CI прошёл. Полный T02/T20/browser acceptance остаётся частичным; результат зафиксирован в `context/audits/2026-10-09T202939+0300-agent-4-P4-01-merge.md`.

- P4-02 использует существующий реальный CRUD/directory/roster/invite API, не заменяет его mock transport. Полный браузерный сценарий admin + два participant выполняется на disposable SQLite и синтетических адресах; данные доступа не сохранять в репозитории/аудитах.
- Резерв READY: P4-03 match/action components по v1 dev transport, P4-04 editor/safe Markdown/TeX/local drafts/reload/task switching, P4-05 map/projector/reducer/dedupe/reconnect. Это можно делать до future endpoints.
- P4-06 CONNECT каждого готового API по одному на exact SHA. При missing API runtime показывает error, fixtures только dev/tests; mock verdict не выдаётся за работающий MVP.
- Не завершать дорожку при ожидании одного endpoint: в той же сессии продолжать следующую страницу/editor/draft/map/test задачу. Собственный audit/card/PR после среза, затем следующая READY работа до явного стопа или исчерпания доступной очереди.
- Пути: frontend/browser tests, соседние apps не менять. Private source/CE не загружать в public UI; XSS/unsafe URLs/diagnostics только plain text/sanitized rendering.
- Для P4-02 созданы отдельный implementation audit и запись о merge checkpoint P4-01; подробные границы browser CONNECT указаны в P4-02 audit. После merge P4-02 начать P4-03 на новой `feature/admin-match-ui` от актуального `origin/develop`; P4-04 editor/drafts, P4-05 map и полный demo остаются открытыми. R1 real smoke pipeline, затем R2 обязательные функции/R3 official T01–21.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
