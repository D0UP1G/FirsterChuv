# Запрос A3: безопасная очистка orphan sandbox после остановки worker

- Дата: 2026-10-09.
- Статус: `WAITING_CONNECT`; этот запрос не меняет общий контракт, Docker/Compose или active worker.
- Задача: P3-04.2, J04/T19; crash/restart и удаление только собственных orphan containers.

## Наблюдаемая граница

`SubmissionService` выдаёт durable claim с ограниченным lease и восстанавливает просроченные DB claims/outbox. `DockerRunner` создаёт отдельные контейнеры с случайными именами и удаляет их в `finally`. При принудительном завершении Python worker `finally` не выполняется, Docker container может пережить процесс. Сейчас нет устойчивой связи `container → submission/claim lease`, а также общего подтверждённого механизма, который доказывает, что worker-владелец уже не активен.

ROADMAP v3 включает собственную очистку orphan containers в P3-04.2. При этом ADR07 в `docs/architecture/decisions.md` всё ещё имеет статус `PROPOSED`; нельзя считать единственный worker подтверждённой гарантией конкурентности. Sweep по общему имени/label может удалить контейнер другого активного worker или контейнер, который LocalJudge ещё инспектирует после завершения процесса.

## Что требуется согласовать

Нужно определить owner/lease boundary, по которой A3 может доказать, что контейнер больше не обслуживает действующую работу. Потребители: A3 `SubmissionWorker` и LocalJudge `DockerRunner`; runtime concurrency/развёртывание worker координирует A1. Возможные направления для обсуждения (не выбраны):

- привязать sandbox container к устойчивому accepted submission + claim/fencing token и сверять его с текущим lease до удаления;
- либо подтвердить и технически обеспечить эксклюзивность worker на общем runtime-хранилище, включая restart/expiry semantics.

Точный способ должен переживать process kill, не удалять живую работу параллельного worker, не передавать Docker authority API/solution и оставаться совместимым с SQLite single-host MVP.

## До согласования

- `finally` cleanup для штатных и перехваченных ошибок остаётся активным.
- DB lease recovery остаётся активным и не подменяет container cleanup.
- Startup не запускает глобальный `docker rm/prune` и не угадывает ownership по имени/метке.
- T19/process-kill container cleanup не объявляется закрытым; после согласования нужны file-backed lease/concurrency tests и Docker restart smoke на изолированном runtime.
- Остальные worker/outbox/adapter задачи продолжаются независимо.
