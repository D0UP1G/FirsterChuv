# Внутренний формат ProblemBundleV1

Модуль `problems` хранит неизменяемые версии задач и предоставляет порт `ProblemCatalogV1`. Это внутренний нормализованный формат FirsterChuv для MVP, а не формат архива организаторов и не описание API Яндекс Контеста. Внешнее сопоставление будет добавлено отдельным P3-06 только по предоставленному README пакета.

## Формат синтетического архива

Архив ZIP содержит `manifest.json` версии `schemaVersion: 1`, необязательные публичные файлы `public/assets/*` и закрытые файлы `private/tests/*`, `private/checkers/*`, `private/validators/*`, `private/references/*`. Точный пример создаётся в unit tests, а не позиционируется как официальный пакет.

Manifest разделяет `public` и `private`. Public содержит label/title/statement Markdown/assets/examples/limits и language IDs с шаблонами. Private описывает входы и ожидаемые ответы тестов, checker, validator и reference solution; для каждого кода сохраняются source path и language ID. В metadata языка разрешён только ID из серверного registry; image, argv и пути компилятора архив задавать не может. Сейчас зарегистрирован только `cpp20`, с серверными image/argv из sandbox harness. Запись compiler spec пока `verified=False`: до реального Docker runtime proof production catalog оставляет такие версии `NOT_READY`.

Минимальная форма внутреннего manifest (значения демонстрационные):

```json
{
  "schemaVersion": 1,
  "problemId": "00000000-0000-0000-0000-000000000040",
  "version": "synthetic-v1",
  "public": {
    "label": "A",
    "title": "Синтетическая задача",
    "statementMarkdown": "Найдите сумму.",
    "assets": [],
    "examples": [{"input": "2 3\n", "output": "5\n"}],
    "limits": {"timeLimitMs": 2000, "memoryLimitBytes": 536870912},
    "languages": [{"id": "cpp20"}]
  },
  "private": {
    "tests": [{"inputPath": "private/tests/001.in", "expectedOutputPath": "private/tests/001.out"}],
    "checkerPath": null,
    "checkerLanguageId": null,
    "validatorPath": null,
    "validatorLanguageId": null,
    "referenceSolutionPath": null,
    "referenceSolutionLanguageId": null
  }
}
```

Публичные assets принимаются только как PNG/JPEG/WebP с совпадающими расширением, заявленным MIME и сигнатурой; SVG/HTML и активные типы не принимаются. Private bytes хранятся отдельно от public metadata и не входят в `PublicProblemVersion`. Checker/reference/validator только хранятся и не запускаются этим importer-ом.

## Безопасное чтение и готовность

ZIP читается ограниченными порциями и никогда не извлекается на файловую систему; пути и метаданные ссылок не преобразуются в hardlink/symlink на host. По умолчанию действуют caps: архив 16 MiB сжатых данных, 4096 записей, один файл 8 MiB, всего 64 MiB распакованных данных, ratio 100:1. Поддерживаются только ZIP Stored/Deflate. Абсолютные/parent/backslash/drive пути, дубликаты (включая регистровые), зашифрованные, символьные ссылки и специальные Unix-типы отклоняются. Локальные caps — эксплуатационные ограничения импортера, а не заявления о формате организаторов.

Внутренний checksum вычисляется по canonical JSON manifest и всем файлам с путями и не публикуется в public DTO; `(problemId, version)` уникальна и immutable. Повтор той же версии и checksum идемпотентен; иной checksum для уже существующей версии — конфликт. Первая полностью проверенная READY версия становится активной. Public catalog перечисляет только активные READY версии; `load_bundle` возвращает private data только доверенному judge-коду. Без тестов либо без expected output/checker версия сохраняется как `NOT_READY` и catalog её не выдаёт.

Архивы в tests синтетические. Тесты могут передать verified test compiler, чтобы проверить переход catalog в READY; это не меняет production registry и не подменяет запуск/вердикт. Архивы не покрывают официальный package import и не закрывают T12/T20.
