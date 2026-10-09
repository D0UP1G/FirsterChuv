# LocalJudge

`LocalJudge` реализует `JudgeProvider.execute(TrustedJudgeJob)` для внутреннего
`ProblemBundleV1`. Он загружает точную пару `problemId/version`, сверяет
checksum с принятым заданием и использует только server-owned compiler
registry. В manifest нельзя задать image или команду компилятора.

Все compile/run операции идут через `backend.apps.judge.runner.DockerRunner`;
корневой `sandbox/runner.py` оставлен тонким compatibility import для smoke CLI.
Код решения никогда не запускается в API/worker Python-процессе. Каждый тест
получает новый контейнер. Для запуска берутся task `timeLimitMs` и `memoryLimitBytes`, с
верхними границами sandbox: 120 секунд и 512 MiB на тест, минимум 32 MiB;
общий предел времени одной проверки — 5 минут. Сеть, процессы, stdout/stderr, артефакт,
wall watchdog и cleanup имеют ограничения sandbox. ML выдаётся только когда
Docker подтверждает OOM; необъяснённый SIGKILL
является инфраструктурной ошибкой.

Вызов выполняет только trusted worker вне DB write transaction. Текущий Compose
ещё не предоставляет worker Docker CLI/Engine access; это остаётся P3-04.2 и
P1-04 integration work. При отсутствии CLI/Engine `DockerRunner` возвращает
typed infrastructure failure.

Без checker LocalJudge сравнивает stdout с внутренним synthetic expected output
побайтно. Это не заменяет checker для задач с несколькими правильными ответами.
Хотя ProblemBundleV1 уже хранит private checker source, формат его запуска и
значения ответа должны быть взяты из README официального пакета. Пока README не
получен, такой job завершается typed infrastructure error, а не WA/RE.

`cpp20` остаётся `verified=False`, пока не пройдёт реальный Docker smoke.
После сборки закреплённого image проверить sandbox командами из
`sandbox/README.md` и выполнить gated integration test. Только после успешных
реальных compile/run и проверки Docker limits/cleanup владелец может отметить
compiler spec verified в `backend/apps/problems/compilers.py`:

```bash
FIRSTERCHUV_REAL_JUDGE_SMOKE=1 DJANGO_DEBUG=true uv run --project . python manage.py test backend.apps.judge.tests.test_real_smoke --verbosity 2
```

Этот smoke программно сохраняет синтетический normalized bundle и реально
компилирует/запускает решение через Docker. Он не является official package
acceptance и не закрывает T12/T14/T18/T20/T21.
