# Состояние интеграции

Обновлено: `2026-10-09T15:50:25+03:00`. Ответственный за дальнейшее обновление: агент 1.

## Проверенный статус

GitFlow начат пустым корневым commit `e9fc0ef` на `main`; документация интегрирована PR #1. Bootstrap A1-01 принят PR #2, account/auth A1-02 — PR #5, tournament/roster A1-03 — PR #8. Проверенный текущий `develop`: merge SHA `b8947165ac08792751aa34e8a97c9c38ae11b17c`. После PR #8 на этом merged SHA прошли 37 backend tests, Django system check и migration drift check. Это частичная backend evidence, не полные T03/T05/T20 или T01.

| Компонент | Статус | Доказательство |
|---|---|---|
| Требования, архитектура, план агентов | В `develop` | PR #1, merge в `e5f421b` |
| PDF кейса | В `develop` | `docs/source/Кейс_Платформа_соревнований.pdf`; SHA-256 записан в `docs/source/README.md` |
| Django/DRF backend bootstrap | В `develop` | PR #2, merge SHA `2484d86`; custom User, общие contracts, health/error handling |
| Auth, register/login/CSRF, account permissions, bootstrap admin | В `develop` | PR #5, merge SHA `c64555c`; 16 account/common tests и post-merge checks; полные T02/T20 открыты |
| Tournament CRUD и roster | В `develop` | PR #8, merge SHA `b894716`; после merge 37 backend tests, `manage.py check`, migration drift check; полный T03/T05 открыт |
| Tournament invites | Не реализованы | Следующая задача Agent 1: A1-04 на отдельной feature-ветке от актуального `origin/develop` |
| Сетка, match-clock, score/advancement | Не интегрированы | Владение агента 2; PR #7 открыт, feature SHA `db67be4`; не менять чужую ветку |
| Sandbox/judge runtime | Не интегрирован | PR #3 агента 3 открыт; feature SHA `3a0d865`; T18/T20 и продуктовую приёмку не утверждать |
| Frontend | Не реализован | Владение агента 4; отдельные feature changes не интегрированы |
| CI | Не настроен | GitHub PR #8 имеет пустой `statusCheckRollup`; branch protection для `develop` не настроена |
| Official package и его README | Не получены | Нужны для реальных условий/checkers и полной проверки T12/T14/T21 |
| Полная T01/T02/T20 и demo/video | Не пройдены | Есть только ограниченные backend/account checks; сквозной сценарий не запускался |

## Подтверждённые remote refs

Проверено `2026-10-09T15:50:25+03:00` через `git ls-remote origin` и GitHub PR API; PR #8 имеет статус `MERGED`, merge SHA `b8947165ac08792751aa34e8a97c9c38ae11b17c`; PR #7 и #3 остаются `OPEN`.

- `main`: `e9fc0ef97dcb83d2beffa41f42cb873ebcde71bc` — пустая начальная инициализация.
- `develop`: `b8947165ac08792751aa34e8a97c9c38ae11b17c` — включает PR #1, A1-01 PR #2, state sync PR #4, A1-02 PR #5, state sync PR #6 и A1-03 PR #8.
- `feature/docs-mvp-context`: `edd10ea2c5cb1db8a885cd052e4425cb48d2faed`; PR #1 merged, ref сохранена.
- `feature/platform-bootstrap`: `ccf8eeac09df34e8df836541c529e68c846825d9`; PR #2 merged в `develop`, ref сохранена.
- `feature/a1-01-state-sync`: `7e10d0dc446e9e0a22a7d0ed768b3e585f642812`; PR #4 merged в `develop`, ref сохранена.
- `feature/account-roles`: `3b1be0c2e5580a2bae629c05278f8dfc8c08da90`; PR #5 merged в `develop` merge commit `c64555c`, ref сохранена.
- `feature/a1-02-state-sync`: `5885984664b76de68f6a3f32a53ff96ec66edc40`; PR #6 merged в `develop`, ref сохранена.
- `feature/tournament-roster`: `5163f6ceb8753b355efcfa113a71f746ff4e6618`; PR #8 merged в `develop` merge commit `b894716`, ref сохранена.
- `feature/bracket-runtime`: `db67be465c9d3ef07dc60211ec2ea975d31c6541`; принадлежит агенту 2, PR #7 открыт и не интегрирован в указанный SHA.
- `feature/sandbox-proof`: `3a0d86503b22b95b5004625ef8998cd1cc4c11c3`; принадлежит агенту 3, PR #3 открыт и не интегрирован в указанный SHA.

Снимок относится к указанным времени и SHA и не заменяет повторную проверку refs перед merge/release. `main` ещё не содержит выпуска MVP.

## Следующие действия

1. Открыть отдельный PR текущей A1-03 STATE sync ветки в `develop`; после его merge начать A1-04 в `feature/tournament-invites` от актуального `origin/develop`.
2. Реализовать безопасные invite token, expiry/maxUses/revoke и транзакционный идемпотентный accept; проверить T04, включая concurrent use/cap.
3. Полные T03/T05 требуют browser acceptance и интеграции с реальным bracket/Match history; partial evidence A1-03 не считать полным pass.
4. Полный `T02` требует полного registration/invite/admin browser flow. Полный `T20` требует также IDOR, XSS/SQL/CSRF/SSRF/archive/command, runtime isolation и leakage checks; account audit содержит только partial evidence.
5. Интегрировать PR других агентов только после owner review, сверки миграций/contracts и доступных checks; не менять чужие ветки. Сквозной полуфинал → финал пока не выполнялся.
6. Официальный package, demo и видео, полная матрица T01–T21 и release gate остаются обязательными до `release/0.1.0`/`v0.1.0`.

## Блокеры

Official package и README формата не предоставлены. Это блокирует проверку настоящих условий/checkers и финальную judge/demo приёмку, но не A1-03/A1-04. PR #3 sandbox proof всё ещё открыт; сам по себе он не закрывает T18/T20. Яндекс Контест остаётся только опцией импорта и не заменяет локальный пакет или собственную песочницу.

Не менять статус компонента на «готов», если есть только документация, mock или несмерженная feature-ветка. Указывать SHA, PR и воспроизводимую проверку после интеграции.
