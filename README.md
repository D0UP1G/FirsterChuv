# FirsterChuv

Веб-платформа для блиц-турниров 1×1 по спортивному программированию (кейс «Платформа соревнований»): организатор ведёт турнир на выбывание, участник решает задачи в редакторе прямо на странице матча, код проверяется собственной песочницей, зритель наблюдает за ходом борьбы на живой карте.

## Что умеет

| Блок кейса | Возможности |
|---|---|
| Управление турниром | Турнир с датами и лимитом, приглашения (срок и лимит активаций, отзыв), состав, автосетка на выбывание с BYE, ручные пары, настройка матча, ручной и автоматический старт, пауза, продление, переигровка, техническая победа, замена |
| Условия и редактор | Markdown и TeX, картинки, примеры, лимиты, редактор с подсветкой, языки только из реально проверенных компиляторов, серверные и локальные черновики с версиями |
| Проверка кода | Собственная песочница в Docker: изолированная компиляция и запуск, лимиты, без сети и секретов; надёжная очередь посылок, воркер судьи, учёт результатов |
| Зрители | Публичная сетка и карта матча без регистрации, обновление через SSE, режим проектора |
| Защита | Роли `participant` и `admin`, CSRF, лимиты запросов, чужой код недоступен, публичные ответы без личных данных |

## Архитектура

- **Backend:** Django REST Framework, SQLite (WAL), приложения `accounts`, `tournaments`, `competition`, `problems`, `submissions`, `drafts`, `judge`, `events`.
- **Frontend:** React + TypeScript, Vite, редактор CodeMirror, безопасный Markdown/TeX.
- **Проверка (вариант Б кейса):** отдельный воркер с собственной песочницей; Яндекс Контест используется только для планируемого импорта задач.
- Подробнее: [архитектура](docs/architecture/README.md), [API](docs/architecture/api.md), [безопасность](docs/architecture/security.md).

## Быстрый старт (Docker, всё включено)

Нужны Git и Docker (Docker Desktop или Docker Engine с Compose). Запускаются сайт, API, воркер судьи и часы матча; код участников проверяется в изолированной песочнице.

1. Скопируйте настройки и задайте секрет: `cp .env.example .env` (в PowerShell: `copy .env.example .env`), затем в `.env` замените значение `DJANGO_SECRET_KEY` на любую случайную строку. Сохраняйте файл в UTF-8 без BOM.
2. Запустите:

   - Linux, macOS, WSL: `./scripts/start-demo.sh`
   - Windows (PowerShell, Docker Desktop должен быть запущен):

     ```powershell
     docker build --platform=linux/amd64 --tag firsterchuv/sandbox-cpp:0.1.0 sandbox
     $env:DOCKER_SOCKET_GID = "0"
     docker compose up --build
     ```

3. В другом терминале создайте демо-данные: `docker compose exec api python manage.py seed_demo`.
4. Откройте http://localhost:8080.

**Демо-аккаунты** (только для локального показа, команда `seed_demo` отказывается работать при `DJANGO_DEBUG=false`):

| Роль | Логин | Пароль |
|---|---|---|
| Организатор | `admin@demo.local` | `admin12345` |
| Участники | `player1@demo.local` … `player4@demo.local` | `player12345` |

**Пройти матч за пять минут:** войдите организатором → «Создать турнир» (лимит 2) → создайте приглашение и скопируйте ссылку → в двух разных браузерах (или окнах инкогнито) войдите игроками 1 и 2 и откройте ссылку → организатор: «Сетка и матчи» → «Сформировать сетку» → выберите задачу → «Сохранить настройки» → «Запустить матч» → игроки открывают матч из личного кабинета, пишут решение (демо-задача: сумма двух чисел) и жмут «Отправить решение» → вердикт приходит без перезагрузки; зритель без входа смотрит ход матча на странице «Зрителям».

Остановить: `docker compose down` (данные сохраняются); удалить вместе с данными: `docker compose down -v`. Если репозиторий клонировался до появления `.gitattributes`, выполните `git add --renormalize . && git checkout -- scripts`, чтобы у скриптов были окончания строк LF.

## Быстрый старт (разработка без Docker)

Нужны Python 3.14 с [uv](https://docs.astral.sh/uv/) и Node.js 20.19+. Песочница в этом режиме недоступна (нужен Linux и Docker), поэтому вердикты не выдаются.

```sh
cp .env.example .env            # задайте приватный DJANGO_SECRET_KEY
uv sync
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py seed_demo
uv run --env-file .env python manage.py runserver 127.0.0.1:8000
cd frontend && npm ci && npm run dev   # http://localhost:8080
```

Детали запуска, восстановления и защиты — в [runbook](docs/operations/runbook.md).

## Проверки

```sh
uv run --env-file .env python manage.py test      # backend
cd frontend && npm run typecheck && npm test && npm run build
```

## Статус

Сквозной путь «приглашение → матч → посылка → вердикт OK/WA → счёт → публичная карта» работает в Docker-запуске (проверено на реальной песочнице). Не пройдено до конца: вердикты CE/TL/ML/RE, продвижение победителя на реальных данных, враждебные проверки и официальный пакет задач организаторов (не получен). Результаты приёмки: [приёмка](docs/quality/mvp-acceptance.md), [M0](docs/quality/m0-demo.md), [состояние](context/STATE.md).

## Документация

- [Требования кейса и покрытие](docs/requirements.md), [исходный PDF](docs/source/Кейс_Платформа_соревнований.pdf).
- [Архитектура и решения](docs/architecture/README.md), [сценарии](docs/architecture/user-flows.md).
- [Запуск и защита](docs/operations/runbook.md), [GitFlow](docs/operations/gitflow.md).
- [Дизайн BLITZ_ARENA](frontend/design/README.md), [брендбук](docs/source/brandbook.md).

## Разработка и агенты

Работа ведётся по GitFlow (`feature/*` → PR в `develop`). Правила для ИИ-агентов — [AGENTS.md](AGENTS.md), план — [ROADMAP](ROADMAP.md), контекст — [context/](context/README.md).

Репозиторий: [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv).
