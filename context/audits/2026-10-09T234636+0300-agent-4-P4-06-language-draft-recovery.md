# Аудит реализации: Agent 4 / P4-06 language-scoped draft recovery

- Автор/роль: Agent 4 — интерфейсы, редактор, сохранение и зрительская карта.
- Время: `2026-10-09T23:45:14+03:00` — `2026-10-09T23:46:36+03:00` (Europe/Moscow).
- Задача: P4-06, E04/T15 — проверка language namespace на странице участника.
- Ветка: `feature/workspace-language-draft-recovery`.
- База `origin/develop`: `623a17912efa55fd00550565fdfc0ac06d41607a`.
- Task checkpoint commit: `da251319f96d8618e6478ad76b1b66cdf67ec4b5`.
- Статус: regression реализован; впереди публикация PR. T15/P4-06 не закрыты.

## Сверка с кейсом

E04/T15 требует draft namespace как минимум по user/run/problem/language. Existing `localDrafts.test.ts` покрывает ключ по всем четырём измерениям на unit-level; этот срез проверяет интеграцию страницы/переключателя языка/editor и повторного mount на явном dev transport. Реальный server draft provider по `/matches/{matchId}/problems/{problemId}/draft` не находится в `develop`; открытая PR #21 не используется.

## Изменения

- `frontend/src/pages/ParticipantWorkspacePage.test.tsx`: новый сценарий на задаче A вводит отдельный marker для `cpp20` и `python3`, переключает язык, возвращается к каждому исходнику и проверяет восстановление после page remount при недоступных draft GET/PUT (`draft=offline-fixture`). После remount проверяется исходный C++ draft, затем Python draft после явного выбора Python.
- Production компонент, hook, transport, backend/API contracts и `context/STATE.md` не менялись. Fake submissions остаются выключенными.
- Первая версия сценария ожидала, что выбранный Python язык сохранится как UI preference после remount. Тест показал, что страница корректно выбирает язык по умолчанию; T15 требует сохранить draft по namespace, но не сохранять preference селектора. Сценарий поправлен: после remount Python выбирается явно. Production defect не обнаружен.

## Проверки

- `npm test -- --run src/pages/ParticipantWorkspacePage.test.tsx`: PASS, 1 файл / 6 тестов.
- `npm run typecheck`: PASS.
- `npm test -- --run`: PASS, 18 файлов / 80 тестов.
- `npm run lint`: exit 0; 5 существующих `react(set-state-in-effect)` warnings в draft/page effects.
- `npm run build`: PASS; остаётся прежнее предупреждение о CodeEditor chunk `612.88 kB` (>500 kB).
- `git diff --check`: PASS после изменений кода, карточки и этого audit.

## Ограничения и следующий шаг

Это jsdom page remount + localStorage test при offline synthetic dev transport, не browser reload/restart, server durability или revision/conflict evidence. Provider-backed GET/PUT CONNECT остаётся `WAITING_CONNECT` до A3 P3-05/provider. Следующий шаг — финальный diff review, commit, PR → develop, CI на final PR head, ordinary merge commit и merge audit. T15 и P4-06 остаются partial/in progress.
