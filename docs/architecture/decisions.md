# Реестр архитектурных решений

Обновлено: 2026-10-09. `CONFIRMED` — прямое решение команды. `PROPOSED` — предложение архитектуры, реализация должна записать фактический выбор и результаты. `SUPERSEDED` — предыдущий вариант больше не применяется. `IMPLEMENTED` — наблюдаемый код, не новое подтверждение команды; `ADOPTED` — выбранная спецификация в рамках текущего поручения, ещё не код.

| ID | Статус | Решение и основание |
|---|---|---|
| ADR01 | CONFIRMED | Глобальные `participant`/`admin`; регистрация всегда participant. Зритель без аккаунта. Команда изменила предыдущую модель. |
| ADR02 | CONFIRMED | Строгий GitFlow: main/develop/feature/release/hotfix, аудит каждого агента. |
| ADR03 | CONFIRMED | Django REST Framework + React, SQLite3. Выбрано командой 2026-10-09. |
| ADR04 | CONFIRMED | Официальная проверка собственным sandbox, вариант Б кейса. Яндекс Контест — только импорт задач. |
| ADR05 | PROPOSED | Один Django-проект с доменными apps; frontend отдельно; отдельный trusted judge-worker и одноразовые Docker sandbox. |
| ADR06 | IMPLEMENTED | Session auth/CSRF и management command admin интегрированы PR #5; один origin proxy остаётся целью, не full browser acceptance. |
| ADR07 | PROPOSED | Durable queue в SQLite, один judge-worker, один узел, WAL/timeout и атомарные обновления. Redis/Celery не требуются для MVP. |
| ADR08 | PROPOSED | SSE + snapshots/events для публичных обновлений; собственный безопасный DTO, без private source. |
| ADR09 | PROPOSED | React + TypeScript, Monaco, безопасный Markdown и TeX-renderer. Конкретные библиотеки/версии фиксировать lockfiles при bootstrap. |
| ADR10 | PROPOSED | Admin глобально управляет всеми турнирами. Участие admin в матчах выключено; роль participant играет, публичный просмотр открыт всем. |
| ADR11 | PROPOSED | Solved ↓, penalty ↑, last accepted active time ↑, окончательное равенство → rematch. Параметры публикуются до старта и замораживаются для run. |
| ADR12 | PROPOSED | Условия/тесты/checkers из официального пакета — основной import. Импорт Яндекс описаний/метаданных связывается с этим пакетом; source-only задачи не готовы для матча. |
| ADR13 | SUPERSEDED | Роли только внутри турнира без глобальной роли аккаунта. Отменено командой. |
| ADR14 | SUPERSEDED | FastAPI/PostgreSQL и проверка через Яндекс API. Команда выбрала DRF/SQLite и собственную песочницу. |
| ADR15 | IMPLEMENTED | Tournament API ограничивает формат single elimination, cap минимумом 2 и match duration диапазоном 60–7200 секунд; duration default — 1200 секунд. API guard интегрирован PR #8; обычный диапазон кейса 15–30 минут не является верхним/нижним системным лимитом. |

## Последствия подтверждённых решений

SQLite задаёт границу MVP: один сервер, локальный persistent volume и один проверяющий worker. Не рассчитывать на row locks/`select_for_update` как в PostgreSQL. Критичные переходы защищаются короткой транзакцией, conditional update и уникальными ограничениями. При росте нагрузки смену базы обсуждают отдельно; не менять стек команды молча.

Собственная песочница требует реальной проверки враждебными решениями, готовности Docker-хоста, безопасной компиляции и запуска, обработки official checker. Наличие Docker само по себе не подтверждает изоляцию. Исполнитель нельзя заменить полным сторонним judge-продуктом.

Регистрация не должна менять роль по входным данным. Application admin не равен Django `is_superuser`; права выдаются и проверяются явно.

При изменении решения добавить дату, автора, причину, новый статус и влияние на требования, API, данные и задачи. Сохранить запись старого решения, чтобы следующий агент не восстановил устаревшую архитектуру.

## Ревизия параллельной работы, 2026-10-09

ADR16, **ADOPTED**: по поручению команды ROADMAP v2 даёт READY очередь, малый implementation PR, отдельный CONNECT/full acceptance. Совместимые consumers пишутся по [parallel-contracts v1](parallel-contracts.md), test/dev fixtures не используются runtime. Причина: PR #7 ждал уже merged A1-03, STATE sync становился prerequisite. Владельцам apps разрешены минимальные AppConfig/URL additions вместе с кодом; common typing interfaces расширяются короткими P1-02 срезами; порт не означает готовый provider.

Наблюдаемый код: custom User/common/accounts/tournaments в develop, competition ORM/sandbox только open PR, queue/clock/frontend отсутствуют. ADR05/07/08/09/11/12 остаются целевыми деталями до реализации и проверки. Official adapter P3-06 ждёт package/README, но normalized storage/queue/UI разработка продолжается.
