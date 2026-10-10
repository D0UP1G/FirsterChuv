# Agent 2 audit — P2-05 persisted pause/resume/extend

## Scope

Adds the first persisted P2-05 admin-action slice: pause, resume, and bounded duration extension with trusted admin checks, pure transition guards, and durable idempotency receipts.

## Changes

- Added a unique `(match, command_id)` receipt model storing the trusted actor, intent fingerprint, action, reason, and exact response.
- Added atomic service methods for pause/resume and duration extension; run effect and receipt commit together.
- Retries replay the first response before checking the current run state; reused command IDs with different intent conflict.
- Uses the same run-then-match write reservation order as readiness and result persistence.
- Maximum per-command extension is 600 seconds; technical result, rematch, and participant replacement remain future slices.

## Verification

- Focused admin runtime and pure guard suites: 24 passed.
- Full backend suite: 250 passed, 2 skipped.
- Django check, migration drift, compileall, and `git diff --check`: clean.
