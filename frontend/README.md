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

Регистрация создаёт аккаунт участника, но не открывает сессию: затем пользователь входит обычным способом. Публичные маршруты независимы от auth guard. Маршрут `/admin` управляет реальными турнирами, ростером и ограниченными приглашениями; `/invites/:token` показывает публичное preview, сохраняет ссылку через регистрацию/вход и принимает её только аккаунтом participant. Raw invite token показывается только после создания и не сохраняется в локальном хранилище.

P4-01—P4-04 уже интегрированы в `develop`. P4-04 добавляет участнику рабочее место, безопасное отображение условия, редактор и локальные/ревизионные черновики. Его dev-сценарий изолирован; пока problem/draft/submission API не подключены на актуальном `develop`, production показывает ошибку endpoint и не создаёт тестовые вердикты.

P4-05 spectator-map UI slice разрабатывается в `feature/spectator-map`. Публичные маршруты карты: `/watch/:tournamentId` и `/watch/:tournamentId/matches/:matchId`; режим проектора включается параметром `projector=1`. В локальной разработке synthetic fixtures доступны только при явном `?scenario=public-map`. Без PublicAccess и SSE backend production не подменяет отсутствующий endpoint fixtures-данными. Public snapshot/event validators принимают только allowlisted поля и закрываются при неописанных/private полях; source, email и compiler diagnostics не запрашиваются и не отображаются. Реальный HTTP/SSE CONNECT выполняется отдельно после интеграции P2-06 и A1 PublicAccess на exact SHA.
