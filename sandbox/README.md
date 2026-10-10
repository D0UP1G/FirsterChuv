# A3-01: изолированный smoke-runner

Это собственный Docker исполнитель для P3-01 и sandbox backend LocalJudge. Он не заменяет package importer, API или durable worker.

## Текущая поддержка

- Язык: C++20, compiler `g++ 14.2.0` из официального `docker.io/library/gcc:14.2.0-bookworm`.
- Базовый amd64 OCI manifest закреплён в `Dockerfile` digest `sha256:82549aa8f90ada3236a8be70c74543132a76662ef33f0c3271ed802b81584a82`.
- Другие языки не объявлены: официальный пакет задач и его README ещё не предоставлены.
- Fixtures — собственная smoke-задача. Они не выдаются за пакет организаторов и не закрывают проверку официальной задачи.

## Ограничения запуска

Исходник компилируется в отдельном контейнере. Его ограниченный исполняемый артефакт возвращается host runner-у по stdout, затем для каждого теста создаётся новый контейнер с уникальным именем и ему передаются только артефакт и один тестовый ввод через stdin. Ожидаемый ответ остаётся снаружи контейнеров. В команду Docker не попадают аргументы, image, путь или argv от участника.

Контейнер запускается с:

- `--network=none`, PID namespace Docker по умолчанию и Docker default seccomp profile; PID-флаг намеренно не передаётся, поскольку используемый Docker CLI не принимает `--pid=private`;
- read-only root filesystem и одним исполняемым tmpfs `/work` размером 64 MiB;
- UID/GID `65534:65534`, `cap-drop=ALL`, `no-new-privileges`;
- compile контейнер: 512 MiB memory без swap, один CPU и 64 процесса; compile wall cap 15 секунд;
- run контейнер: task time/memory limits из trusted normalized bundle, строго в диапазонах 1–120 000 ms и 32–512 MiB; memory ограничивается Docker cgroup без swap, один CPU и 64 процесса остаются service caps;
- внешний run watchdog добавляет не более 5 секунд к task time limit; service caps: source 32 KiB, test input 8 MiB, stdout/stderr file 32 KiB.

Команда создания контейнера не монтирует каталоги host, пакет тестов, Docker socket или переменные окружения хоста. Решение видит только собственный исходник и текущий ввод; эталонный ответ и остальные тесты остаются снаружи. `docker rm --force` получает только ID/name, созданный текущим запуском; глобальная очистка не используется. Ошибка Docker/протокола возвращается как инфраструктурный отказ, а не как verdict.

Supervisor отключает dumpability через `PR_SET_DUMPABLE` до чтения запроса и запуска дочернего процесса. Это закрывает same-UID доступ решения к `/proc/1/fd/1`, где находится stdout JSON-протокола. Smoke case `protocol-write` проверяет, что попытка открыть этот канал блокируется. Host runner читает stdout/stderr Docker CLI одновременно ограниченными порциями: stdout ограничен размером протокольного ответа 12 MiB, stderr — 64 KiB. При превышении лимита runner завершает только свой Docker CLI и затем удаляет только созданный им контейнер.

Образ собирается заранее доверенным оператором из закреплённого base digest. Запуск использует `--pull=never`: отсутствующий локальный build приводит к ошибке инфраструктуры, а не к неявному скачиванию образа при выполнении решения.

## Сборка и запуск

Требуется активный Docker Engine с cgroups/лимитами. Проверка пока не запускалась: в checkout-хосте Docker CLI есть, но daemon/socket недоступны.

```bash
docker build --platform=linux/amd64 --tag firsterchuv/sandbox-cpp:0.1.0 sandbox
python3 sandbox/smoke.py --case all
```

Ожидаемое поведение при успешном реальном выполнении: `ok: OK`, `wa: WA`, `timeout: TIME_LIMIT`, `output-limit: OUTPUT_LIMIT`, `protocol-write: BLOCKED`. Этот harness не может напечатать такой результат без успешного выполнения настоящего контейнера. При недоступности Engine пишет `NOT_VERIFIED` и завершается с кодом 2.

## Граница доказательства и угрозы

Здесь проверяются реальные compile/run smoke cases, включая ограниченный доступ к управляющему stdout, и видимые параметры запуска Docker. Unit tests проверяют ограничение потоков на host runner-е отдельными доверенными дочерними процессами; они не подменяют Docker. Компилятор и каждая тестовая попытка находятся в отдельных контейнерах; host runner передаёт артефакт между ними, но не запускает его на хосте. Фактическую PID-настройку контейнера, CPU/RAM/PID, отсутствие сети и host/secret доступа нужно подтвердить hostile checks и Engine inspect на доступном Docker Engine. Эти проверки в текущем checkout-хосте не выполнены: daemon/socket недоступны. `KILLED_UNKNOWN` становится ML только при `Docker inspect .State.OOMKilled=true`; необъяснённый kill остаётся infrastructure error.

LocalJudge повторно использует runner для реального compile/run и передаёт лимиты конкретной нормализованной версии задачи. Docker proof не запускался в этом checkout: daemon/socket недоступны; перед runtime readiness нужно собрать образ и выполнить smoke плюс gated judge integration test. Официальный пакет не найден в репозитории. До получения его README формат импорта, checker protocol, verdict codes и package commands не предполагаются. Синтетический smoke не закрывает official T12/T14/T21 и hostile T18/T20.
