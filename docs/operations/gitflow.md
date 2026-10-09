# GitFlow и совместная работа

Команда требует строгий GitFlow. История сохраняется, изменения проходят feature → PR → develop. Все branch names должны быть действительными Git refs и соответствовать роли ветки.

| Ветка | Источник | Назначение / куда merge |
|---|---|---|
| `main` | Первый bootstrap / release | Выпущенные версии, теги |
| `develop` | `main` при инициализации | Интеграция feature, основа release |
| `feature/<task>` | Актуальная `develop` | Одна задача/связанный срез → PR в develop |
| `release/<version>` | develop | Стабилизация → main + tag, обратно в develop |
| `hotfix/<version>` | main | Срочный ремонт выпуска → main + tag и develop |

Префикс `feature/` выбран по GitFlow и имеет приоритет над общими agent defaults. Squash/rebase merge в этом проекте не используется: PR сохраняет commits/audits через merge commit. Force push и прямые commits в main/develop после bootstrap не используются.

## Первичная инициализация

2026-10-09 repo был полностью пуст. Создан пустой корневой commit `e9fc0ef` на main, от него develop и feature/docs-mvp-context. Это одноразовое начало истории, не выпуск MVP. В feature находится только документация; PR направлен в develop. Не повторять bootstrap в уже существующем репозитории и не пересоздавать ветки поверх чужих коммитов.

## Начать задачу

В собственном checkout с чистым status:

```bash
git fetch origin --prune
git switch develop
git pull --ff-only origin develop
git switch -c feature/match-clock
```

Перед edits записать task/branch/base SHA в собственную context card. Для синхронизации feature использовать `git fetch origin`, затем `git merge origin/develop`, разрешить конфликты, повторить относящиеся проверки. Не обновлять чужие feature refs.

## Четыре изолированных checkout

Использовать отдельные clones или worktrees. В общем clone сначала получить origin/develop. Пример новых worktrees для свободных branch names:

```bash
git worktree add ../firster-agent-1 -b feature/platform-bootstrap origin/develop
git worktree add ../firster-agent-2 -b feature/bracket-runtime origin/develop
git worktree add ../firster-agent-3 -b feature/sandbox-proof origin/develop
git worktree add ../firster-agent-4 -b feature/frontend-shell-auth origin/develop
```

Если ветка существует, не создавать её повторно; проверить её владельца/состояние. Эти примеры не запускают агентов. Каждый работает только в собственном path; смена ветки root checkout не координирует параллельную работу.

## Commit и PR

1. Проверить diff, секреты, own tests/acceptance и `git diff --check`.
2. Заполнить отдельный audit и own card. Не менять общий integrated STATE для результата, которого ещё нет в develop.
3. Commit с понятным scope, например `feat(competition): enforce match deadline`; docs — `docs: document MVP architecture`.
4. Push только feature. PR base develop, description включает task IDs, requirement IDs, ссылку на audit, contract/migration changes, фактические проверки и ограничения.
5. После review/checks merge commit; координатор интеграции проверяет merge и обновляет STATE без блокирования следующей задачи. Feature удаляется только после доказанного включения и сохранения нужной работы.

Использовать PR template. Не записывать токены в CLI/PR, multiline body передавать через файл или structured argument. Опубликованность подтверждать `git ls-remote`/PR, не только локальным commit.

## Выпуск

После всей обязательной приёмки создать release/0.1.0 от develop. Разрешены исправления/release metadata/documentation, новые функции идут в будущие feature. Release PR → main; на release merge commit ставится annotated v0.1.0. Затем изменения release/main возвращаются в develop через PR/merge. В отличие от исходного empty bootstrap, main после этого содержит подтверждённый выпуск.

Проверить теги/remote refs и demo URI после публикации. Если на время release develop продолжает получать новые функции, не переносить их в текущий release случайным merge всей develop. Hotfix main также возвращается в develop, чтобы дефект не появился в следующей версии.

Ревизия 2026-10-09: main/develop protected=false, configured checks отсутствуют. P1-02 добавляет workflow jobs `contracts-and-common-imports`, `backend`, `domain`, `sandbox-unit`; при включении защиты рекомендуются обязательные PR для обеих веток, required checks по этим четырём именам, разрешённый merge commit, запрет force push/delete и хотя бы одно независимое approval review, если это позволяет размер команды. `sandbox-unit` остаётся зелёным с явным сообщением, когда suite отсутствует в ref. `Real sandbox smoke / real-smoke` не является обычным required check и требует boolean-подтверждения; его GitHub dispatch станет доступен после добавления workflow в текущую default branch `main` по обычному GitFlow release.

Это рекомендации для владельца репозитория. P1-02 не меняет GitHub rulesets/branch protection; после PR требуется отдельно проверить настройки и только тогда писать, что защита включена. Само наличие checks в PR не делает их обязательными для merge.

## Короткие срезы и актуальность

ROADMAP v2 заменяет ожидание всей чужой задачи контрактами и отдельными CONNECT-шагами. CODE merge достаточно для следующей feature-задачи; отдельный STATE sync PR не prerequisite. Реализацию алгоритма можно review/merge отдельно от полной browser acceptance, сохранив честный scope. Перед продолжением PR #3/#7 владелец merge-ит актуальный develop в свою ветку, не делает rebase/force push. При конфликтах карточки сохранить актуальный план P-ID и собственное новое фактическое состояние, прежние аудиты не переписывать.
