# Аудит: Agent 4 / P4-06 compiler language UI pass-through

- Автор/роль: Agent 4 — интерфейсы, редактор, сохранение и зрительская карта.
- Время: `2026-10-09T23:30:45+03:00` — `2026-10-09T23:32:56+03:00` (Europe/Moscow).
- Задача: P4-06, E02/T13 — UI поведение для языка из workspace language response без локального syntax mode.
- Ветка: `feature/server-compiler-language-ui`.
- База `origin/develop`: `7e2cb466676e13f6ecc5a90eba858f3655eed570`.
- Исходный task checkpoint: `c6f7d11` (merge audit PR #36 и Agent 4 card с branch/base/path).
- Статус: UI component slice выполнен; публикация отдельным PR впереди; полный E02/T13 и P4-06 — `PARTIAL`/`IN_PROGRESS`.

## Цель и границы

`docs/requirements.md` E02 требует языки из реально доступных компиляторов и шаблоны; E01/T13 требует рабочий редактор. `ROADMAP.md` разрешает продолжать независимые UI regression checks, пока provider/runtime отсутствует, при условии что synthetic data остаётся строго в явном DEV scenario. Реальный endpoint `/matches/{matchId}/problems/{problemId}/languages` не присутствует в `develop` на базе `7e2cb46`; workspace contract во frontend — `MatchProblemLanguage[]`.

Тест не заявляет, что `rust2024` установлен или доступен в production registry. Он проверяет только то, что workspace не отбрасывает language response, если локального CodeMirror highlighter нет, и использует предоставленный транспортом template.

## Изменения

- `frontend/src/workspace/devTransport.ts`: добавлен фиксированный `rust2024` test/dev fixture только при параметре `compiler=rust-fixture`; он выбирается лишь при одновременно включённом explicit `scenario=workspace-ui`.
- `frontend/src/pages/ParticipantWorkspacePage.test.tsx`: добавлен компонентный тест выбора `rust2024`, появления отличительной строки `println!("Hello, world!");` из language template в editable plain-text editor, подсказки об отсутствии локальной подсветки и отключённой fake submission кнопки.
- Production transport/API, compiler registry, API contracts, submissions, draft storage и backend не менялись; `fetch` не вызывается для isolated fixture.
- Обновлены карточка Agent 4 и этот аудит. `context/STATE.md` не менялся.

## Проверки

- `npm test -- --run src/pages/ParticipantWorkspacePage.test.tsx`: PASS, 1 файл / 4 теста.
- `npm run typecheck`: PASS.
- `npm test -- --run`: PASS, 18 файлов / 77 тестов.
- `npm run lint`: exit 0; остаются 5 прежних `react(set-state-in-effect)` warnings.
- `npm run build`: PASS; существующее предупреждение о chunk `CodeEditor` 612.88 kB (>500 kB).
- `git diff --check`: PASS после финальных исходниковых изменений и оформления карточки/audit.

## Сверка с кейсом и ограничения

Этот UI slice подтверждает передачу language/template и plain-text fallback внутри компонентного dev scenario. Он не подключает или не проверяет реальный compiler registry, не компилирует Rust и не является T13/T14/T21 acceptance. Dev scenario не посылает code и не рисует verdict.

Фактическая доступность языка остаётся `WAITING_CONNECT`: endpoint `/matches/{matchId}/problems/{problemId}/languages` отсутствует на текущем `develop`; ожидаемый DTO `MatchProblemLanguage[]`; владелец интеграции — A3 через P3-02/P3-03. После provider merge подключить его на exact SHA и выполнить браузерный/compiler CONNECT. Этот ожидательный подпункт не блокирует другие готовые задачи Agent 4.

## Следующий шаг

Повторить focused test после последней правки названия, проверить diff/base, затем опубликовать feature PR в `develop`. После merge зафиксировать merge checkpoint, перечитать свежие roadmap/state и продолжить следующую READY задачу Agent 4; не смешивать этот synthetic test с real compiler acceptance.
