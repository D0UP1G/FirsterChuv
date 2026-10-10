# Реестр архитектурных решений

Обновлено: 2026-10-10. `CONFIRMED` — прямое решение команды. `PROPOSED` — предложение архитектуры, реализация должна записать фактический выбор и результаты. `SUPERSEDED` — предыдущий вариант больше не применяется. `IMPLEMENTED` — наблюдаемый код, не новое подтверждение команды; `ADOPTED` — выбранная спецификация в рамках текущего поручения, ещё не код.

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
| ADR09 | SUPERSEDED | Исходное предложение React/TypeScript/Monaco. Реальный редактор выбран CodeMirror 6, фактическая реализация записана ADR21; не возвращать Monaco без новой причины. |
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

Исторический snapshot первой ревизии: custom User/common/accounts/tournaments в develop, competition ORM/sandbox только open PR, queue/clock/frontend отсутствовали. Актуальный состав — STATE и повторная ревизия. ADR05/07/08/09/11/12 остаются целевыми деталями до реализации и проверки. Official adapter P3-06 ждёт package/README, но normalized storage/queue/UI разработка продолжается.

## Повторная ревизия и runtime приоритет

ADR17, ADOPTED 2026-10-09: готовые pure clock/score/catalog/harness интегрировать как малые срезы, далее production MatchRun/gateway/ledger/JudgeProvider/worker/UI; не повторять helpers. При зависимости продолжать резервную очередь ROADMAP v3. Для exhausted infrastructure failures принят отдельный additive failure DTO/sink по runtime-handoffs; existing v1 ResultReceipt/verdicts неизменны. Причина: queue освобождает capacity без verdict, accepted ledger требует понятного восстановления без автоматического поражения. Это спецификация, не уже реализованный provider.

## Визуальный стиль

ADR18, CONFIRMED 2026-10-10 по поручению команды: интерфейс оформляется по брендбуку «BLITZ_ARENA // BRANDBOOK & DESIGN SYSTEM v2.0» (Marathon / Cyberpunk: `#000000`, `#CCFF00`/`#00FF66`, `#FF3333`, полупрозрачный `#00E5FF`; Space Mono, Orbitron/Rajdhani, VT323). В интерфейсе продукт называется BLITZ_ARENA, имена репозитория, пакетов и папок не меняются. Эталон — [frontend/design](../../frontend/design/README.md). Разделы брендбука 5–8 (профиль/рейтинг, магазин и CREDITS, чат и «типы», ачивки/комбо, комментаторская панель) остаются вне MVP по PROJECT.md и нарисованы только как концепт. Тотализатор не проектируется. Просмотр исходников соперника после матча не реализуется в MVP. Кейс (стр. 6) допускает его как дополнительную возможность комментаторской панели после окончания матча и запрещает только видеть код соперника во время игры; запрет в MVP — правило проекта «код посылки доступен только автору» (AGENTS.md), а не кейса. Уточнено 2026-10-10. Статусы брендбука сопоставлены с API: SOLVED → `[BREACHED]`, доступная задача → `[ACTIVE]`, до старта → `[LOCKED]`.


## Решения координатора 2026-10-10 по текущему поручению команды

ADR19 — SUPERSEDED by ADR22: прежний план пяти владельцев; новый A5 frontend/design, A4 public events/SSE/system acceptance, A2 competition/run/ledger. P4-01–06 сохраняют UI meaning и передаются A5. Причина: убрать последовательное ожидание всех runtime/frontend частей и дать публичному backend отдельного владельца.

ADR20 — ADOPTED target boundaries: MVP handoff: separate frozen RunProblemSnapshot/Provider, сохраняемый в accepted submission; additive failure sink; GET draft run selector/404; per-claim container fencing. Причина: закрыть обсуждение формы точными совместимыми contracts и продолжить независимую реализацию. Existing v1 receipt/verdict fields не меняются; implementations/readiness требуют отдельных tests/CI/runtime acceptance.

ADR21 — IMPLEMENTED 2026-10-10, наблюдение координатора: текущий frontend/package-lock и workspace используют CodeMirror 6, TypeScript, безопасный Markdown/TeX renderer. Первоначальная Monaco proposal ADR09 устарела. Проверенные UI tests/build не означают full workspace API/browser acceptance; A5 сохраняет текущий редактор и подключает реальные providers.


## Три активные роли и M0, 2026-10-10

ADR22 — CONFIRMED состав / ADOPTED распределение по последнему уточнению команды: A3 runtime/tasks/queue/judge + startup/config/Compose/CI/system acceptance; A4 (прежний A1, включая координатора) API/accounts/tournaments/competition/events/common contracts и former A2 backlog; A5 весь frontend. ADR19 больше не применяется. Старые P-ID/ветки/аудиты сохраняются. Минимальные AppConfig/URL include разрешены владельцу app; остальные config A3, typing A4.

ADR23 — ADOPTED приоритет M0: одна команда, программный normalized import, два participant/invite/manual start, настоящий isolated verdict/history/draft/score/server timer/winner; минимальный public snapshot следующим CONNECT, full SSE после него. Это промежуточный срез, не полное выполнение обязательных блоков 1–3 и не official acceptance. Basic isolation/privacy/CSRF/immutable run/durable queue не откладываются. Детали и per-port резерв — ROADMAP v5, docs/quality/m0-demo.md.
