# CEE Stage 0 R1 — Event Replay Kernel

## Status

Complete.

## Goal

Extend the initial `StatePatch` reducer into an auditable event replay kernel.

## Changes

- Added `.gitignore` to prevent generated Python/test artifacts from polluting project review.
- Added `StateTransitionEvent`.
- Added `reduce_event(state, event)`.
- Added `replay(events, initial_state=None)`.
- Exported the new primitives from `cee_core`.
- Expanded tests from 4 to 8.

## Authority Restored

State authority and policy authority.

State transitions now require a policy decision and can be replayed from an event stream.

## Explicit Non-Goals

- No LLM integration
- No database
- No RAG
- No tool gateway
- No approval UI
- No multi-agent runtime

## Validation

```text
python -m pytest -q
8 passed
```

## Current Kernel Semantics

- `StatePatch` describes the requested mutation.
- `PolicyDecision` decides whether the mutation is allowed.
- `StateTransitionEvent` binds patch, policy, actor, trace, and reason.
- `reduce_event` rejects blocked transitions.
- `replay` deterministically reconstructs final state from allowed events.

## Next Candidate Cut

Stage 0 R2 should introduce an explicit append-only `EventLog` abstraction:

- append event
- list events by trace
- replay all events
- reject non-transition events during state replay

Do not add LLM planning before `EventLog` and replay boundaries are stable.

