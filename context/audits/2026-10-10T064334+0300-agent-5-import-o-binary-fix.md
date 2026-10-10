# Аудит: Агент 5 / фикс O_BINARY в импортёре демо-задачи

- Автор/роль агента: Агент 5 по прямому поручению пользователя («сделай фикс сам»); файл принадлежит зоне A3.
- Начало и окончание: `2026-10-10T06:40:00+03:00` — `2026-10-10T06:43:34+03:00`.
- ID задач: P3-02.2 (дефект переносимости, не новая функция).
- Ветка: `feature/agent-5-import-o-binary`.
- Базовый SHA: `feef318e8ea9ceecb92570925f03c8f2db19874a` (`origin/develop`, merge #81).
- Статус: `IN_REVIEW` после публикации PR.
- PR / последующие коммиты: нет.

## Цель и исходное состояние

После слияния #85 тест `test_imports_an_explicit_normalized_archive_with_bounded_regular_file_read` падал на Windows с «archive is not a valid ZIP file». `_read_bounded_regular_file` открывает файл через `os.open` с флагами `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`; на Windows нет `O_BINARY`, поэтому чтение идёт в текстовом режиме и искажает ZIP. На Linux (CI) тест проходил.

## Выполненные изменения

- `backend/apps/problems/management/commands/import_demo_problem.py`: к флагам добавлен `getattr(os, "O_BINARY", 0)`. На Linux и macOS значение 0, поведение не меняется; ограничения размера, `O_NOFOLLOW` и проверка обычного файла сохранены.
- `context/agents/agent-5.md`: запись среза. Другие файлы, контракты, миграции не менялись.

## Сверка с кейсом

P01/P02/E02 (программный импорт демо-задачи) — только переносимость, требования не закрываются.

## Проверки

| Команда или сценарий | Результат | Ограничения |
|---|---|---|
| `manage.py test backend.apps.problems.tests.test_import_command` | до правки FAIL (не валидный ZIP), после правки 5 тестов OK | Только Windows воспроизводит дефект |
| problems + judge без `test_archive` | 36 тестов OK, 1 пропущен | `test_archive` на Windows падает отдельно (см. ниже) |
| `manage.py check` | без проблем | |

## Решения и отклонения

Правка в зоне A3 сделана по прямому поручению пользователя и ограничена одной строкой. Отдельное наблюдение, не исправлялось: `test_archive.test_rejects_traversal_absolute_windows_and_duplicate_paths` падает на Windows, потому что `zipfile.writestr` заменяет `\` на `/` и кейс `nested\escape` превращается в допустимое имя; на Linux тест проходит.

## Блокеры и риски

Нет. Windows-специфичный кейс в `test_archive` можно помечать пропуском на `os.name == "nt"` или собирать байты ZIP без нормализации имени; решение за A3.

## Передача следующему агенту

A3 при желании исправляет `test_archive` для Windows. Результат доступен в `develop` только после merge PR.
