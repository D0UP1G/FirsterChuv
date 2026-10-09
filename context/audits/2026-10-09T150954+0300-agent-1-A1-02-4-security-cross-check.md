# Аудит: agent 1 / A1-02.4 / сверка T02 и T20

- Автор/роль агента: Codex, agent 1.
- Время проверки: `2026-10-09T15:09:54+03:00`.
- ID задачи: `A1-02.4`.
- Ветка: `feature/account-roles`.
- Базовый SHA: `be0323cb4ec8ee1357af767bbac855f751b627bc` (`origin/develop`); сверяемый feature tip: `16a8b80`.
- Статус: `IN_PROGRESS` — contract cross-check и документация завершены; общий A1-02 feature PR ещё предстоит.
- PR: не открыт на момент аудита.

## Объём сверки

Повторно проверены исходный PDF `docs/source/Кейс_Платформа_соревнований.pdf` (роли и техническое разграничение доступа), `docs/requirements.md` (`S02`, `TEAM01`, `TEAM06`), `docs/quality/mvp-acceptance.md` (строки `T02`, `T20`), API/security/runbook contracts, тесты accounts/common и реализация auth, role permissions и `create_admin`.

## T02: результат по критериям

| Критерий T02 | Реальное доказательство в feature slice | Оценка |
|---|---|---|
| Register создаёт participant | `AccountAuthenticationTests.test_register_requires_csrf_and_never_accepts_role_assignment` | Проверено тестом |
| Входной `role=admin` не повышает права | Тот же test: неизвестное поле отклонено, пользователь не создаётся; `create_admin` также отказывается повышать существующего participant | Проверено тестами |
| Anonymous и participant не выполняют admin write | `test_admin_permission_uses_application_role_and_active_state`: permission probe отвечает 401/403 | Базовый permission проверен; продуктовых admin write endpoints нет, критерий end-to-end не закрыт |
| Inactive account запрещён | `test_login_failure_is_generic_and_success_starts_private_session` и permission probe с inactive admin | Проверено на login/role gate, будущие tournament actions отсутствуют |

Итог: частичное evidence для `TEAM01`/`S02`, но `T02` остаётся `NOT_RUN` как полный acceptance scenario до реализации и проверки реальных admin CRUD, invite registration и отдельных browser sessions.

## T20: account slice и оставшиеся области

| Область T20 | Account slice | Что остаётся |
|---|---|---|
| CSRF | Register/login/logout тестируются с CSRF; register без token и cross-origin register отклоняются | Cross-origin browser matrix/proxy/origins; CSRF для будущих mutations |
| Role/mass assignment | Registration rejects `role=admin`; app permissions игнорируют Django staff flags; inactive users запрещены | UUID/object IDOR, реальные admin/domain endpoints, чужие source/draft/history |
| Secret/DTO leakage | Public user summary не включает password; `/me` не включает email; bootstrap output не включает пароль | Полные browser/log/SSE/artifact/sandbox canary scans отсутствуют |
| SQL injection | Не подтверждено adversarial query suite | Hostile search/filter и DB invariants |
| XSS | Не подтверждено | Отображение user-controlled name/Markdown/diagnostics в frontend |
| Command injection | Не подтверждено для judging path; bootstrap command не строит host shell command | Hostile source/filename/argv probes у Agent 3 и T18/T20 |
| SSRF/archive/deserialization | Не реализовано/не проверено account-веткой | Importer/package parser A3, включая redirects, traversal, symlink и size caps |
| Sandbox/network/host/secret isolation | Не проверено account-веткой | Реальные bounded hostile submissions и runtime evidence A3/A1 |

Итог: частичные доказательства только по auth CSRF, role escalation и ограниченному DTO/bootstrap secret output; весь `T20` остаётся `NOT_RUN`.

## Изменения документации

- `docs/architecture/security.md`: добавлена таблица фактического evidence account slice с ограничениями и проверяемыми именами тестов.
- `docs/architecture/api.md`: уточнено, что реальные admin writes и object ownership отсутствуют.
- `docs/quality/mvp-acceptance.md`: сохранён статус полного T02/T20 `NOT_RUN`, разъяснена разница с частичными feature tests.
- `context/agents/agent-1.md`: A1-02.4 отмечена выполненной; следующий шаг — PR после проверки актуальной базы.
- `context/STATE.md` не менялся: A1-02 не интегрирована в `develop`.
- Финальный PR diff review выявил устаревшую feature-only правку integrated STATE из раннего A1-02.1 commit; файл восстановлен до `origin/develop` без переписывания истории, чтобы в итоговом PR не менять integrated STATE.

## Проверки

| Команда | Результат | Ограничения |
|---|---|---|
| `uv run --env-file .env.example python manage.py test backend.apps.accounts backend.apps.common --verbosity 1` | 16 tests passed | Test client/probe views; не full browser/security suite |
| `uv run --env-file .env.example python manage.py check` | Успех, 0 issues | Не release gate |
| `uv run --env-file .env.example python manage.py makemigrations --check --dry-run` | Успех, `No changes detected` | Нет миграционных изменений |
| `git diff --check` | Успех | Feature PR review ещё впереди |

## Следующий шаг

Обновить/проверить feature against the latest `origin/develop`, выполнить финальный diff/secret review и открыть один PR `feature/account-roles` → `develop` с audits A1-02.1–A1-02.4. Полный T02/T20 и STATE status менять только после реальной интеграции и сценарных проверок; A1-03 остаётся отдельной feature задачей.

## Последующее изменение

После этого аудита PR #5 создан: [feat(auth): add account roles and secure admin bootstrap](https://github.com/D0UP1G/FirsterChuv/pull/5), target `develop`. GitHub сообщает `mergeStateStatus=CLEAN`; configured checks отсутствуют, `reviewDecision` пустой. Финальная ручная проверка, merge commit и подтверждение интеграции остаются следующими шагами.
