# Агент 3: sandbox, задачи, код

Перепланировано координатором 2026-10-09 по поручению команды; исторические NOT_RUN/PASS владельца не переписаны.

- Проверены/integration feature: #3 6950f10 harness F01/F07 fixes, 12 units/5 actual smoke/bounded isolation+cleanup+recovery; #14 9234951 normalized catalog/private split/immutable versions. GitHub MERGED общего PR определяет integration. Не повторять готовые cores.
- Первое READY P3-04.1: #15 7d76d0b busy/locked race → bounded whole-transaction retry/503, original received_at, file-backed concurrent keys/rollback tests, затем merge core.
- Главный execution READY P3-03: реальный LocalJudge/verified compiler на programmatically imported normalized smoke bundle, task limits/checker/OK WA TL ML RE CE, private diagnostics, infra отдельно. Это возможно без A2/UI/official package.
- Следом actual worker/recovery/result+failure adapters/immutable run version/checksum P3-04.2–4; Runtime без real gateway/provider отказывает, fixture verdict запрещён.
- Резерв READY P3-05 private revisioned drafts/history; P3-02 import/public workspace/assets/languages и strict artifact language type validation. Test access ports до короткого CONNECT A2.
- ONLY P3-06 WAITING_EXTERNAL: official package/README. Пока package нет, роль продолжает P3-02/03/04/05. P3-07 Yandex после обязательного MVP.
- Пути: sandbox/problems/submissions/drafts/judge и собственные migrations/tests. Full T12–15/T18–21 не закрыты; ML нельзя выводить только из signal9, source/checkers/tests не public.

## Текущая сессия: P3-03 · LocalJudge

- Статус: `IN_PROGRESS`.
- Ветка: `feature/local-judge`; база: `origin/develop` SHA `f7f4e2d42b42170b2169b608d1e86b6eb7af6921` (сверена после `git fetch origin develop`).
- Требования: J01/J02/E03 и часть J03/S01; ROADMAP v3 P3-03. Источники: `docs/requirements.md`, `docs/architecture/parallel-contracts.md`, `docs/architecture/runtime-handoffs.md`, `docs/architecture/judging.md`, страницы 4–5 и 7 кейса.
- Подзадачи: (1) реализовать `JudgeProvider.execute(TrustedJudgeJob)` поверх доверенного `ProblemCatalogV1.load_bundle`, проверить checksum и неизменяемую версию; (2) использовать только серверный compiler registry, компилировать и запускать каждый тест через собственную sandbox; (3) применить лимиты задачи с жёсткими пределами сервиса и классифицировать OK/WA/TL/ML/RE/CE, отделяя infra failures; (4) ограничить CE diagnostics и оставить их внутренним/private результатом; (5) покрыть policy/verdict/error/privacy границы тестами; (6) проверить реальный programmatically imported synthetic smoke только при доступном Docker Engine, не выдавая его за official acceptance.
- Пути с изменениями: `backend/apps/judge/`, регистрация своей app в `backend/config/settings.py`, `sandbox/runner.py` compatibility import, `sandbox/container_runner.cpp`, `sandbox/smoke.py`, `sandbox/tests/`, их README, эта карточка и отдельный P3-03 audit. `backend/apps/problems/compilers.py` не изменён: `cpp20` остаётся `verified=False` до настоящего Docker proof. `context/STATE.md` и чужие feature refs не менялись.
- Ограничение preflight: на `2026-10-09 20:42 MSK` `docker info` не подключился к `unix:///var/run/docker.sock`; `cpp20` остаётся `verified=False`, пока реальный sandbox/compiler proof не выполнен. Формат official checker неизвестен без package README; не вводить предположительный формат организаторов и не исполнять package scripts на host.
- Runtime CONNECT открыт: текущие `compose.yaml` и `backend/Dockerfile` не дают judge-worker Docker CLI/Engine access; это shared deployment wiring P1-04/P3-04.2. Доступность Docker из host runner сама по себе не меняет compiler readiness.
- Разделение результата: implementation и unit/policy evidence будут указаны отдельно от integration и acceptance. Официальный package/T12/T14/T18/T20/T21 acceptance не закрывается synthetic bundle или тестовыми doubles.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
