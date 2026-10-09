# BLITZ_ARENA: макеты и разметка для подключения

Статичный макет дизайна по брендбуку «BLITZ_ARENA // BRANDBOOK & DESIGN SYSTEM v2.0». Здесь нет логики, запросов и React-кода: это эталон внешнего вида и HTML-структуры для агента, который переносит стиль в `frontend/src`. Данные на экранах демонстрационные: имена, счёт и время показывают состояние, а не реальный ответ API. Квадратные скобки `[…]` отмечают содержимое, которое приходит только из пакета задач или от сервера.

Интерактивный холст со всеми экранами, включая концепты вне MVP: <https://claude.ai/artifact/JHRzq9qFwzXTwQtpAFqkk9> (приватный, доступ выдаёт владелец через Share).

## Состав

| Файл | Назначение |
|---|---|
| `blitz.css` | Токены брендбука (`--ba-*`) и все компоненты. Имена классов совпадают с текущими React-компонентами; новые брендовые элементы имеют префикс `ba-` |
| `screens/*.html` | По одной странице на экран MVP, открываются в браузере напрямую |

Открыть: любой `screens/*.html` в браузере, сборка не нужна. Vite эту папку не собирает.

## Брендбук → токены

| Брендбук | Токен | Где используется |
|---|---|---|
| Primary Void `#000000` | `--ba-void` | Фон всех экранов, редактор, «колодцы» внутри карточек |
| Toxic Acid `#CCFF00` | `--ba-acid` | Активные элементы, основная кнопка, границы выбранного, акцент заголовков, таймер |
| Toxic Acid `#00FF66` | `--ba-acid-ok` | Успех: `[BREACHED]`, `[OK]`, победитель, LIVE |
| Alarm Red `#FF3333` | `--ba-alarm` | `[WA] [TL] [ML] [RE] [CE]`, `[LOCKED]`, критический таймер (меньше 60 с), опасные действия |
| Tech Grid `#00E5FF` | `--ba-grid*` | Полупрозрачные подложки карточек и полей, линии каркаса, тех-сетка 24 px внутри карточек |
| Space Mono | `--ba-font-base` | Основной текст |
| Orbitron / Rajdhani | `--ba-font-display` / `--ba-font-ui` | Заголовки / кнопки, вкладки, подписи полей |
| VT323 | `--ba-font-terminal` | Код, логи, лента событий, таймеры, счёт |

Шрифты Google Fonts (подключение есть в `<head>` каждой страницы):
`https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;800;900&family=Rajdhani:wght@500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&family=VT323&display=swap`.

Брендбук не задаёт цвет основного текста. Взят светлый оттенок Tech Grid `--ba-text: #e6fbff` и приглушённые `--ba-text-muted` / `--ba-text-dim` с контрастом не ниже 4.5:1 на чёрном. Углы прямые (`--ba-radius: 0`); угловые засечки терминала — класс `ba-frame`.

### Отступы текста

Расстояние зависит от смысла пары соседних элементов (раздел 3a `blitz.css`), шаги — токены `--ba-space-*`:

| Пара | Отступ |
|---|---|
| Подпись (`ba-kicker`, `card-kicker`, `ba-state-label`) → заголовок или значение | 4 px |
| Надзаголовок `eyebrow` → заголовок страницы | 8 px |
| Заголовок → текст | 8 px (лид `page-lede` — 12 px) |
| Абзац → абзац, список | 12 px |
| Текст → новый подзаголовок | 24 px |
| Текст → кнопки (`ba-actions`, `form-actions`) | 24 px |
| Блок → блок внутри карточки (`ba-stack`, карточки состояний) | 24 px, плотная группа `ba-stack-tight` — 16 px |
| Секция → секция | 48 px |

Межстрочный интервал: заголовки 1.1–1.3, текст 1.6. Длина строки абзаца — не больше 68 символов.

Группировка в разметке: `ba-head` — подпись и статус над карточкой (8 px), `ba-copy` — связанный текст, отступы внутри по правилам ритма, `ba-actions` — ряд кнопок. Правила ритма записаны в `:where()` с нулевой специфичностью, поэтому отступ компонента всегда главнее. Инлайновые `margin` не использовать: нужен отдельный отступ — класс `ba-mt-1`…`ba-mt-7` из той же шкалы.

### Тех-сетка

Фон страницы — чистый `#000000` без сетки. Сетка (`--ba-grid-pattern`, шаг `--ba-grid-step: 24px`) рисуется только внутри элементов, раздел 15 `blitz.css`:

- **есть:** карточки и панели (`ba-panel`, `management-panel`, `workspace-panel`, `auth-card`, `dashboard-card`, `invite-preview-card`, `tournament-card`, `spectator-match-card`, `empty-state`, `success-panel`, `workspace-conflict`), условие задачи `workspace-statement-panel`, колонка сетки турнира `spectator-bracket`, сцена проектора `spectator-page-projector`; для нового блока — класс `ba-grid`;
- **нет:** фон страницы, шапка, подвал, поля ввода, кнопки, теги, редактор кода, баннеры и строки состояния, внутренние чёрные блоки (примеры, ячейки задач, строки таблиц).

Правило сетки стоит в конце файла. Цвет подложки компонентам задавать через `background-color`: shorthand `background` в инлайновом стиле сотрёт сетку.

## Статусы: брендбук ↔ API

| Вид | Класс | Источник |
|---|---|---|
| `[BREACHED]` | `ba-tag ba-tag-breached` | task `status = SOLVED` |
| `[ACTIVE]` | `ba-tag ba-tag-active` | `NOT_STARTED` / `ATTEMPTED` после старта; задачи решаются в любом порядке |
| `[LOCKED]` | `ba-tag ba-tag-locked` | Только до старта матча, пока условия закрыты |
| `[OK]` / `[WA] [TL] [ML] [RE] [CE]` | `ba-tag-ok`, `ba-tag-wa` … `ba-tag-ce` | `verdict` |
| `[QUEUED]` `[RUNNING]` | `ba-tag-queued`, `ba-tag-running` | `submission.status` |
| `[СБОЙ ПРОВЕРКИ]` | `ba-tag-infra` | `INFRA_FAILED`: не ошибка участника, не красный |
| Статус матча | `ba-tag-live` / `-active` / `-neutral` / `-queued` / `-ok` / `-warn` | `RUNNING` / `READY` / `WAITING`, `PAUSED` / `FINALIZING` / `FINISHED` / `TIED` |

Скобки рисует CSS (`::before`/`::after`), в разметке остаётся чистое значение (`<span class="ba-tag ba-tag-wa">WA</span>`). Кнопка отправки — `<span class="ba-command">EXECUTE_DUMP</span>`, на экране выглядит как `[ EXECUTE_DUMP ]`.

## Экраны → маршруты → API

`data-route`, `data-api`, `data-field`, `data-action` и `data-state` в разметке — подсказки для подключения; в production их можно удалить.

| Файл | Маршрут React | Компонент сейчас | API (docs/architecture/api.md) |
|---|---|---|---|
| `00-design-system` | — | — | Палитра, шрифты, кнопки, поля, теги, состояния, 404 |
| `01-home` | `/` | `HomePage` в `App.tsx` | — |
| `02-auth` | `/login`, `/register` | `LoginPage`, `RegisterPage` | `GET /auth/csrf`, `POST /auth/login`, `POST /auth/register` |
| `03-invite` | `/invites/:token` | `InvitePage` | `GET /invites/{token}`, `POST /invites/{token}/accept`; состояния гость/вошёл/принято/404-410-409 |
| `04-dashboard` | `/dashboard` | `DashboardPage` | `GET /me`, `GET /tournaments`, `GET /matches/{id}`, `POST /matches/{id}/ready` |
| `05-arena` | `/matches/:matchId` | `ParticipantWorkspacePage` | match, problem, languages, draft, submissions |
| `06-arena-states` | `/matches/:matchId` | то же | READY, RUNNING ≤60 с, PAUSED, FINALIZING, FINISHED/TIED, конфликт revision, ошибка, INFRA |
| `07-admin-tournaments` | `/admin` | `AdminTournamentsPage`, `TournamentForm` | `GET/POST /tournaments`, `DELETE /tournaments/{id}` |
| `08-admin-tournament` | `/admin/tournaments/:id` | `AdminTournamentPage` | participants, `/admin/users`, invites, `/problems` |
| `09-admin-match` | `/admin/tournaments/:id/matches` | `AdminMatchPage` | bracket generate/read/pairings/reset, match start/pause/resume/extend/technical-result/rematches/replacements |
| `10-watch` | `/watch` | `PublicViewerPage` | Список публичных турниров: endpoint в api.md пока не определён |
| `11-spectator` | `/watch/:tournamentId/matches/:matchId` | `SpectatorMapPage` | Публичный snapshot + SSE (`docs/architecture/realtime.md`) |
| `12-projector` | тот же маршрут + `?projector=1` | `SpectatorMapPage` (`spectator-page-projector`) | То же; без шапки, форм и кнопок управления |

## Правила, которые сохраняет разметка

- Регистрация не даёт выбрать роль; в интерфейсе указано, что новый аккаунт всегда участник.
- Ошибка компиляции (CE) и исходный код видны только автору в Arena View. На публичной карте, в ленте и в проекторе их нет; CE не выводится и в публичной ленте событий.
- Карта зрителя двигает фишку только по подтверждённому `solvedCount`, неуспешная попытка — красный узел без движения. Анимации (`ba-anim-solve`, `ba-anim-overtake`) запускаются один раз на новое SSE-событие, не при загрузке snapshot или переподключении. `prefers-reduced-motion` отключает их.
- Лидер всегда показан с объяснением тай-брейка (решено → штраф → последнее принятое), полное равенство — переигровка.
- В режимах PAUSED и FINALIZING кнопка отправки неактивна, причина видна.
- Диагностика компилятора — только текст (`<pre>`), без HTML.

## Вне MVP

Профиль с «паутинкой» навыков, ачивки и комбо, магазин имплантов, микрочат и «типы» нарисованы на холсте только как концепт, с пометкой «не подключать». Здесь их разметки нет. Тотализатор и просмотр чужого кода не проектировались: первый вне MVP, второй запрещён правилом приватности исходников (AGENTS.md, `docs/architecture/security.md`).

## Как переносить в frontend/src

1. Перенести токены из раздела 1 `blitz.css` в `frontend/src/index.css`, заменив текущие `--green` / `--orange` / `--surface`.
2. Подключить шрифты в `frontend/index.html`.
3. Стили компонентов переносить по разделам `blitz.css` в соответствующие `App.css`, `Admin.css`, `workspace.css`, `spectator.css`: имена классов уже совпадают.
4. Новые классы `ba-*` (теги, узлы, бейджи, таймер, лента, `ba-frame`) добавить в общий CSS. Логику, тексты состояний и проверки существующих компонентов не менять.
5. Бренд в шапке и подвале — BLITZ_ARENA вместо «блиц.»; названия пакетов и папок не переименовывать.

## Безопасный просмотр форм

Поля login/register в статическом preview отключены, кнопки не отправляют native GET. Данные аккаунтов в макеты не вводятся. При переносе в React использовать существующий session/CSRF HTTP client и обработчик формы; preview `disabled` не переносить в рабочую форму.
