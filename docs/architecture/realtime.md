# Public snapshots и SSE

Поток однонаправленный: commands/submit через REST, updates через SSE. Вариант разрешён кейсом. Backend агент 2 владеет логом/проекцией, frontend агент 4 — подключением/отображением.

## Согласованность

State change и MatchEvent сохраняются одной SQLite транзакцией. EventId монотонный и durable. Snapshot содержит `lastEventId` вместе с state на согласованной точке: выполнить короткое согласованное чтение, чтобы событие не оказалось включено в state, но отсутствовало в cursor.

Browser сначала получает snapshot, потом открывает SSE с cursor (`afterEventId` для первого подключения, `Last-Event-ID` для reconnect). Сервер отправляет события с ID больше cursor. При слишком старом/неверном cursor сообщает `stream.resync_required`; frontend перечитывает snapshot. Транспортное дублирование допустимо, повторная анимация/изменение score не допускается: dedupe по ID, score приходит authoritative.

Не открывать SQLite write transaction на срок жизни SSE. Django ASGI async stream делает bounded reads и heartbeat; backend/proxy не буферизуют поток. У клиента виден connection/stale статус; большие задержки не выглядят как остановка матча. На overflow дать resync, не накапливать неограниченную очередь на каждого клиента.

## Безопасный DTO

```json
{
  "matchId": "00000000-0000-0000-0000-000000000001",
  "runId": "00000000-0000-0000-0000-000000000002",
  "status": "RUNNING",
  "serverNow": "2026-10-09T12:03:00Z",
  "elapsedMs": 180000,
  "remainingMs": 1020000,
  "leaderUserId": "00000000-0000-0000-0000-000000000003",
  "lastEventId": 42,
  "players": [{
    "userId": "00000000-0000-0000-0000-000000000003",
    "displayName": "Ира",
    "solvedCount": 1,
    "penaltyMs": 134000,
    "tasks": [{"label": "A", "status": "SOLVED", "attempts": 1, "lastVerdict": "OK"}]
  }]
}
```

Два игрока, все задачи и published score rules должны присутствовать в реальном DTO; пример сокращён. Allowed task statuses NOT_STARTED/ATTEMPTED/SOLVED. Код, email, пароль, session, source path, raw compiler logs, test input/output и package secrets запрещены. Public serializer whitelist, нельзя использовать `fields="__all__"` для модели submission/user.

## События

| Type | Разрешённый payload / эффект |
|---|---|
| `match.started` | runId, state/clock, players; открыть новый run |
| `match.paused`, `match.resumed`, `match.extended` | clock/state, bounded public reason |
| `submission.accepted` | submissionId, playerId, task label, attempt count; без source |
| `submission.judged` | task label, playerId, normalized verdict |
| `score.changed` | authoritative players score/task states и leader |
| `match.tied`, `match.finished` | state/winner/reasonKind, не private logs |
| `bracket.advanced` | winner, upstream/downstream match/slot |
| `match.restarted`, `participant.replaced` | new run/slots; old events не изменяют current map |

SSE frame: `id: 43`, `event: score.changed`, `data: <JSON>`, пустая строка. Использовать JSON serializer; пользовательский displayName/reason не вставляется в протокольные строки, чтобы newline не создал поддельное event. Frontend отображает строки как text.

## Карта

Положение по solvedCount, отдельные checkpoints/statuses по A–D и badge leader с объяснением penalty tie-break. Задачи решаются не обязательно слева направо. Не показывать неуспешный submit как пройденную задачу и не двигать фишку автоматически от времени.

Обгон определяется сменой authoritative leader, победа — FINISHED, task solve — переходом в SOLVED. Initial snapshot/replay после reconnect обновляет state; уже прошедшие события не запускают повторную победную анимацию. Projector включает крупный timer, players/score, task grid и bracket navigation; управление отдельно от публичного экрана.

Public tournament checked до snapshot/stream. Unlisted token даёт только read, его hash хранится в DB, query token редактируется в логах и не отправляется referer. Длинные соединения имеют rate/connection cap, heartbeat, отключение медленного клиента; unlimited SSE может перегрузить MVP даже без права submit.
