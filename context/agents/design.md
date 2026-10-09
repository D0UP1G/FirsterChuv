# Дизайн: макеты BLITZ_ARENA

Отдельная роль по прямому поручению команды 2026-10-10; не номерной агент, чужие задачи не занимает.

- Задача: `D-01` макет дизайна и разметки по брендбуку BLITZ_ARENA v2.0 без логики и подключения к API.
- Статус: `IN_REVIEW` — разметка и холст готовы, перенос в `frontend/src` не выполнялся.
- Ветка: `feature/design-blitz-arena`, база `origin/develop` `1b7cc9e`.
- Пути: `frontend/design/**`, `docs/architecture/decisions.md` (ADR18), эта карточка, собственный аудит. `frontend/src` не менялся.
- Следующий шаг для агента 4: перенести токены и классы из `frontend/design/blitz.css` в существующие CSS-файлы по README, не меняя логику и тесты; проверить `npm run build` и `npm test`.

[Аудит D-01](../audits/2026-10-10T004342+0300-design-D-01-blitz-arena.md), [README макетов](../../frontend/design/README.md).
