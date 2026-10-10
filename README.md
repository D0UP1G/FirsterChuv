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

## Быстрый старт (разработка)

Нужны Python 3.14 с [uv](https://docs.astral.sh/uv/) и Node.js 20.19+.

```sh
cp .env.example .env            # задайте приватный DJANGO_SECRET_KEY
uv sync
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py create_admin --email admin@example.com --display-name Admin
uv run --env-file .env python manage.py runserver 127.0.0.1:8000
cd frontend && npm ci && npm run dev   # http://localhost:8080
```

Демо-задачу можно загрузить командой `uv run --env-file .env python manage.py import_demo_problem`. Запуск всего стенда (API, веб, воркер судьи, таймер матча) описан в [runbook](docs/operations/runbook.md): `scripts/start-demo.sh` требует Linux с Docker Engine и Docker Compose.

## Проверки

```sh
uv run --env-file .env python manage.py test      # backend
cd frontend && npm run typecheck && npm test && npm run build
```

## Статус

Сквозной путь «приглашение → матч → посылка → публичная карта» работает; получение вердикта требует Docker Engine и проверенного компилятора, а официальный пакет задач организаторов пока не получен. Результаты приёмки: [приёмка](docs/quality/mvp-acceptance.md), [M0](docs/quality/m0-demo.md), [состояние](context/STATE.md).

## Документация

- [Требования кейса и покрытие](docs/requirements.md), [исходный PDF](docs/source/Кейс_Платформа_соревнований.pdf).
- [Архитектура и решения](docs/architecture/README.md), [сценарии](docs/architecture/user-flows.md).
- [Запуск и защита](docs/operations/runbook.md), [GitFlow](docs/operations/gitflow.md).
- [Дизайн BLITZ_ARENA](frontend/design/README.md), [брендбук](docs/source/brandbook.md).

## Разработка и агенты

Работа ведётся по GitFlow (`feature/*` → PR в `develop`). Правила для ИИ-агентов — [AGENTS.md](AGENTS.md), план — [ROADMAP](ROADMAP.md), контекст — [context/](context/README.md).

Репозиторий: [D0UP1G/FirsterChuv](https://github.com/D0UP1G/FirsterChuv).
