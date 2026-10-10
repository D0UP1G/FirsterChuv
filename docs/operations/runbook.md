# Целевой запуск, восстановление и защита MVP

Текущий приоритет ROADMAP: A3/A4/A5 и [первый матч M0](../quality/m0-demo.md). P1-04.2 добавляет запуск Compose одной командой, но сборка и полный стек на Docker Engine ещё не проверены. PR с worker factory и программным demo import/compiler probe остаются зависимостями; до их интеграции запуск judge-worker не означает готовую проверку посылок. Для M0 нужны два participant и normalized programmatic tasks; полная защита с полуфиналом→финалом/official tasks остаётся следующим этапом.

Полный demo и T01 не приняты. Compose запускает `api`, `web`, `match-clock` и `judge-worker` без профилей; web/worker/clock зависят от API health. API entrypoint применяет миграции. `match-clock` команда уже присутствует в актуальном backend. Worker требует production factory и реальные execution/result/failure providers; без них он должен штатно отказывать закрыто. Не сообщать, что MVP или demo уже запускаются, пока не получено evidence полного сценария.

## Одна команда запуска

На Linux с Docker Engine и Compose plugin подготовьте локальный `.env` и запустите `./scripts/start-demo.sh`. Скрипт проверяет `.env`, доступность Engine и Compose, определяет GID Docker socket, собирает закреплённый локальный sandbox image `firsterchuv/sandbox-cpp:0.1.0`, затем выполняет `docker compose up --build`. Compose ждёт API health перед запуском web/worker/clock; API entrypoint отвечает за миграции. Данные SQLite хранятся в named volume `app-data`, штатный запуск volume не удаляет. Проверка скрипта синтаксисом выполнена, но Docker Engine/socket и Compose plugin в среде автора отсутствуют: image build, `compose up`, health и сквозной матч имеют статус NOT_RUN.

Первичная настройка: `cp .env.example .env`, затем замените `DJANGO_SECRET_KEY=replace-before-sharing` приватным случайным значением в локальном файле. Не коммитьте `.env` и не вставляйте ключ в терминальные команды или аудит. Скрипт отклоняет отсутствующий `.env` и незаменённый placeholder. Запуск требует Linux `/var/run/docker.sock`; Compose получает его только `judge-worker`. Для worker дополнительно задаётся GID этого socket, вычисленный скриптом. API, web и clock socket не монтируют. Доступ worker к Engine — доверенная административная граница: worker image и конфигурацию следует считать trusted; недоверенный solution выполняется только в sandbox с отдельными ограничениями.

Ожидаемые локальные адреса: web `http://localhost:8080`, API `http://localhost:8000`. Это не production deployment и не доказательство приемки. До появления factory/providers worker не подтверждает verdict; demo import/compiler probe остаются отдельными требованиями. Официальный пакет организаторов этой командой не загружается и для старта Compose не требуется.

Необходимые условия: Linux, Docker Engine/Compose, доступ текущего пользователя к Docker socket, достаточные CPU/RAM/disk под собственную песочницу и persistent volume для SQLite. Во время проверки solution network off; trusted startup может получать разрешённые images. Если для Engine нужны системные права, настройку выполняет оператор отдельно; приложение не должно ослаблять права host.

Публичный TLS ingress в репозитории не настроен. До внешней публикации reverse proxy должен завершать HTTPS и задавать redirect/HSTS; пока эти два инфраструктурных параметра не определены, `manage.py check --deploy` ожидаемо сообщает W004/W008. Compose API и web ports по умолчанию привязаны к localhost.

`.env.example` должен содержать только реально используемые ключи без секретных значений. Минимальные группы настроек: Django secret/hosts/origins, SQLite path, admin bootstrap identity/password из защищённой конфигурации, official package path, compiler registry, execution/resource caps и request/queue limits. Yandex read credentials отдельны и нужны только import feature, не local checking.

Передавать service-specific env: API не получает Docker socket; worker не получает OAuth/password/Django secret; sandbox не получает env ни одного из них. Сейчас `.env` передаётся только API; не применять весь `.env` к остальным контейнерам.

## Первоначальные данные

Первый application admin создаётся командой `./scripts/manage.sh create_admin --email admin@example.org --display-name "Tournament Admin"`. В интерактивном terminal пароль запрашивается скрыто дважды. Для automation передайте `DJANGO_ADMIN_PASSWORD` через secret manager/защищённую конфигурацию только этого процесса; не помещайте пароль в аргумент команды, inline shell command, общий `.env`, Compose env API, Git или логи. Значение читается и удаляется из окружения процесса команды. Если нет ни secret injection, ни TTY, команда завершится ошибкой.

Команда проверяет настроенные Django password validators. При повторном запуске для уже активного application admin она оставляет аккаунт и пароль без изменений; существующий participant не повышается, неактивный admin автоматически не включается. Созданный application admin имеет `role=admin`, но `is_staff=False` и `is_superuser=False`; Django superuser не требуется для продуктовых admin endpoints. Для изменения роли или состояния используйте отдельную контролируемую процедуру, не bootstrap повторный запуск. Никаких стандартных общедоступных admin/admin. Официальный пакет импортируется программно, checksum/format/readiness фиксируются.

Для demo нужны четыре participant: два новых присоединяются по ссылке, ещё два могут быть назначены заранее. Admin строит полуфиналы/финал. Для быстрой проверки поставить небольшую duration, для показательного матча — 20 минут. Не выдавать smoke fixtures собственного автора за единый пакет организаторов.

## Health и readiness

- API health проверяет доступность приложения/DB без полного settings dump.
- Worker readiness подтверждает DB claim path, compiler images и безопасные sandbox settings; engine available недостаточно без настроенных limits.
- Public page/SSE обслуживаются proxy одним origin; buffering SSE выключен.
- При отказе execution API сохраняет accepted submission и показывает retry/infrastructure status. Не включать direct execution fallback.

## Сбой и восстановление

| Ситуация | Действие / ожидаемый результат |
|---|---|
| Worker restart в RUNNING | Найти свои stale containers по job labels, завершить, восстановить expired lease и retry; source сохранён, score один раз |
| Docker unavailable | Новые jobs ждут/retry с понятным статусом; нет RE/fake OK и host execution |
| SQLite locked | Short bounded retry; не держать external calls в transaction; source уже сохранён после 202 |
| API restart | Состояние/clock/run queue из DB, frontend восстанавливается snapshot |
| SSE disconnect | Heartbeat/reconnect и events after cursor/resync; leader/score не откатываются |
| Timeout с unfinished jobs | FINALIZING ждёт timely submissions; admin видит задержку |
| Wrong package/checker | Import/проблема NOT_READY либо infrastructure error, не ложный WA |
| Disk pressure/output flood | Bounded artifacts/output, только собственный cleanup, accepted source не удаляется |

Не выполнять глобальный Docker prune, reset DB, force push или очистку чужих containers как часть штатного восстановления. SQLite backup должен включать согласованное состояние DB/WAL через штатный backup или остановку writers. Retention/data purge описывается отдельно после защиты.

## Защита и видео ≤5 минут

1. Показать repo/README/одну команду, выбранный вариант Б и общую архитектуру.
2. Admin создаёт турнир, импортирует/привязывает official задачи, формирует invite.
3. Два participant в отдельных browser sessions регистрируются и принимают invite; показать автоматическую participant роль.
4. Admin назначает оставшихся, строит bracket и запускает полуфинал. Участник отправляет реальное решение, получает verdict без reload.
5. Anonymous spectator видит изменение task/score/map; матч заканчивается и winner попадает в финальный слот.
6. Коротко показать hostile code в sandbox, его bounded прекращение/отсутствие сети и следующий нормальный job. Никакого выполнения опасного кода на host.

Сначала прорепетировать полностью, потом записать backup video. Live demo и видео равноценны по кейсу; для собственного sandbox поведение на предложенных экспертом враждебных решениях остаётся частью защиты. Проверить доступность опубликованной ссылки с новой anonymous session. Технические ошибки честно показывать, не заменять их mock verdict.

## Подключения без ожидания всей платформы

Инфраструктурная очередь P1-04 и per-module CONNECT описаны в ROADMAP v3. Готовая app включается коротким PR, затем проверяется один endpoint/worker command. Отсутствующий provider не выбирает mock и не делает start/submit успешным; readiness/integration error видна. Official package нужен для финальной T12/T14/T21, не для CI/UI/queue-core разработки. Sandbox #3 6950f10 исправил F01/F07, повторная ревизия подтвердила real execution/cleanup; LocalJudge/task limits/official acceptance ещё не готовы.

Повторная ревизия: [actual runtime/checks](../reviews/2026-10-09-integration-review.md). Перед smoke заново собрать `docker build --platform=linux/amd64 --tag firsterchuv/sandbox-cpp:0.1.0 sandbox`, затем `uv run --locked python sandbox/smoke.py --case all`; проверено в integration feature. Старый локальный tag до F07 fix не подтверждает новый runner. `frontend/Dockerfile` собирает web image, но полный worker/clock/web startup остаётся целью P1-04 и пока не проверен как runnable stack.
