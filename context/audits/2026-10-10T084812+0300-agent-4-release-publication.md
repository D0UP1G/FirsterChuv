# Agent 4 · release 0.1.0 publication checkpoint · 2026-10-10 08:48 +0300

Связанный audit подготовки: [release 0.1.0](2026-10-10T084331+0300-agent-4-release-0.1.0.md).

## Публикация в main

- Release PR [#101](https://github.com/D0UP1G/FirsterChuv/pull/101) обычным merge смёржен в `main`.
- Release head: `24065e01dfa6c5e89bd0dc98afc322ac576c1708`; merge commit: `5056e65778e5faf047270f481290561a88fd6d55`.
- Все 5 GitHub CI jobs на exact release head SUCCESS: backend, contracts-and-common-imports, domain, frontend, sandbox-unit.
- Annotated tag `v0.1.0` создан на release merge commit `5056e65778e5faf047270f481290561a88fd6d55` и проверен через `git ls-remote --tags`.
- `origin/main` подтверждён на `5056e65778e5faf047270f481290561a88fd6d55`; `origin/develop` пока `d524343f75149e624d56e4970cd059d6216e1f5b`.

## Оставшееся

- Создать PR с main release в develop, проверить точный head и выполнить ordinary merge.
- Удалить после release только 95 remote `feature/*`, чьи commits уже вошли в develop; сохранить все неслитые refs и базовые ветки. Локальные ветки attached к checkout/worktree не удалять.
- Acceptance limitations из `docs/releases/0.1.0.md` остаются в силе; релиз не объявляет M0/M1/M2 принятыми.
