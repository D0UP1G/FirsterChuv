# Агент 1: платформа и запуск

Карточку перепланировал координатор по запросу команды 2026-10-09; это наблюдаемый статус и назначения, не новая рабочая сессия владельца.

- Реализация: bootstrap/auth/roles/tournament/roster срезы A1-01/02/03 интегрированы PR #2/#5/#8; state sync #4/#6/#9 merged; документационная ревизия #10 merged.
- Приёмка: полные T01/T02/T03/T05/T20 ещё открыты; координатор повторил 37 backend tests на develop 146b2cb до PR #10.
- Текущая задача: **P1-01 IN_REVIEW**, `feature/tournament-invites`; backend-срез готов, ждёт PR в `develop`.
- База перед edits: исходная ветка создана от `146b2cb64a6273472c2de9cae04bfad21acd1782`; fetched `origin/develop=d9488e3bf960c6a2248fd4399ba5848a091b8769` влит merge commit `23dcd02e1f519dd4064d33956f60daf7ec932658`; до изменений дерева код проверен на этом synced HEAD.
- Текущие пути: `backend/apps/tournaments/{models,migrations,serializers,services,views,urls,tests}.py`, `backend/config/settings.py` (preview throttle), `docs/architecture/{api,data-model,parallel-contracts,security}.md`, `docs/{requirements.md,quality/mvp-acceptance.md}`, эта карточка и аудит.
- Малые шаги: P1-01.1 модели/ограничения/create-list-revoke; P1-01.2 public preview + authenticated accept; P1-01.3 атомарность use/roster-cap/repeat/race; P1-01.4 сверка M02/T04, аудит и PR.
- [x] P1-01.1 Invite/InviteAcceptance models, migration, create/list/revoke и hashed-token boundary.
- [x] P1-01.2 Anonymous rate-limited preview и authenticated participant accept после register/login.
- [x] P1-01.3 Atomic maxUses + roster cap/freeze + idempotency; DB/API concurrency regression tests.
- [x] P1-01.4 Проверить M02/S02/T04, обновить API/data/security acceptance docs и записать аудит.
- Проверки P1-01: `makemigrations --check --dry-run` — без drift; 10 invite/concurrency tests и полный backend suite (47 tests) прошли; `compileall` и `git diff --check` без ошибок. T04/S02 целиком всё ещё не приняты; см. audit.
- Очередь: P1-01 приглашения → P1-02 CI/короткие подключения → P1-03 proxy/share access → P1-04 Compose → P1-05 release gate.
- Если ждёт интеграция: делать CI/proxy/Compose; не ждать весь A2/A3/A4. STATE sync не блокирует начало задачи.
- Исторические подтверждения: [A1-03 review](../audits/2026-10-09T154714+0300-agent-1-A1-03-4-case-cross-check.md), [integration](../audits/2026-10-09T155025+0300-agent-1-A1-03-integration-state-sync.md), PR #8/#9.
- Следующий шаг: открыть PR P1-01 в `develop`, пройти merge commit и обновить integrated STATE; затем начать P1-02 в отдельной feature-ветке от актуального `origin/develop`. Не открывать заново merged STATE PR #9.

План: [ROADMAP v2](../../ROADMAP.md). Контракт: [parallel-contracts](../../docs/architecture/parallel-contracts.md). Ревизия: [отчёт](../../docs/reviews/2026-10-09-repository-audit.md). Перед edits владелец записывает фактическую сессию; после неё добавляет новый аудит.
