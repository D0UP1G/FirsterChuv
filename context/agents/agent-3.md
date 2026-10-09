# Агент 3: sandbox, задачи и код

Карточка объединена координатором при повторной ревизии 2026-10-09 по запросу команды; собственные аудиты владельца сохранены.

- В feature/mvp-integration-review-2 собраны sandbox PR #3 (6950f10) и normalized catalog PR #14 (9234951). До MERGED общего PR их код не приписывается develop.
- F01/F07 исправлены автором и перепроверены на заново собранном Docker image: 12 unit tests, real smoke включая protocol-write, bounded isolation/output/cleanup/recovery checks прошли. Full official/hostile T18/T21 не закрыты.
- Catalog — normalized parser/storage/DTO/readiness/immutable version, не official mapping, workspace HTTP или LocalJudge.
- Queue PR #15 (7d76d0b) не интегрируется: concurrent SQLite admission может дать необработанный database locked и HTTP 500; нужен bounded retry/503 и race regression.
- Следующие задачи: исправить #15, реализовать настоящий LocalJudge/worker по bundle и common ports, private drafts/history, programmatic import/public assets/language registry. Only official package adapter ждёт организаторов.
- При WAITING_CONNECT продолжать LocalJudge/core/recovery/drafts в своей зоне; test doubles разрешены только tests, runtime provider отсутствует → fail closed.

[ROADMAP](../../ROADMAP.md), [v1](../../docs/architecture/parallel-contracts.md). Итоговый consolidated status будет дополнен после проверки общего integration PR.
