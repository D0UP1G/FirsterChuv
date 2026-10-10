# Запрос A3: redact invite token в access logs

- Дата: 2026-10-10.
- Статус: `WAITING_CONNECT`; contract/request only, реализация `deploy/nginx/default.conf` и `backend/config/settings.py` остаётся у A3.
- Контекст: P1-03, S01/S02/T20; public access и redaction секретов в logs.

## Наблюдаемая граница

Invite preview/accept используют `GET /api/v1/invites/{token}` и `POST /api/v1/invites/{token}/accept`. В проекте нет собственного Nginx `log_format`/`access_log` rule, исключающего URI этих маршрутов; рабочий audit уже фиксировал, что Django development server выводит invite token path в access-log строке ([P4-06 audit](../audits/2026-10-09T224702+0300-agent-4-P4-06-browser-api-integration.md)). Точная конфигурация production/Nginx access logger не проверялась настоящим запуском в этом срезе.

P1-03 share secret не кладётся в request URI: admin API выдаёт ссылку `/watch/{tournamentId}#shareToken=...`, browser передаёт fragment value в `X-Tournament-Share-Token`. Fragment не отправляется HTTP и не попадает в стандартную URI access log. Хеш остаётся единственной persist representation.

## Требуемое действие в A3-owned runtime

- Для `/api/v1/invites/<token>` и `/api/v1/invites/<token>/accept` не записывать raw path/request URI в Nginx/web access log. Можно использовать dedicated route-level `access_log off` либо custom safe log format, сохраняющий статус, время, request ID и безопасный path без token.
- Проверить отдельно production Nginx и `runserver` development access logger; не выдавать reverse-proxy redaction за redaction Django stdout.
- Регрессия должна отправить synthetic token, проверить реальные доступные log sinks и подтвердить, что в них нет token; сохранить logging полезные поля без body/header/token.

Не выводить token в fixtures/audits/CI output. До этой проверки новый P1-03 share token transport безопасен относительно URI logs, но legacy invite-path log redaction и T20 secret-log acceptance остаются открытыми.
