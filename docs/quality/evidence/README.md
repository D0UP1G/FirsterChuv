# Evidence для приёмки

`scripts/acceptance/run_api_smoke.py` запускает ограниченный реальный HTTP сценарий на loopback с отдельной временной SQLite базой. Он сам применяет миграции, создаёт временного application admin, поднимает WSGI сервер на случайном localhost порту, проходит регистрации/CSRF/invite/bracket запросы и удаляет БД при завершении. `.env`, общая база, внешние API и Docker для этого API smoke не используются.

Запуск из корня репозитория в активном Python окружении:

```sh
uv run python scripts/acceptance/run_api_smoke.py
```

Для сохранения JSON выберите новый файл evidence, чтобы не перезаписать прежнюю запись:

```sh
uv run python scripts/acceptance/run_api_smoke.py --output docs/quality/evidence/2026-10-10T030000+0300-api-smoke.json
```

Для дополнительной проверки normalized importer на той же одноразовой базе используйте `--demo-import`; вместе с ним можно запросить synthetic sandbox probes флагом `--sandbox`:

```sh
uv run python scripts/acceptance/run_api_smoke.py --demo-import --sandbox
```

Поле `demoImport` сообщает только, что встроенная синтетическая задача прошла importer в disposable SQLite, и указывает её фактический `READY`/`NOT_READY`. Это не доказывает запуск Compose, доступность compiler или импорт в постоянную базу приложения. Отсутствующий Docker Engine оставляет sandbox probe `NOT_RUN`; полный G01/G03/G05 и M0 не повышаются до PASS.

Manifest фиксирует source SHA, base SHA и чистоту рабочего дерева до записи самого manifest. В evidence не попадают email, пароли, session/CSRF значения, invite token, тела HTTP запросов и URL приглашения. HTTP access logging отключён, redirects и proxy окружения не используются. Временный admin password передаётся management command только через окружение процесса.

Статусы `PASS` относятся только к перечисленным HTTP smoke checks. Полный M0, все G01–G06 и полные T01–T21 этот runner всегда оставляет `NOT_RUN`/`NOT_ACCEPTED`; для фактической приёмки нужны production providers, интегрированный SHA и доказательства из `docs/quality/m0-demo.md`/`mvp-acceptance.md`. Флаг `--sandbox` просит runner проверить Docker Engine и вызвать существующий `sandbox/smoke.py --case all`; отсутствие Engine означает `NOT_RUN`, а не PASS. Эта отдельная проверка покрывает только synthetic fixtures и не закрывает T18/T20. Queue recovery без реального production worker/factory также остаётся `NOT_RUN`. Test doubles, фикстуры и зелёный CI сами по себе не закрывают кейс.
