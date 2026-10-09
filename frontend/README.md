# Frontend FirsterChuv

React + TypeScript interface for the FirsterChuv blitz tournament platform.

Use Node.js `20.19+` or `22.12+` for the Vite toolchain.

## Локальный запуск

```sh
npm ci
npm run dev
```

Vite слушает `http://localhost:8080` и проксирует `/api` и `/health` к backend на `http://localhost:8000`. Порт 8080 совпадает с локальным значением `CSRF_TRUSTED_ORIGINS`. Запустите backend командой `./scripts/dev.sh` из корня репозитория. API client использует same-origin `/api/v1`; session cookie остаётся HttpOnly, а каждый mutation получает и отправляет CSRF-токен API.

В deployment frontend и `/api` должны работать под одним origin. Если задан отдельный API base URL, backend должен явно доверять origin браузера и разрешать запросы с credentials. Не помещайте токены и секреты в frontend environment variables.

## Проверки

```sh
npm run typecheck
npm run lint
npm test
npm run build
```

Регистрация создаёт аккаунт участника, но не открывает сессию: затем пользователь входит обычным способом. Публичные маршруты независимы от auth guard. CRUD турниров, редактор и live-данные зрительской карты подключаются в следующих срезах P4-02–P4-06.
