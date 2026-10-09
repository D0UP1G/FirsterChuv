# Целевой запуск, восстановление и защита MVP

Полный demo и команда `./scripts/start-demo.sh` ещё не реализованы. На feature-ветке Agent 1 прошли ограниченные проверки Django/миграций, `scripts/dev.sh`, сборки API image и Compose health после запуска/перезапуска; полная приёмка чистой установки и T01 не выполнялись. В backend есть начальный каркас и локальные dev helpers; Compose содержит API scaffold, opt-in web и незавершённые runtime profiles. `match-clock` и `judge-worker` станут запускаемыми после реализации команд агентами 2 и 3. Не сообщать, что MVP или demo уже запускаются.

## Одна команда запуска

После одноразового заполнения `.env` и предоставления official package целевая команда — `./scripts/start-demo.sh`. Будущий script должен собрать/подготовить compiler images, дождаться SQLite/API/worker readiness, применить миграции один раз и запустить web/API/match-clock/judge-worker через Docker Compose. Не удалять volumes и не сбрасывать историю при обычном restart.

Необходимые условия: Docker Engine/Compose, достаточные CPU/RAM/disk под собственную песочницу, один local persistent volume для SQLite и private package storage. Во время проверки solution network off; trusted startup может получать разрешённые images. Если нужны system permissions/Docker group, это отдельная настройка оператора, не обход изоляции.

Публичный TLS ingress в репозитории не настроен. До внешней публикации reverse proxy должен завершать HTTPS и задавать redirect/HSTS; пока эти два инфраструктурных параметра не определены, `manage.py check --deploy` ожидаемо сообщает W004/W008. Compose API и web ports по умолчанию привязаны к localhost.

`.env.example` должен содержать только реально используемые ключи без секретных значений. Минимальные группы настроек: Django secret/hosts/origins, SQLite path, admin bootstrap identity/password из защищённой конфигурации, official package path, compiler registry, execution/resource caps и request/queue limits. Yandex read credentials отдельны и нужны только import feature, не local checking.

Передавать service-specific env: API не получает Docker socket; worker не получает OAuth/password/Django secret без необходимости; sandbox не получает env ни одного из них. Не применять весь `.env` к каждому контейнеру.

## Первоначальные данные

Первый admin создаётся защищённой management command; никаких стандартных общедоступных admin/admin. Идемпотентный bootstrap не меняет пароль существующего пользователя при каждом restart. Официальный пакет импортируется программно, checksum/format/readiness фиксируются.

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
