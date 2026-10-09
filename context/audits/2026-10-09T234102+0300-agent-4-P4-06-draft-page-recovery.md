# Аудит: Agent 4 / P4-06 page-level local draft recovery

- Автор/роль: Agent 4 — интерфейсы, редактор, сохранение и зрительская карта.
- Время: `2026-10-09T23:36:46+03:00` — `2026-10-09T23:41:02+03:00` (Europe/Moscow).
- Задача: P4-06, E04/T15 — recovery local drafts при смене задачи и повторном mount workspace page.
- Ветка: `feature/workspace-page-draft-recovery`.
- База `origin/develop`: `25a82c092236d98275f897d624452b24bd501883`.
- Исходный task checkpoint: `fb475fa` (merge audit PR #39 и branch/base/path в карточке Agent 4).
- Статус: page-level component slice реализован; PR впереди; полный T15/P4-06 остаются `PARTIAL`/`IN_PROGRESS`.

## Цель и сверка с документацией

Кейс, `docs/requirements.md` E04 и acceptance T15 требуют сохранять исходник при смене задачи и reload, с namespace user/run/problem/language, локальной и серверной revision, без потери конфликтующих версий. Существующие тесты `useDraftController`/`localDrafts` уже покрывают controller/remount и namespace; этот срез проверяет интеграцию controller/editor/page через смену задачи и повторный mount. Реальный draft provider отсутствует в текущем `develop`; frontend transport endpoint — `/matches/{matchId}/problems/{problemId}/draft` с `runId` и `languageId` query, write идёт PUT на ту же resource.

## Изменения

- `frontend/src/workspace/devTransport.ts`: добавлен explicit dev-only `draft=offline-fixture`, который возвращает `503 integration_unavailable` для draft GET/PUT; HTTP/production transport не изменён.
- `frontend/src/pages/ParticipantWorkspacePage.test.tsx`: тест вводит разные source markers в задачах A и B, переключает A→B→A и проверяет восстановление. Затем размонтирует и повторно монтирует страницу с новым in-memory transport и подтверждает восстановление обоих drafts, пока server endpoint недоступен.
- `frontend/src/workspace/CodeEditor.test.tsx`: добавлен controlled-component regression test; он проверяет, что текущая controlled value принимает отдельные типовые key events.
- Submit в synthetic scenario остаётся disabled; тест подтверждает, что `fetch` не вызывается. Production hook, page, API/contracts, backend и `context/STATE.md` не менялись.

Пакетный вызов `userEvent.keyboard("draftA")` давал в jsdom пропущенные/переупорядоченные символы как в page test, так и в изолированном controlled editor. После отправки каждого символа отдельным keyboard event controlled editor и page scenario проходят; это фиксирует discrete input events и не потребовало изменения production code. Тест не используется как доказательство browser key repeat/timing.

## Проверки

- `npm test -- --run src/pages/ParticipantWorkspacePage.test.tsx src/workspace/CodeEditor.test.tsx`: PASS, 2 файла / 13 тестов.
- `npm run typecheck`: PASS.
- `npm test -- --run`: PASS, 18 файлов / 79 тестов.
- `npm run lint`: exit 0; 5 существующих warnings `react(set-state-in-effect)` в draft/page effects.
- `npm run build`: PASS; прежнее предупреждение о chunk `CodeEditor` размером 612.88 kB (>500 kB).
- `git diff --check`: PASS после изменений кода, карточки и этого audit.

## Ограничения и следующий шаг

Повторный mount страницы в jsdom плюс localStorage не является реальным browser reload, browser restart, offline browser test или доказательством durable server storage. Реальный GET/PUT draft CONNECT остаётся `WAITING_CONNECT` до интеграции A3 P3-05 provider; open PR #21 не использовалась как runtime dependency. Полный T15 также требует language/reconnect/server revision/conflict/browser проверки.

После завершения карточки/audit провести финальный diff check, выполнить commit, fresh fetch, открыть отдельный PR в `develop` и дождаться CI на final head. После merge перепроверить свежую очередь Agent 4 и продолжать доступный READY пункт.
