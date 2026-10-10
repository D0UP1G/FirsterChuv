# Agent 4 · P2-04 publication start

Дата: 2026-10-10, Europe/Moscow. PR [#76](https://github.com/D0UP1G/FirsterChuv/pull/76) опубликован из `feature/a4-p2-04-ledger-persistence` в `develop`.

- PR head на момент создания: `a0d7e1044babfa4c2fb0205db6780201e324d142`.
- Fresh base: `origin/develop` `475cdf71fa88de6aa5aad2142fc9fdbdf90625f6`; он является предком head. Source #58/#59 остались отдельными OPEN refs и не менялись.
- Все пять CI checks запущены на точном head: `contracts-and-common-imports`, `backend`, `frontend`, `domain`, `sandbox-unit`; пока `IN_PROGRESS/QUEUED`. Merge не выполнялся.
- Локальная проверка и известный full-suite intermittent failure отражены в [implementation audit](2026-10-10T032018+0300-agent-4-P2-04-ledger.md). На PR сохраняется этот backend risk; повтор успешного одиночного теста не считается исправлением.
- Следующий шаг: дождаться пяти результатов exact-head CI; если только known unrelated invite concurrency снова упадёт, inspect log и rerun failed job на том же SHA. Исправления A3/A5/tournaments не включать без отдельной задачи.
