# Запрос контракта Agent 3: snapshot задачи принятой посылки

- Дата: 2026-10-09.
- Статус: `WAITING_CONNECT`; запрос фиксирует потребность, не меняет common v1 и не выбирает API.
- Задача: P3-04.4, trusted `JudgeJob` для accepted submission.
- Требования: J01/J02/J04, E03; P3-03/P3-04.4; частично T09/T14/T19/T20.

## Текущее состояние

`CompetitionGatewayV1.authorize_submission(...)` возвращает `SubmissionPermit` с `run_id`, `elapsed_ms` и `scoring_version`. `AttemptReceipt` фиксирует `run_id` и `problem_id`, но не immutable problem version/checksum. `TrustedJudgeJob` требует `problem_version` и `problem_checksum`. В свежем `origin/develop` нет production A2 run snapshot provider, из которого A3 мог бы получить эту пару.

По runtime handoff judge обязан использовать версию, назначенную именно тому immutable run, в котором принята посылка. `active latest` каталога, новый run после rematch или версия, выбранная после submit, недопустимы.

## Что нужно согласовать

Нужен стабильный способ получить при admission для пары `(run_id, problem_id)` доверенные `problem_version` и SHA-256 `problem_checksum`, а также подтверждение, что эта связь immutable в пределах run. Владельцы A2 определяют источник и момент фиксации; A1/A2 определяют, должен ли результат приходить additive полями permit либо через отдельную типизированную snapshot boundary. Это варианты для решения, не выбранный контракт.

A3 должен сохранить полученные значения вместе с accepted submission и передать их в `TrustedJudgeJob`; worker не должен запрашивать текущую версию задачи без ключа исходного run. Версия и checksum относятся к нормализованному доверенному bundle; checksum проверяется до sandbox execution. DTO не содержит source, tests, checker, reference solution или diagnostics.

## Владельцы и потребители

- Producer: A2, authoritative MatchRun/problem assignment snapshot и его lifecycle.
- Общая типизация, если потребуется изменение DTO/Protocol: A1 и A2; изменения сначала согласуются и вносятся в common contract отдельным срезом.
- Consumers: A3 submissions admission/persistence, worker snapshot resolver и LocalJudge `TrustedJudgeJob` adapter.
- Затрагиваемые файлы после CONNECT: `backend/apps/submissions/ports.py`, `models.py`, own migration, `services.py`, executor/factory tests; shared contract только после решения владельцев.

## Совместимость и fallback

Существующие `AttemptReceipt`/`ResultReceipt` и verdict semantics не расширяются этим запросом. Совместимый additive вариант предпочтительнее; точную форму и обязательность данных подтверждают owners. До готового production provider runtime admission/judging остаётся fail-closed с integration/readiness error. Нельзя принять посылку, а затем подставить latest version или тестовый fixture.

## Независимая работа

Failure outbox, leases, retry и тесты P3-04.4 не зависят от snapshot boundary и продолжаются отдельно. После CONNECT добавить сохранение snapshot полей и проверку, что после rematch старая посылка использует исходную пару version/checksum.
