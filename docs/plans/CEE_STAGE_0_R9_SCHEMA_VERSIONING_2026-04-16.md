# CEE Stage 0 R9 — Schema Versioning

## Status

Complete.

## Goal

Add explicit schema versions to serialized contracts before any file, database, API, or LLM adapter boundary uses them.

## Changes

- Added `schemas.py`.
- Added schema constants:
  - `cee.patch.v1`
  - `cee.policy_decision.v1`
  - `cee.task.v1`
  - `cee.plan.v1`
  - `cee.state_transition_event.v1`
- Added `require_schema_version()`.
- Added `schema_version` to serialized patch, policy decision, task, plan, and transition event payloads.
- Added missing-version and unknown-major-version tests.

## Semantics

- Serialized payloads must include `schema_version`.
- Missing schema version is rejected.
- Unknown major schema version is rejected.
- Unsupported minor/variant version is rejected for now.

## Authority Restored

Contract authority.

The serialized boundary is now versioned and cannot silently drift when persistence or external interfaces are added.

## Explicit Non-Goals

- No migration framework
- No backward compatibility beyond v1
- No file event store
- No database
- No API
- No LLM adapter

## Validation

```text
python -m pytest -q
48 passed
```

## Next Candidate Cut

Stage 0 R10 should add a minimal JSON event artifact round-trip:

- dump event payloads to JSON string
- load JSON string
- replay loaded payloads

Still no database and no CLI.

