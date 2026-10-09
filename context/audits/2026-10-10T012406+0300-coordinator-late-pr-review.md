# Аудит координатора: поздние PR и финальная очередь MVP

- Дата: 2026-10-10T01:24:06+03:00, Europe/Moscow.
- Задача: прямое поручение команды проверить все новые PR, merge только готовых, создать frontend owner и распределить оставшийся MVP.
- Branch: feature/mvp-readiness-handoff; base cc204e62a060eb2ceb16067a1b0693a2e083d9ab.
- Статус: IN_REVIEW перед публикацией. Не утверждает MERGED или полный R1.
- Пути: собственный audit/card, ROADMAP/STATE/review/owner handoff; source #54/#56 ordinary merge. Чужие checkout/branches не изменены.

## Поздние heads

- #54 86208d54846377bba1f61f079081edf011f6a711 APPROVE reference: black-page/grid-in-elements и text spacing, только design HTML/CSS/own audit. Inert auth fix coordinator сохранён: 5 disabled fields, 2 type=button, HTMLParser PASS; script/iframe отсутствуют. Изменения source code backend/frontend/src нулевые. Новый source audit сохранён.
- #56 3e99ae5368fd177f8342d49878ef137cd31974d9 APPROVE: Markdown brandbook/reference links/new own audit. Extraneous shop/chat/hints/achievements/code view не назначены в MVP, privacy не отменена. Original Google Docs equivalence — заявление автора, внешний оригинал в этой ревизии не проверялся.
- #57 0073fbd96d38f657368ffa318d6ca23bff5f8a2d REQUEST_CHANGES: ORM catalog read перед первым write внутри atomic config.
- #58 1f3fae5fc3ee70ab4e2bff713fd3a6cd7439d6a8 REQUEST_CHANGES: accepted/result read→write races; historical participants читаются из mutable MatchSlot, late old result после replacement не сохраняется.
- #59 сначала 5c32c474d4620e21ff1aab15ab98c8ba28b7852e, затем 7465a9c3ca0110a93bb5f8e5a4c63aecf80b42b8 REQUEST_CHANGES: same-key command read→write race осталась. Последний добавил technical/rematch; эти функции не объявлены accepted, replacement/full HTTP ещё нет.
- #53 fd79038847a23b38bb8a444c028b87ce75ed9571 REQUEST_CHANGES подтверждён прежде в этой же ревизии, не включён. Snapshot concurrent cursor loss/equal-run overwrite — first READY A4.

#57–59 source bases feature, source checks отсутствуют. После #50 в develop retarget PR→develop согласуется с GitFlow и не требует force push; неисправленный код не merge даже при зелёном CI.

## Проверки и все попытки поздней проверки

Combined production code PASS уже записан в [предыдущем собственном audit](2026-10-10T011516+0300-coordinator-mvp-readiness-review.md): backend255/4skips, draft18 и bracket24 file-backed, frontend82, domain68/sandbox15/schema9/import/check/drift.

Late #57–59 initial source tests13 PASS; latest #59: команда ниже с DJANGO_DEBUG=true, 16/16 PASS, 19.122s. Первый повтор без test settings остановился на DJANGO_SECRET_KEY guard; это setup error, не продуктовая ошибка. Первый повтор probe использовал прежнюю disposable DB и остановился на duplicate synthetic account; fresh DB ниже дал завершённый результат. Ни одна неуспешная попытка не скрывается как PASS.

```text
CONFIGURE_ORM_CATALOG_RACE: один ok, один OperationalError(database is locked)
ACCEPTED_RACE: один ok, один OperationalError(database is locked), ACCEPTED_ROWS=1
RESULT_RACE: один ok, один OperationalError(database is locked), RESULT_ROWS=1
ADMIN_SAME_KEY_RACE: один ok, один OperationalError(database is locked), ADMIN_ROWS=1
OLD_RESULT_AFTER_REPLACEMENT: LedgerPersistenceError(stored receipts violate run ledger invariants)
OLD_RESULT_STORED=False
```

SQLite настоящая файловая, отдельные connections/threads, timeout0.2. Barrier поставлен после фактического ORM SELECT, не подменяет SQL lock exception. ORM catalog read соответствует допустимому реальному producer. Replacement моделирован в disposable DB новым entrant; accepted original run не меняется. Никакой пользовательский код/hostile execution не выполнялся.

## Воспроизведение source-only probe

Export exact #59 latest (включает #57/#58 ancestry) в отдельный временный каталог. Установленный trusted Django runtime используется как обычное test окружение. Все test accounts synthetic; путь probe DB должен быть новым при каждом запуске. Запуск tests:

```bash
DJANGO_DEBUG=true python manage.py test backend.apps.competition.tests.test_runtime backend.apps.competition.tests.test_ledger_persistence backend.apps.competition.tests.test_admin_runtime --noinput
```

Ниже полный разовый probe; выполняется из корня export, не из production checkout. Никогда не направлять SQLITE_PATH в реальную DB.

```python
import os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())
os.environ['DJANGO_SETTINGS_MODULE']='backend.config.settings'
os.environ['DJANGO_DEBUG']='true'
os.environ['SQLITE_PATH']='/tmp/firster-review4-runtime/probe-runtime-7465a9c.sqlite3'
os.environ['SQLITE_TIMEOUT']='0.2'
import django
django.setup()
from django.core.management import call_command
from django.db import connections, close_old_connections
from django.db.models.query import QuerySet
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from unittest.mock import patch
from uuid import uuid4
from datetime import timedelta
from backend.apps.competition.tests.test_runtime import PersistedMatchRuntimeTests, TestCatalog
from backend.apps.competition.tests.test_ledger_persistence import PersistedLedgerTests, START
from backend.apps.competition.runtime import configure_match_run
from backend.apps.competition.ledger_persistence import register_accepted, apply_result
from backend.apps.competition.admin_runtime import execute_match_admin_command
from backend.apps.competition.domain.scoring import Verdict
from backend.apps.competition.models import Match, MatchRun, MatchSlot, AcceptedAttempt, AttemptResult, MatchAdminCommandReceipt
from backend.apps.accounts.models import User
from backend.apps.tournaments.models import TournamentParticipant
call_command('migrate',verbosity=0)
fixture=PersistedMatchRuntimeTests();fixture.setUp()
barrier=Barrier(2)
class ReadingCatalog(TestCatalog):
 def describe_ready(self, problem_ids):
  Match.objects.filter(pk=fixture.match.pk).exists()
  barrier.wait(timeout=5)
  return super().describe_ready(problem_ids)
def guarded(fn):
 close_old_connections()
 try:return ('ok', str(fn()))
 except Exception as e:return(type(e).__name__,str(e))
 finally:connections.close_all()
def configure(_):
 return guarded(lambda:configure_match_run(fixture.match.pk,problem_ids=[fixture.problem_id],allowed_duration_ms=600000,start_mode='manual',scoring_rule=None,catalog=ReadingCatalog(fixture.problem_id)))
with ThreadPoolExecutor(max_workers=2) as pool: print('CONFIGURE_ORM_CATALOG_RACE',list(pool.map(configure,range(2))))
ledger=PersistedLedgerTests();ledger.setUp()
original_first=QuerySet.first
def synchronized_first_for(model):
 b=Barrier(2);state=local()
 def read(qs):
  value=original_first(qs)
  if qs.model is model and not getattr(state,'synced',False):
   state.synced=True;b.wait(timeout=5)
  return value
 return read
receipts=[ledger.accepted(elapsed=10000),ledger.accepted(elapsed=20000)]
with patch.object(QuerySet,'first',synchronized_first_for(AcceptedAttempt)):
 with ThreadPoolExecutor(max_workers=2) as pool:
  print('ACCEPTED_RACE',list(pool.map(lambda r:guarded(lambda:register_accepted(r)),receipts)))
print('ACCEPTED_ROWS',AcceptedAttempt.objects.filter(run_id=ledger.run.pk).count())
# Ensure both accepted receipts exist before concurrent result delivery.
for r in receipts:register_accepted(r)
results=[ledger.result(r,Verdict.OK) for r in receipts]
with patch.object(QuerySet,'first',synchronized_first_for(AcceptedAttempt)):
 with ThreadPoolExecutor(max_workers=2) as pool:
  print('RESULT_RACE',list(pool.map(lambda r:guarded(lambda:apply_result(r)),results)))
print('RESULT_ROWS',AttemptResult.objects.filter(accepted__run_id=ledger.run.pk).count())
admin=User.objects.get(email='ledger-admin@example.test')
with patch.object(QuerySet,'first',synchronized_first_for(MatchAdminCommandReceipt)):
 with ThreadPoolExecutor(max_workers=2) as pool:
  print('ADMIN_SAME_KEY_RACE',list(pool.map(lambda _:guarded(lambda:execute_match_admin_command(actor_user_id=admin.pk,match_id=ledger.match.pk,command_id='review-extension-same-key',action='extend',reason='bounded review',seconds=60,now=START+timedelta(seconds=30))),range(2))))
print('ADMIN_ROWS',MatchAdminCommandReceipt.objects.filter(command_id='review-extension-same-key').count())
# Old accepted receipt without result must remain resolvable after participant replacement.
old=ledger.accepted(elapsed=30000);register_accepted(old)
third=User.objects.create_user(email='replacement-review@example.test',display_name='Replacement')
entry=TournamentParticipant.objects.create(tournament_id=ledger.match.tournament_id,user=third,status='active')
slot=MatchSlot.objects.get(match_id=ledger.match.pk,participant__user_id=ledger.players[0].pk)
slot.participant=entry;slot.save(update_fields=['participant'])
replacement=MatchRun.objects.create(match=ledger.match,sequence=2,status='READY',allowed_duration_ms=600000,score_rule=ledger.run.score_rule,start_mode=ledger.run.start_mode,problem_versions=ledger.run.problem_versions,scoring_version=ledger.run.scoring_version)
Match.objects.filter(pk=ledger.match.pk).update(current_run=replacement,status='READY')
print('OLD_RESULT_AFTER_REPLACEMENT',guarded(lambda:apply_result(ledger.result(old,Verdict.OK))))
print('OLD_RESULT_STORED',AttemptResult.objects.filter(accepted_id=old.submission_id).exists())

```

## Сохранение аудитной истории

Проверка всех148 audit blobs current base: изменений0. Новые source-only audit blobs совпадают. В #51 старый blob `context/audits/2026-10-10T001529+0300-agent-4-P4-06-draft-reconnect-audit-publication.md` отличается от base cc204e6 уже до нашей работы. Current base сохранён, старый source blob достижим через обычную merge ancestry. Проверка всех взаимоисключающих старых blobs на одинаковое содержимое дала ложную ошибку integrity; исправлено правило сравнения: current base exact + new source exact + historical source ancestry. Coordinator чужой audit не переписывал.

## Параллельный план и следующий шаг

A1 contracts/access/build, A2 reviewed persistence fixes→HTTP/gateway/failure/finalization, A3 actual executor/workspace/import/fencing, A4 snapshots/producers/SSE/system evidence, A5 full frontend/design/real per-endpoint CONNECT. У всех READY резерв; WAITING только конкретного adapter. A5 thread 01a122b2-27f9-7af0-ab77-dd282807d489 active, own clone/feature, runtime готовность не подтверждена.

Опубликовать coordinator feature→develop, дождаться 5 checks на точном SHA, проверить fresh base/source refs и merge commit; затем remote/ancestry/source PR states. #53/#57–59 остаются open до correctness fix. Source branch refs/main не удалять/переписывать. Полный кейс/официальный пакет/Docker hostile/browser/demo в этой поздней проверке NOT_RUN; R1 ещё не accepted.
