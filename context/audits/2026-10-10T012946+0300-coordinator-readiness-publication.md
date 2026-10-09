# Аудит координатора: публикация #60 и поздние обновления

- Время: 2026-10-10T01:29:46+03:00, Europe/Moscow.
- Branch: feature/mvp-readiness-handoff; base cc204e62a060eb2ceb16067a1b0693a2e083d9ab.
- PR: https://github.com/D0UP1G/FirsterChuv/pull/60, attached к задаче.
- Scope: latest design merge, own review/roadmap/card checkpoints, actual editor decision; original author audits immutable.
- Статус: IN_REVIEW до окончательного exact-head CI/MERGED. Main/source refs не изменялись.

## Публикация и gate

Remote head014c98f13a1f2be84980fd83ed9c117fdfb5d448 проверен gh и git ls-remote. Первый [CI37999339340](https://github.com/D0UP1G/FirsterChuv/actions/runs/37999339340) завершился5/5 SUCCESS: frontend/backend/domain/sandbox-unit/contracts-and-common-imports. После latest source54/docs новый SHA публикуется и проходит собственный CI до merge; прежний PASS не используется как gate для другого SHA.

Все148 audit blobs current base сохранены exact,13 новых source-only на014c98f сохранены exact. 30 roadmap parent IDs включают все24 прежних,37 requirements и21 acceptance сохранены; case SHA256 совпадает. Backend events/problems/submissions/judge/services и frontend/src не меняются этой ревизией, кроме source competition#50/drafts#21 и own static auth/CI correction. Copy roadmap в docs/history первоначально имел root-relative links; link check выявил9 dangling targets, только пути ссылок rebased ../../ и снапшот помечен. Последующий check PASS. Одна синтаксическая ошибка разового link-fix script остановила его до edits; исправленный script завершился.

## Самый поздний проверенный runtime head

#59 latest9eb394c88c64b1d22d90685c2eb44d946f91d755 добавил real participant replacement, migration0006 participant_user_ids и frozen snapshot. Exact export source tests19/19 PASS (19.276s), Django check0. Повтор четырёх file-backed races прежнего audit: configure/accepted/result/same-command дают один success и один uncaught OperationalError(database is locked), по одной receipt/result строке. Historical replacement probe теперь PASS: old result saved=True, current score untouched (False). Старый #58 defect исправлен в leaf #59, сохранить fix при sync.

Новый probe на том же exact export: source fixture создаёт4-player bracket, technical winner первого semi проходит в next slot; допустимый rematch до старта next создаёт новый READY run, но старый winner остаётся downstream PLAYER. Повторный technical winner другого участника не может пройти, команда rollback с AdminCommandPersistenceError(downstream slot is no longer available for winner advancement). Нужны revoke/reopen unstarted downstream projection в той же transaction и advancement/started guard tests. Ни #57/#58/#59/latest head не merged в coordinator feature.

```text
UPSTREAM_AFTER_REMATCH READY
DOWNSTREAM_RESOLUTION PLAYER
OLD_WINNER_STILL_ADVANCED True
NEW_WINNER_ADVANCEMENT AdminCommandPersistenceError downstream slot is no longer available for winner advancement
```

Дополнительный разовый probe ниже. Работать только из temporary exact export, SQLITE_PATH должен быть новым disposable file, participant code не исполняется:

```python
import os,sys
sys.path.insert(0,os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE']='backend.config.settings'
os.environ['DJANGO_DEBUG']='true'
os.environ['SQLITE_PATH']='/tmp/firster-review4-runtime-9eb394c/probe-downstream.sqlite3'
import django
django.setup()
from django.core.management import call_command
from datetime import timedelta
from backend.apps.competition.tests.test_admin_runtime import PersistedAdminClockCommandsTests, START
from backend.apps.competition.models import Match,MatchSlot
from backend.apps.competition.runtime import start_match_run
from backend.apps.competition.admin_runtime import execute_match_admin_command
call_command('migrate',verbosity=0)
f=PersistedAdminClockCommandsTests();f.setUp()
f.test_technical_winner_advances_into_the_reserved_downstream_slot()
m=Match.objects.get(tournament__title='Four player actions',status='FINISHED',round_index=0)
slot=MatchSlot.objects.get(match_id=m.next_match_id,slot_index=m.next_slot)
original_winner=slot.participant_id
execute_match_admin_command(actor_user_id=f.admin.pk,match_id=m.pk,command_id='review-rematch-finished',action='rematch',reason='Review before final',now=START+timedelta(seconds=60))
m.refresh_from_db();slot.refresh_from_db()
print('UPSTREAM_AFTER_REMATCH',m.status,'DOWNSTREAM_RESOLUTION',slot.resolution,'OLD_WINNER_STILL_ADVANCED',slot.participant_id==original_winner)
start_match_run(m.current_run_id,now=START+timedelta(seconds=70))
new_winner=m.slots.exclude(participant_id=original_winner).get().participant.user_id
try:
 execute_match_admin_command(actor_user_id=f.admin.pk,match_id=m.pk,command_id='review-second-winner',action='technical_result',reason='New result',winner_user_id=new_winner,now=START+timedelta(seconds=80))
 print('NEW_WINNER_ADVANCEMENT','ok')
except Exception as error: print('NEW_WINNER_ADVANCEMENT',type(error).__name__,str(error))

```

## Latest design и документация

#54 94d42a0026c1b9c0c3b61ddf4ce3c25ac1ff4f8b: CSS19 строк horizontal nesting, README и new own audit; HTML diff только CSS classes (механическое сравнение после удаления class attrs PASS). Source merged ordinary, own disabled auth/type=button retained. Further source updates после этого checkpoint не считаются автоматически reviewed. Применение к React — A5.

README/ADR09 перестают рекомендовать первоначальный Monaco: наблюдаемый CodeMirror 6 фиксируется ADR21 IMPLEMENTED; нет нового решения о смене stack.

A5 thread first turn completed/idle: own auth-return-path slice и84 tests заявлены автором, всё пока local/uncommitted, coordinator не выдаёт чужой невлитый код за accepted. Merge #60 снимает только handoff prerequisite; затем продолжение brand/auth/responsive/per-endpoint READY очереди, без ожидания всего backend.

## Следующее

Опубликовать final head #60, дождаться5/5 CI на том же SHA и fresh base, merge --merge с matching HEAD. Проверить remote parents/selected ancestry/excluded absence/main/PR states. #57–59 привести base к develop после availability #50 без переписывания code refs; unsafe heads оставить OPEN. A5 получает available handoff и продолжает работу. Полный working MVP ещёNOT_ACCEPTED; official package/real hostile/browser/demo evidence не подменяются CI.
