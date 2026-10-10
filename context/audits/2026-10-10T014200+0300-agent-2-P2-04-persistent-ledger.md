# Agent 2 audit — P2-04 persistent attempt/result receipts

## Scope

Adds a durable Django adapter around the existing pure accepted/result ledger. This stacked slice depends on P2-02 bracket persistence and P2-03 run configuration/readiness.

## Changes

- Added append-only accepted attempt and one-to-one verdict result tables, with a globally unique submission identity.
- Persisted scoring contract version and current score snapshot on MatchRun.
- `register_accepted` validates the current RUNNING run, participant/problem membership, scoring version and exact server elapsed time; exact retry is idempotent and conflicting identity is rejected.
- `apply_result` validates against the immutable accepted receipt, records exact verdict retries once, recomputes score through the pure domain core, and does not mutate score for superseded runs.
- SQLite first-write reservation and atomic boundaries serialize receipt updates with current-run transitions.

## Verification

- Focused persistence + pure ledger tests: 25 passed.
- Full backend suite: 246 passed, 2 skipped.
- Migration drift: clean.
- Django check: clean.
- `compileall` and `git diff --check`: clean.

## Boundary

FINALIZING drain policy, infrastructure-failure receipt/outbox, score-to-bracket downstream transitions, events, and HTTP/worker adapters remain follow-up slices.
