# CEE Stage 0 R8 — Serialization Contract

## Status

Complete.

## Goal

Create a stable in-memory serialization boundary before persistence, CLI, API, or LLM adapter work.

## Changes

- Added `StatePatch.to_dict()` / `StatePatch.from_dict()`.
- Added `PolicyDecision.to_dict()` / `PolicyDecision.from_dict()`.
- Added `StateTransitionEvent.from_dict()`.
- Updated `StateTransitionEvent.to_dict()` to use nested contracts.
- Added `TaskSpec.to_dict()` / `TaskSpec.from_dict()`.
- Added `PlanSpec.to_dict()` / `PlanSpec.from_dict()`.
- Added `replay_serialized_transition_events()`.
- Added 6 focused tests.

## Semantics

- Serialized state-transition events can be replayed.
- Non-transition serialized events are ignored by state replay.
- Blocked or approval-required serialized transitions are ignored by state replay.
- Allowed serialized transitions mutate replayed state.

## Authority Restored

Serialization authority.

State, policy, plan, task, and event boundaries now have explicit data contracts before persistence or external interfaces are introduced.

## Explicit Non-Goals

- No database persistence
- No JSON file event store
- No CLI
- No API server
- No LLM adapter
- No schema versioning yet

## Validation

```text
python -m pytest -q
46 passed
```

## Next Candidate Cut

Stage 0 R9 should add explicit schema version fields before any on-disk or API contract:

- `schema_version` for task, plan, patch, policy decision, transition event
- reject unknown major versions
- preserve backward-compatibility rules

