# Агент 1: платформа и запуск

Перепланировано координатором по поручению команды 2026-10-09, наблюдаемые факты не присваивают работу автора.

- DONE backend: bootstrap/auth/roles/CRUD/roster #2/#5/#8, invites P1-01 #12, CI/common P1-02 #17 и docs #18/#19. Не повторять готовые срезы.
- Прежний stop после P1-02 относится к отдельной сессии владельца. Следующие задания назначены для её нового запуска, документ не отправляет resume в другой чат.
- Первое READY: P1-03 public/unlisted share access port + proxy topology/log token redaction. Никакой зависимости от judge/UI.
- Резерв READY: P1-04 infrastructure/build/readiness; P1-02.5 additive failure DTO/Protocol/import tests по runtime handoffs. Common ports не дают runtime готовности.
- CONNECT: отдельно каждый реальный clock/worker/frontend command/SHA; отсутствующий provider fail closed. До подключения продолжать инфраструктуру/access/common, не заканчивать сессию из-за ожидания одного модуля.
- Пути: common/accounts/tournaments/config/CI/scripts/deploy/Compose; владельцы apps делают свои минимальные registrations.
- Full T01/T02/T03/T04/T05/T18/T20/T21 открыты. P1-05 release/demo только после R1/R2/official acceptance.
- Перед edits: собственный IN_PROGRESS/branch/base/paths; после каждого среза новый audit, PR→develop, merge commit. Старые audits сохранены.

[ROADMAP v3](../../ROADMAP.md), [STATE](../STATE.md), [повторная ревизия](../../docs/reviews/2026-10-09-integration-review.md), [handoffs](../../docs/architecture/runtime-handoffs.md).
