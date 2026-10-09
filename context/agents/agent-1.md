# Агент 1: платформа и запуск

Карточку перепланировал координатор по запросу команды 2026-10-09; это наблюдаемый статус и назначения, не новая рабочая сессия владельца.

- Реализация: bootstrap/auth/roles/tournament/roster интегрированы PR #2/#5/#8; state sync #4/#6/#9, roadmap #10 и invites P1-01 #12 merged.
- Интеграция P1-01: merge commit `cad34ea4ddf1171779dc22139f2e1533160b5015` в `develop`; PR #12 head `a0b3252904d684855d55d8d1ca163e64ed861f2c`. Полные T01/T02/T03/T04/T05/T20 всё ещё открыты.
- Текущая задача: **P1-02 IN_PROGRESS**, `feature/platform-ci-contracts`; финальная сверка новых PR #15/#16 и контрактных форм перед публикацией.
- База перед edits: актуальный `origin/develop=cad34ea4ddf1171779dc22139f2e1533160b5015`; отдельная feature-ветка создана от этого SHA. Новые open refs проверены read-only.
- Текущие пути: `.github/workflows/{ci.yml,sandbox-real-smoke.yml}`, `backend/apps/common/{contracts.py,tests.py}`, `backend/apps/tournaments/tests.py` (стабилизация race-assertion P1-01, найденной полным CI прогоном), `contracts/mvp-v1/schemas.json`, `scripts/{check_contracts.py,check_contract_imports.py,check_domain_suites.py}`, `pyproject.toml`, `uv.lock`, `context/STATE.md`, эта карточка, `docs/architecture/parallel-contracts.md`, GitFlow/quality docs и отдельный аудит сверки.
- Малые шаги P1-02: .1 синхронизировать STATE по подтверждённому PR #12 и обновить наблюдаемый список open refs; .2 CI для Django checks/tests/migration drift с отдельным sandbox-unit шагом без real-Docker подмены; .3 formal fixture schemas/checker и shared typed v1 ports без imports отсутствующих apps; .4 сверить PR #13–#16: локальные receipts/ResultSink в PR #15 требуют narrow adapter к неизменённому v1 при CONNECT, `LanguageRegistry.is_supported` совпадает с добавленным общим port; PR #16 event store пока без production EventWriter adapter. Не менять v1 required fields/semantics без version/migration plan; race-тест допускает только одно принятие и второй `invite_unavailable` либо bounded `database_busy`; сверить D02/S01/S02/T20 partial, записать аудит и PR.
- Очередь: P1-02 CI/contracts → P1-03 proxy/share access → P1-04 Compose → P1-05 release gate; P1-01 browser CONNECT остаётся у P4-02.
- Аудиты P1-02: [реализация CI и контрактов](../audits/2026-10-09T174100+0300-agent-1-P1-02-ci-contracts.md), [сверка PR #15/#16 и финальные проверки](../audits/2026-10-09T175107+0300-agent-1-P1-02-contract-refresh.md).
- Следующий шаг: опубликовать feature → develop, дождаться четырёх GitHub CI jobs, слить merge commit и обновить integrated STATE; P1-03 пока не начинать по текущему поручению.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
