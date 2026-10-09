# Очередь посылок

Приложение `submissions` хранит приватный исходный код, idempotency, leases очереди и durable outbox результата. Исходник возвращается только через авторскую проверку UUID пользователя; принятые события, открытые DTO и список попыток не содержат исходник, его hash, CE-диагностику или секретные материалы.

## Приём

`SubmissionService` требует реальные `CompetitionGatewayV1`, `EventWriter` и `LanguageRegistry`. При отсутствии хотя бы одного порта приём закрыт с `IntegrationUnavailable`; нет разрешения по умолчанию, тестового runtime adapter или фиктивного вердикта. Фабрика подключается через `SUBMISSION_SERVICE_FACTORY` только после готовности production adapters.

`POST /api/v1/matches/{matchId}/submissions` принимает только `runId`, `problemId`, `languageId`, `source` и обязательный `Idempotency-Key`. Успех возвращает `202` после короткой SQLite-транзакции: лимиты очереди → проверка матча/run/задачи → source/submission → accepted ledger → allowlisted event → commit. Порты выполняются в том же процессе и транзакции, сетевые callbacks не подходят. `received_at` берётся с сервера. Тот же ключ и тело возвращают ту же посылку; другое тело даёт `409`.

Исходник ограничен 32 KiB UTF-8. Условные SQL-обновления ограничивают общее число ожидающих посылок, число на автора и число на матч; лимиты по умолчанию — 1000, 10 и 20 (два участника MVP × 10). HTTP submit дополнительно ограничен 30 запросами в минуту на автора/матч. Throttle использует настроенный Django cache; для нескольких API-процессов нужен общий cache, а proxy/network rate limit остаётся отдельной задачей P1-03. Переполнение не удаляет уже принятые посылки.

SQLite `BUSY`/`LOCKED` при admission откатывает всю короткую транзакцию и повторяет её не более двух раз после первой попытки, сохраняя исходный серверный `received_at`. После исчерпания попыток API возвращает retryable `503 queue_busy`; клиент повторяет запрос с тем же `Idempotency-Key`. Другие `OperationalError` не маскируются и не повторяются.

Race/rollback тесты нужно запускать на файловой SQLite: `DJANGO_DEBUG=true SQLITE_TEST_PATH=/tmp/submissions-tests.sqlite3 uv run --locked python manage.py test backend.apps.submissions.tests --settings=backend.apps.submissions.test_settings`. Путь можно задать через `SQLITE_TEST_PATH`; test database удаляется Django после завершения тестов.

## Worker и восстановление

Доверенный worker забирает FIFO-посылку условным переходом состояния, без надежды на row locks SQLite. Claim имеет уникальный lease token и ограниченный срок; worker продлевает его heartbeat-потоком без долгой DB-транзакции. Просроченная работа повторяется с экспоненциальной задержкой; после пяти попыток переходит в `INFRA_FAILED` без verdict. Старый worker не может завершить новый claim. `received_at` и elapsed остаются неизменными после повторов.

В `FINISHED` допускаются только `OK/WA/TL/ML/RE/CE`. Инфраструктурные ошибки идут отдельным retry-путём и не превращаются в RE/WA. Завершение атомарно сохраняет приватную CE-диагностику/метрики и `ResultOutbox`. Outbox повторяет `ResultSink` receipt; после сбоя между commit A2 и отметкой доставки receipt может прийти повторно, поэтому sink обязан дедуплицировать по `submission_id`.

`run_judge_worker` обрабатывает одну единицу за цикл: сначала due outbox, затем FIFO claim. Команда восстанавливает просроченные leases очереди и outbox и переживает перезапуск через сохранённые статусы. Если heartbeat не может подтвердить lease, результат всё равно проходит финальную проверку токена и срока; устаревший worker не сохранит вердикт. `--once` выполняет не более одного цикла, `--max-jobs N` завершает процесс после N обработанных элементов, а `--idle-sleep` задаёт паузу пустой очереди. У `--lease-seconds` допустим диапазон `1..900`, значение по умолчанию — 60.

Runtime worker создаётся только через `SUBMISSION_WORKER_FACTORY`, возвращающий `SubmissionWorker` с реальным `SubmissionService`, исполнителем и `ResultSink`. Без этой настройки management command завершается `CommandError`; фиктивные providers не подключаются. Executor должен разрешать только immutable version/checksum исходного run, прежде чем создать `TrustedJudgeJob`; этот snapshot handoff и production adapters выполняются следующими подпунктами P3-04.3–4, поэтому текущий PR не объявляет runtime execution подключённым. Executor обязан сообщать ожидаемые инфраструктурные сбои через `JudgeInfrastructureError`; неожиданные ошибки останавливают процесс безопасным общим сообщением, а claim восстанавливается после lease. Исходный код и диагностики worker не пишет в stdout/stderr.

## API и подключение

- `GET /api/v1/matches/{matchId}/submissions` — только свои метаданные и verdict, с ограниченной пагинацией; можно фильтровать по `problemId`.
- `GET /api/v1/submissions/{submissionId}` — своя попытка и ограниченная CE-диагностика.
- `GET /api/v1/submissions/{submissionId}/source` — только собственный исходник.

Private ответы имеют `Cache-Control: no-store` и `Referrer-Policy: no-referrer`. Admin не получает исходник другого участника. В текущем `develop` production-порты и `SUBMISSION_SERVICE_FACTORY` ещё не подключены: POST отвечает `503 integration_unavailable` до их реализации. Тестовые адаптеры существуют только в тестах; исполняемый worker с настоящим `JudgeProvider` и запуском кода реализуется после P3-03 и готовности ProblemCatalog. Queue core сам не запускает participant code.
