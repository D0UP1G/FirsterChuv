# Agent 2 audit — P2-05 technical result and rematch persistence

Extended the persisted admin command service with two domain actions:

- Technical result validates an active match participant winner, stores the reason/winner on run and match, and advances the winner into the reserved downstream slot atomically. Started downstream matches are rejected by the pure guard.
- Rematch marks the old run SUPERSEDED and creates a clean READY run with a new sequence, pinned config, and empty score snapshot. The durable command receipt remains attached to the superseded run while its response identifies the new run.
- Exact retries replay the first response; changes to winner/reason/action conflict under the same command ID.

## Verification

- Focused admin runtime + pure guard tests: 27 passed.
- Full backend suite: 253 passed, 2 skipped.
- Migration drift: clean.
- Django check: clean.
- `compileall` and `git diff --check`: clean.
