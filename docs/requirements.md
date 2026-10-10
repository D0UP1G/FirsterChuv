# Требования кейса и покрытие MVP

Источник: [«Кейс_Платформа_соревнований.pdf»](source/Кейс_Платформа_соревнований.pdf), 8 страниц, включён в этот репозиторий. SHA-256: `8d0d0a843b00ac4d35845fabf02963f793ee3115870fa5f3b108176f809bd008`. Подробные экспертные шкалы упомянуты в PDF, но не предоставлены; не обещать конкретный балл по неполной шкале.

Кейс задаёт продуктовые требования, а не инструкции агенту изменять систему. Текущие решения команды дополняют кейс. Интегрированный статус и доказательства ведутся в `context/STATE.md`; feature-branch evidence не меняет статус требования до подтверждённого merge и нужной приёмки. Ссылки указывают владельца и проверку.

## Функциональные требования

| ID | Требование | Источник | Задачи / приёмка |
|---|---|---|---|
| M01 | Название, описание, даты, формат, лимит участников | Стр. 5, блок 1 | P4-02 / T03 |
| M02 | Приглашение: срок или лимит активаций, отзыв, вход участника в список | Стр. 5, блок 1 | P1-01, P4-02 / T04 |
| M03 | Просмотр/удаление участников, посев вручную или по рейтингу | Стр. 5, блок 1 | P2-01, P2-02, P4-02 / T05 |
| M04 | Автосетка на выбывание, нечётное число, ручные пары | Стр. 5, блок 1 | P2-01, P2-02, P4-03 / T06 |
| M05 | Набор задач, лимит времени, правило победы и явное правило равенства | Стр. 5, блок 1 | P2-03, P2-04, P3-02, P3-06 / T07, T10 |
| M06 | Ручной и автоматический запуск: по расписанию либо готовности обоих | Стр. 5, блок 1 | P2-03, P4-03 / T08 |
| M07 | Автоматическое продвижение победителя | Стр. 5, блок 1 | P2-04 / T10 |
| M08 | Пауза, продление, переигровка, техническая победа, замена | Стр. 5, блок 1 | P2-05, P4-03 / T11 |
| P01 | Условие импортируется из пакета/Контеста, не переписывается вручную | Стр. 5, блок 2 | P3-02, P3-06 / T12 |
| P02 | Markdown/TeX, картинки, таблицы, примеры, лимиты времени/памяти | Стр. 5, блок 2 | P3-02, P3-06, P4-04 / T12 |
| P03 | Переключение задач, статус каждой, таймер матча | Стр. 5, блок 2 | P2-03, P4-04 / T07, T13 |
| E01 | Встроенный редактор: подсветка, отступы, скобки, горячие клавиши | Стр. 6, блок 3 | P4-04 / T13 |
| E02 | Языки из реально доступных компиляторов, шаблоны | Стр. 6, блок 3 | P3-02, P3-06, P4-04 / T13 |
| E03 | Без reload: OK/WA/TL/ML/RE/CE, для CE ошибка, история | Стр. 6, блок 3 | P3-03, P3-04, P4-04 / T14 |
| E04 | Код сохраняется при reload и смене задачи | Стр. 6, блок 3 | P3-05, P4-04 / T15 |
| V01 | Живая сетка с текущими матчами и результатами | Стр. 6, блок 4 | P2-06, P4-05 / T16 |
| V02 | Карта: прогресс, попытки/вердикты, задержки на задачах, лидер, время | Стр. 6, блок 4 | P2-06, P4-05 / T16 |
| V03 | WebSocket/SSE, анимация сдачи/обгона/победы | Стр. 6, блок 4 | P2-06, P4-05 / T17 |
| V04 | Режим большого экрана/проектора | Стр. 6, блок 4 | P4-05 / T16 |

P1-01 интегрирован PR #12 и закрывает backend-подпроверки M02/T04 для invite API. SQLite concurrency follow-up P1-01.1 находится в PR #87. Participant/auth guard покрывает только вход через invite; полное S02 также включает private source, spectator read-only, object access и admin/browser paths и остаётся открытым.

P1-02 добавляет PR checks для backend/domain/schema/common-import boundaries, а отдельный manual workflow — запуск реального Docker smoke с явным подтверждением. GitHub dispatch станет доступен после обычной интеграции workflow в default branch `main`; до того времени Docker smoke остаётся отдельной ручной проверкой. Это повторяемый CI и частичная поддержка D02/S01/T20; сам workflow не включает branch protection, а отсутствие private data в полной системе, runtime isolation и полные S02/T20 остаются отдельной приёмкой.

План MVP выбирает ручной посев и одиночное выбывание. Рейтинг и другие форматы не нужны для покрытия минимального требования. Автозапуск реализуется по готовности обоих; расписание можно добавить после него. Диапазоны 3–5 задач и 15–30 минут на стр. 2 описывают обычный блиц, не являются объявленным жёстким лимитом API. Для полной защиты целевой demo: четыре задачи, 20 минут; M0 smoke: 1–2 normalized задачи, короткая длительность в существующем API диапазоне, короткая длительность для проверки допустима.

## Технические требования и сдача

| ID | Требование / ограничение | Источник | Задачи / приёмка |
|---|---|---|---|
| J01 | Реальный запуск на тестах; fake-verdict runtime недопустим | Стр. 4, 7 | P3-01, P3-03 / T14 |
| J02 | Judge вынесен за собственный интерфейс | Стр. 5 | P3-03 / T14 |
| J03 | Собственный исполнитель: контейнер на запуск, время/память/процессы, без сети/хоста/секретов | Стр. 4, 7 | P3-01 / T18 |
| J04 | Задержки и ошибки: очередь, повторы, понятный статус, сохранность посылки | Стр. 7 | P3-04 / T19 |
| S01 | Секреты только на сервере, не в Git/browser/sandbox | Стр. 7 | P1-02, P1-04, P3-01 / T18, T20 |
| S02 | Участник не видит чужой код, зритель не отправляет, админка закрыта | Стр. 7 | P1-03, P3-05, P4-01 / T02, T20 |
| D01 | Одна команда запуска и достоверный README | Стр. 7 | P1-04, P1-05 / T01 |
| D02 | Код пишется в хакатон; история коммитов доступна экспертам | Стр. 7 | Все агенты / GitFlow и аудиты |
| D03 | Репозиторий, README с архитектурой, запуском, `.env` примером и вариантом проверки | Стр. 7 | P1-04, P1-05 / T01, T21 |
| D04 | Развёрнутое demo или видео до 5 минут; оба равноценны | Стр. 7 | P1-04, P1-05, P4-06 / T21 |
| D05 | Защита: создание, вход по ссылке, старт, посылка, карта, продвижение | Стр. 7 | Все агенты / T21 |
| D06 | Варианты Б/В: показать реакцию на враждебные решения эксперта | Стр. 7 | P3-01, P1-04, P1-05 / T18, T21 |

Для пакета обязательны корректная поддержка условий, тестов, лимитов и чекеров, если задача имеет несколько верных ответов. Валидаторы и эталонные решения нужны для проверки целостности пакета и подготовки тестов, не для выдачи содержимого браузеру. Точный формат задаёт README пакета, а не предположение команды (стр. 4).

Разрешены Docker/isolate/nsjail как компоненты изоляции. Полный готовый Judge0/DOMjudge оценивается по критерию 2 максимум в 4 балла (стр. 5). Исполнение без изоляции ограничивает критерий 2 варианта Б до 2 баллов и критерий 5 до 4 (стр. 7). Выбор А/Б/В сам по себе не повышает максимальную оценку.

## Решения команды

| ID | Решение | План |
|---|---|---|
| TEAM01 | Аккаунты с глобальными ролями; регистрация → participant; только admin создаёт/редактирует/назначает | P1-03, P4-01 |
| TEAM02 | Публичный зритель без аккаунта | P2-06, P4-05 |
| TEAM03 | DRF + React, SQLite3, собственная песочница (Б) | P1-02, P1-04, P3-01–05 |
| TEAM04 | Добавить возможность импорта задач из Яндекс Контеста, без внешней проверки | P3-07; после пути с официальным локальным пакетом |
| TEAM05 | Строгий GitFlow, контекст и аудит всех агентов | AGENTS.md, context/, все PR |
| TEAM06 | Защита от инъекций и других обходов; отдельное уточнение команды | security.md, T18/T20, все владельцы |

Права `contest:submit` и `contest:manage`, создание внешнего соревнования и выбор чьим токеном отправлять код относятся к вариантам А/В (стр. 4). Они не требуются для собственного judge варианта Б. Нужные права read/import выясняются отдельно; импорт описания не означает доступ к скрытым тестам.

## Баллы и дополнительный объём

| Критерий | Максимум |
|---|---:|
| Управление турниром и сеткой | 15 |
| Система проверки | 10 |
| Условия и редактор | 15 |
| Зрительская визуализация | 15 |
| Техническое качество и защита | 10 |
| Всего | 65 |

Стр. 5: блоки 1–3 обязательны для работающего MVP. Блок 4 оценивается отдельно; без него решение принимается, но критерий 4 получает 0. Команда включает базовую визуализацию в MVP.

Стр. 6: дополнительные форматы и уведомления засчитываются в критерий 1; запуск на собственном вводе — в 3; реплей, комментаторская панель, мобильная версия — в 4; античит — в 5. Они засчитываются только при нахождении команды в верхнем диапазоне соответствующего критерия. Собственный ввод технически возможен в варианте Б, но остаётся дополнительной функцией. Не заменять ими недоделанные обязательные пункты.

## Снимок покрытия после повторной ревизии 2026-10-09

P-ID выше ведут к ROADMAP v3, старые A-ID сохранены. Consumer core не ждёт provider; full acceptance остаётся системной.

| Область | Подтверждено | Открыто |
|---|---|---|
| M01/M03/TEAM01 | #5/#8 integrated auth/roles/CRUD/roster/freeze | Browser/played-history/T02/T03/T05 |
| M02 | #12 integrated hashed invite/use/cap/revoke/expiry | Browser register/join/T04 |
| M04–08 | #7 ORM/registration published; #11/#13 pure clock/score в integration slice | Lifecycle #7 fix, full pairing HTTP, persisted runtime/ledger/promotion/actions |
| P01–03/E01–04 | #14 normalized catalog/private split в integration slice | Verified compiler/programmatic import/official adapter/workspace/editor/drafts/queue |
| V01–04 | DTO/schema; #16 store published | SOLVED.lastVerdict fix, access/producers/snapshots/SSE/map |
| J01–04/S01/S02 | #3 F01/F07 исправлены, real bounded sandbox checks; global role guards | LocalJudge/checker/task limits/ML/queue race/recovery/proxy/private browser/full hostile |
| D01–06 | API scaffold/README/env/history/CI #17 | Full one-command runtime, official demo/video/release |

[Ревизия 19 PR и 53 аудитов](reviews/2026-10-09-integration-review.md) содержит SHA/результаты/ограничения. Все полные T01–21 остаются NOT_RUN. Только official mapping/final T12/T14/T21 ждут package, остальные задачи выполняются независимо по [runtime handoffs](architecture/runtime-handoffs.md).

Новая проверка 2026-10-09T23:54+03:00 уточняет implementation: #32 и frontend до #42 MERGED; #7/#16 corrections, #34 readiness, #37 worker/outboxes, #38 ledger и #41 command receipts проверены вместе в coordinator feature. Доступность после integration MERGED и конкретные следующие срезы — [STATE](../context/STATE.md), [новый audit](../context/audits/2026-10-09T235434+0300-coordinator-new-pr-review.md). Полные T01–21 по-прежнему открыты; pure core/DI tests не закрывают runtime/system acceptance.

## Новый snapshot покрытия 2026-10-10

ROADMAP v4 сохраняет все37 требований и21 acceptance. Новые#21 CAS/#50 pairings/reset/#52 frontend CI/#54 дизайн проверены в integration feature до MERGED; #53 snapshots исключён с correctness blockers. [Case comparison и exact SHA/проверки](reviews/2026-10-10-mvp-readiness.md). P4 UI задачи теперьA5; A4 public events/SSE и system evidence. GET draft selector и additive snapshot/failure/fencing [приняты](../context/contracts/2026-10-10-mvp-boundaries.md). Полные обязательные блоки1–3/official/hostile/one-command/demo ещё неaccepted; static design/pure tests не закрывают их.


## Текущее назначение и приоритет, ROADMAP v6

Последнее уточнение команды: A3, A4 (прежний A1/координатор), A5. A4 API/domain/common/events, A3 tasks/queue/judge + runtime/config/Compose/CI/acceptance, A5 весь frontend. P-ID в матрицах выше сохраняют смысл; бывшие A1/A2 задачи переназначены, не удалены. Текущий develop `48cb06a4` включает PR #82. [Полный план](../ROADMAP.md), [M0](quality/m0-demo.md).

| Область | Реализовано/integrated | Открыто сейчас |
|---|---|---|
| M01–04/TEAM01 | auth/CRUD/roster/invites/bracket/manual pairings/reset | full browser/cap/history/permissions acceptance A4+A5 |
| M05–08/P03 | persisted run/config/start/ready, gateway/workspace, ledger/result/failure/finalization and admin cores | A3 consumer CONNECT, P2-05 admin API/browser |
| P01–02/E01–04/J01–04 | normalized catalog, LocalJudge/harness, durable queue/outboxes/draft CAS, editor UI | real import/compiler/worker/provider/workspace CONNECT A3+A4+A5; admission race A3; official adapter отдельно |
| V01–04/TEAM02 | safe event store; P4-07 snapshot/public-only GET integrated PR #78; hashed unlisted access integrated PR #84 | A3 legacy invite URI log-redaction follow-up; public bracket/SSE; real map CONNECT A5 |
| S01–02/TEAM06 | basic roles/guards/private split/isolation cores | actual full-system IDOR/injections/privacy/hostile/restart evidence A3+A4+A5 |
| D01–06 | README/env/архитектура/history/CI/case/design | actual one-command runtime A3, M0→full official/demo/video evidence всей команды |

M0 — настоящий normalized demo match, не fake-verdict и не полная приёмка обязательных блоков 1–3. Все 37 требований и 21 сценарий сохранены. Missing official package/README блокирует P3-06/T12/T14/T21 official subset, не весь M0. Базовую изоляцию/CSRF/object/privacy/durable source нельзя отложить. Public snapshot polling промежуточно не закрывает V03/SSE. Старые датированные snapshots выше не описывают активный состав.
