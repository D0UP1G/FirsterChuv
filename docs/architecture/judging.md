# Собственная проверка решений: вариант Б

Команда выбрала реальный запуск в собственной песочнице. Яндекс Контест используется только для будущего импорта; посылки туда не отправляются. Готовые Docker/isolate/nsjail допустимы как изоляция, полный сторонний judge-продукт не используется.

## Пакет и языки

Получить official README перед написанием importer. Пакет содержит Markdown/TeX/images, tests, validators, reference solutions, checkers, limits. Сохранить version/checksum и immutable mapping. Проверить пути/размеры/формат до использования; package scripts не выполнять на хосте.

Public statement/assets отделены от private тестов/checker/reference. Checker обязателен для multiple-correct-output; сравнение строк не заменяет предоставленный checker. Формат вызова checker/validator и code meanings берётся из пакета. Ошибка checker — инфраструктурный status, не автоматический WA.

Language registry задаётся сервером: pinned compiler image, фиксированные argv, source filename и шаблон. Для выбора языка нужны реально работающие компиляторы; минимально предложены Python 3 и C++ при наличии подходящих задач/образов. Точные версии фиксирует агент 3 после проверки, список UI берётся из API. Новые compiler images проходят те же security checks.

## Путь посылки

1. API проверяет role/own match/current run/RUNNING/problem/language/size и server clock. В короткой транзакции сохраняет source/idempotency/receivedAt/elapsedMs.
2. После успешного commit отвечает 202/QUEUED. Если запись не удалась, 202 не выдаётся.
3. Один trusted worker атомарно claim задачу, ставит leaseToken/leaseUntil и RUNNING. Не держит SQLite transaction во время execution.
4. Компиляция выполняется в отдельном ограниченном контейнере. Ошибки/таймаут стадии compile → CE с bounded diagnostics владельцу. Infrastructure failure отдельно.
5. Для каждого теста новый isolated solution container получает только конкретный stdin. Компилированный artifact либо source передаётся безопасно, без mounts с test package. Stdout/stderr ограничены по объёму и времени.
6. Внешний trusted orchestrator проверяет output. При custom checker он также запускается в отдельной ограниченной среде с нужными input/expected/actual, без серверных секретов.
7. Сохранить итог, metrics и private diagnostics через `ResultService`. В той же короткой транзакции обновить score/public events. Late/duplicate result защищён lease/run guards.
8. Удалить только собственные контейнеры/tmp artifacts. На crash recovery найти контейнеры по project/job labels, завершить их и вернуть незавершённую задачу в безопасный retry.

Compiler и run не исполняются в Django view или непосредственно в worker namespace. Наличие Docker Engine в worker не даёт коду доступ к его socket.

## Изоляция каждого запуска

- Network disabled; solution не получает DNS/сеть host или других compose services.
- Read-only root, non-root user, bounded tmpfs `/work`; никаких mounts хоста, `/proc` хоста, Docker socket, environment DB/API/import secrets.
- CPU/wall-clock/memory/pids limits, no-new-privileges, capabilities dropped, штатный/проверенный seccomp profile. Не использовать `--privileged`, host PID/network или ослабление seccomp для participant code.
- Ограничения stdout/stderr/files/tmpfs; timeout watchdog снаружи убивает/удаляет container даже если процесс не завершился.
- Stdin передаётся извне, закрытые тесты/эталон не видны solution. Source filename и argv из registry, не из client command.
- Валидаторы/reference/checkers из package запускаются в их собственном ограниченном окружении при необходимости, а не произвольным host shell.

Docker image собирает команда из фиксированного base; compiler code нельзя загружать arbitrary imageName из формы. Trusted worker с Docker socket имеет сильные полномочия на host: его HTTP interface не публикуется, данные solution не превращаются в docker command/options. Реальное отсутствие доступа проверяется сценариями T18/T20; документ не является доказательством неуязвимости.

## Verdict и сбой

| Наблюдение | Результат |
|---|---|
| Успешный запуск и output/checker всех тестов | OK |
| Неверный output / отрицательный checker verdict | WA |
| Превышен execution CPU/wall limit | TL |
| Подтверждён memory/OOM limit | ML |
| Runtime nonzero/signal без TL/ML | RE |
| Compile failure/compile stage limit | CE |
| Bounded output превышен | RE с internal reason output_limit_exceeded |
| Docker unavailable, disk/DB failure, invalid checker infrastructure | RETRY_WAIT/INFRA_FAILED, verdict null |

Не угадывать ML по любому SIGKILL: проверять OOM/timeout данные. Не считать Docker launch failure runtime ошибкой пользователя. Public viewer получает только verdict/task event; CE diagnostics и исходник доступны автору.

## Очередь и восстановление

Source и queue state persist в SQLite. Один worker, атомарный claim без `select_for_update` иллюзии, bounded retries с backoff и lease renewal. Новый lease не может принять result от старого worker. Сетевые retries клиента deduplicate по user/run/idempotency key.

Повтор execution после crash может дать тот же result; scoring принимает submission один раз. Старый run после rematch/technical result не изменяет current score/advancement. Timely submission сохраняет elapsed независимо от queue latency. Финализация ждёт её итог; длительная инфраструктурная ошибка видна admin и не превращается в поражение.

Ограничить очередь на user/match и частоту submit, но уже принятую посылку не удалять при overflow/crash. Статусы retry доступны автору. Admin не редактирует verdict напрямую вместо реальной проверки; technical result является отдельным аудируемым действием.

## Импорт из Яндекс Контеста

Это самостоятельная read/import интеграция после local package path. Проверить официальные методы, необходимые credentials, source host, формат Markdown/TeX/assets. Не выдумывать API endpoints и наличие скрытых тестов.

Imported statement связывается с local official tests/checker/limits. Если data неполные, задача NOT_READY и не назначается в матч. OAuth/read secrets серверные, не передаются worker/solution/browser. Отсутствие импорта не ломает уже работающий локальный judge.

Пробный запуск на собственном вводе возможен в варианте Б, но является дополнительной функцией. Если команда добавит его после обязательного MVP, использовать тот же sandbox, отдельный тип job, private output; trial run не изменяет official score/verdict.
