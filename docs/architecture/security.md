# Безопасность и защита от инъекций

Это обязательная часть архитектуры и приёмки. Команда отдельно потребовала защиту от инъекций. Кейс требует изоляции, защищённых секретов и разграничения прав; для собственного judge эксперты проверяют враждебные решения. Перечень ниже превращает эти требования в конкретные меры и проверки.

Текущая документация не означает, что защита уже реализована. Каждый контроль подтверждается в T18/T20 и аудите владельца.

Feature branch Agent 1 содержит account slice A1-02 и A1-03.1/.2: явную CSRF-защиту изменений аккаунта/турнира/roster, HttpOnly cookies сессии/CSRF, серверное назначение роли participant, ограничение частоты auth-запросов, admin-only tournament writes и roster API с минимальным directory. `IsApplicationAdmin` не доверяет Django `is_staff`/`is_superuser`; неактивная учётная запись не проходит permission check. Строгие serializers отклоняют неизвестные и доступные только для чтения поля. Следующий шаг A1-03.3 усиливает одновременные cap/freeze переходы; replacement после игры остаётся контролируемым действием A2. Private match ownership остаётся ответственностью A2/A3. Частичные тесты не закрывают T02/T20 целиком. DRF throttle cache пока process-local; Compose запускает один API process. До нескольких API processes/replicas нужно настроить shared throttle cache и сверить `NUM_PROXIES` с фактической доверенной proxy chain.

### Частичные доказательства backend slices Agent 1

Результаты ниже относятся к несмерженным feature-срезам Agent 1 и их backend tests. Полные T02/T03/T05/T20 в `docs/quality/mvp-acceptance.md` остаются `NOT_RUN` до concurrency/freeze hardening, интегрированной browser/API проверки, проверки истории сыгравшего участника и полной security матрицы.

| Проверка | Доказательство | Что остаётся вне результата |
|---|---|---|
| Регистрация всегда выдаёт `participant`; `role=admin` и неизвестные поля отклоняются | `AccountAuthenticationTests.test_register_requires_csrf_and_never_accepts_role_assignment` | Invite accept и полный путь регистрации по приглашению |
| Анонимный запрос и participant не получают admin permission; inactive admin запрещён; Django staff flags не заменяют application role | `AccountAuthenticationTests.test_admin_permission_uses_application_role_and_active_state` | Это probe view, а не реальный tournament/admin write endpoint; нет object ownership/UUID IDOR checks |
| Неизвестный email, неверный пароль и inactive account дают одинаковый login failure | `AccountAuthenticationTests.test_login_failure_is_generic_and_success_starts_private_session` | Browser/session matrix и downstream permission checks для реальных endpoint |
| Auth mutations требуют CSRF, cross-origin registration отклоняется, session/private response не кэшируются | `AccountAuthenticationTests.test_register_requires_csrf_and_never_accepts_role_assignment`, `test_cross_origin_registration_is_rejected`, `test_csrf_token_is_http_only_and_me_requires_login` | Полный hostile browser suite на каждой будущей mutation и всех origins/proxy paths |
| Bootstrap не принимает password option, не печатает secret, не повышает participant и не меняет существующий пароль | `CreateAdminCommandTests` | Production secret manager/host process review; лог/CI/runtime secret scans всей системы |
| Tournament CRUD доступен только активному application admin, требует CSRF, проверяет даты/cap/format/visibility/config и отклоняет mass assignment | `TournamentAPITests.test_admin_can_create_list_read_and_patch_a_tournament`, `test_create_rejects_invalid_dates_cap_format_visibility_and_unknown_fields`, `test_admin_mutations_require_csrf_and_reject_mass_assignment` | Несмерженный A1-03.1; полного T03 и browser check нет |
| Directory не раскрывает email; roster принимает только активного participant, соблюдает cap/seed, идемпотентно назначает и логически снимает; participant не читает чужой tournament UUID | `TournamentAPITests.test_admin_user_directory_is_minimal_active_participant_only_and_bounded`, `test_capacity_seed_uniqueness_and_active_participant_role_are_enforced`, `test_assign_is_idempotent_remove_is_logical_and_reassignment_reuses_entry`, `test_participant_reads_only_joined_tournaments_and_safe_roster_fields` | Несмерженный A1-03.2; нет параллельного accept/assignment test, freeze service и полного T05/browser check |
| SQL/XSS/SSRF/archive/worker command attacks, source confidentiality и sandbox isolation | Нет account-slice доказательства для этих threat areas | Владелец/приёмка по A1/A3/A4 и полному T20 |

Следовательно, текущие проверки дают частичные доказательства для `TEAM01`/`S02` и отдельных ветвей `T02`/`T20`, но не pass целого acceptance scenario.

## Границы доверия

Недоверенные данные: HTTP body/query, UUID, email/displayName/description, source, custom stdin, Markdown/TeX/assets, архивы/manifest и remote import responses. Admin-only upload тоже валидируется. Исполняемый source всегда враждебен, даже если пользователь зарегистрирован.

Trusted API управляет состоянием, но не имеет Docker socket. Trusted worker исполняет фиксированные container commands; его Docker socket не публикуется и не попадает в sandbox. Solution container не получает DB, network, host filesystem, official tests/эталон/checker и secret env. Checker/validator/reference работают в отдельных ограниченных запусках, не в namespace API/worker.

## Угрозы, защита и доказательства

| Угроза | Мера | Проверка / владелец |
|---|---|---|
| SQL injection | Django ORM/параметризованные запросы; whitelist sort/filter, без f-string SQL | T20: hostile search/email/filter не меняют query/permissions; A1/A2/A3 |
| Command injection | `shell=False`/argv; compiler/image/file paths из registry, не client; никаких host `eval/exec/os.system` | T20: shell metacharacters в source/name/lang остаются данными; A3 |
| Stored/reflected XSS | Raw HTML Markdown отключён/санитизирован; safe URLs, TeX trust disabled; text-render diagnostics/name/reason | T20: script/event-handler/js URL в condition/name/CE не исполняется; A4/A3 |
| CSRF | Django CSRF на всех browser mutations, register/login включительно; SameSite cookie; один origin | T20: write без валидного CSRF отклонён; A1/A4 |
| IDOR / broken access | Role + object/run permission на каждом private endpoint; own source/draft/history only | T02/T20: participant A не читает/изменяет B по UUID; A1/A3 |
| Mass assignment / escalation | Serializer field allowlist, role default серверный, score/winner/createdBy не обычные поля PATCH | T02/T20: role=admin не повышает права; A1/A2 |
| SSRF remote import | Fixed source/ID, проверенный host allowlist, запрет internal/local/metadata IPv4/IPv6, redirect/DNS checks, timeout/size cap | T20: localhost/file/internal URL не загружается; A3 |
| Zip Slip / traversal / symlink | Path resolve под private root, reject absolute/`..`/links, file count/uncompressed size/ratio limits | T20: archive не пишет вне root и не раскрывает data; A3 |
| Zip/decompression bomb | Bounded compressed/uncompressed sizes, count и timeout | T20: oversized archive отклонён без заполнения диска; A3 |
| Небезопасная десериализация | JSON/schema или safe YAML, без pickle/eval/unsafe loader; manifest не запускает команды | T20: malicious manifest не исполняет код; A3 |
| RCE и утечка через compiler/run | Compile/runtime isolation с net none, read-only root, tmpfs, limits, non-root, capabilities/seccomp | T18: hostile execution и проверка последующего normal job; A3 |
| Resource DoS | Source/upload/output/queue/request caps, rate limits, один worker/контейнер execution, pids/memory/CPU/wall limits | T18/T19/T20: overload не теряет accepted job; A1/A3 |
| Secret leakage | Service-specific env, `.env` ignored, private data volumes, logs redaction, no secrets in container env/DTO | T20: canary secret не обнаружен browser/source output; A1/A3 |
| Повтор/гонка mutations | Idempotency + SQLite atomic/CAS/unique constraints | T04/T09/T10/T19: duplicate invite/submit/result/start не удваивает state; A1/A2/A3 |
| SSE/JSON injection, public data leak | Type allowlist, JSON serializer, sanitized public projection, cursor guards | T17/T20: newline/name не создают event, source отсутствует; A2/A4 |

## HTTP, auth и frontend

Password hashing штатным поддерживаемым Django hasher, а не собственной схемой. Login/register имеют rate limits и безопасные сообщения. Session cookie HttpOnly, Secure при HTTPS, SameSite; production DEBUG off, ALLOWED_HOSTS и trusted origins заданы. Logout инвалидирует session. Для локального HTTP исключение Secure только в dev settings, не в production.

Application role admin не выдаёт Django superuser автоматически. `create_admin` создаёт первичный application admin с `is_staff=False` и `is_superuser=False`, запрашивает пароль без echo в TTY или читает его из `DJANGO_ADMIN_PASSWORD`, переданного через protected secret injection; пароль не является CLI argument и не выводится. Команда идемпотентна для существующего активного admin и не меняет его пароль; существующего participant она не повышает. Public role promotion не существует. Деактивированный аккаунт не может submit/управлять.

CORS с credentials только для разрешённого origin; предпочтительно один origin через proxy. GET не меняет state. Login/register CSRF защищаются явно: DRF SessionAuthentication для анонимного запроса не заменяет эту меру. Private code/draft/diagnostics responses no-store, shared caches запрещены.

Markdown не вставляется в DOM без sanitizer; внешние опасные схемы `javascript:`/`data:text/html` исключены, TeX trust false. SVG/HTML assets отвергать либо безопасно преобразовывать; не обслуживать активный SVG как произвольный HTML. Content-Type allowlist, `X-Content-Type-Options: nosniff`, CSP под реальные editor workers/renderer и `Referrer-Policy`. CSP дополняет sanitizer, не заменяет его. Пользовательские названия и ошибки компилятора показываются как текст.

Local draft namespace содержит user/run/problem/language; logout не оставляет source доступным следующему вошедшему пользователю через UI. Смена task/language сначала сохраняет draft. Source не добавлять в аналитические payload/URL/error report.

## Импорт и файловая система

Не принимать путь к файловой системе из браузера. Upload сохраняется по сгенерированному ID, assets запрашиваются по assetId. Проверка resolved path должна исключать escape через symlink и hardlink, а не только строку `../`.

Package parser проверяет схему, количество/размеры файлов, MIME, references и checksums. Только официальный формат README; никаких автозапусков `setup.sh`/manifest commands. Public assets и private tests находятся в разных roots; proxy не раздаёт `.data`/uploads целиком. Ошибка импорта атомарна и не оставляет READY проблему с частично отсутствующими тестами.

Яндекс importer строит запрос из фиксированного проверенного host и валидированных IDs. Пользовательский URL/image link не является разрешением fetch. Не следовать redirect на private addresses; защищаться от DNS rebinding, ограничивать timeout/response size. Не считать, что remote statement содержит secret tests. Tokens только в API/import service, не в trusted worker env.

## Sandbox и процессы

Контейнеры solution/compiler/checker всегда одноразовые, без `--privileged`, host net/PID, writable host mounts и Docker socket. Root read-only + bounded tmpfs, non-root, cap-drop, no-new-privileges, pids/CPU/memory/wall limits. Все команды из server registry; source передаётся файлом/bytes, не shell interpolation.

Timeout watchdog живёт снаружи solution и убивает container при зависании. Output capture bounded, чтобы бесконечная печать не заполнила RAM/диск. Worker cleanup действует только на свои project/job labels; не запускать глобальный `docker system prune` в recovery. После crash stale jobs/containers восстанавливаются по lease, без двойного score.

В sandbox не передаются official test files целиком, DB, API settings, secret env или каталоги репозитория. Текущий test input подаётся stdin, expected output остаётся в orchestrator/checker. Пользователь может видеть свой stdin/процессы внутри sandbox, но не данные сервера. Условия с filesystem operations требуют отдельной поддержанной модели по пакету; не включать произвольный host доступ.

## Security acceptance

T18: infinite loop, memory exhaustion, process creation, network probe, host/secret-read probe, endless output, compile-resource exhaustion. Проверить timeout/OOM/pids isolation, bounded output, cleanup, нормальную проверку сразу после атаки. Probe использует безопасный canary, реальные секреты в отчёт не копировать.

T20: SQL/XSS/CSRF/SSRF/archive/command injection и обход ролей/UUID. Проверять server response, DB invariants и browser effect; отсутствие видимой ошибки само по себе не доказывает защиту. Записать фактические execution settings и ограничения платформы, а не утверждение «Docker полностью безопасен».

Если Docker/isolation недоступны, запрещено временно выполнять participant code напрямую. Сохранить submission и показать infrastructure error. Перед release непройденные обязательные security checks блокируют заявление о готовности.
