# CEE Stage 0 R4 — Approval Semantics

## Status

Complete.

## Goal

Add minimal approval semantics for transitions that policy marks as `requires_approval`.

## Changes

- Added `ApprovalDecision`.
- Added `ApprovalAuditEvent`.
- Added `approve_transition(event, decision)`.
- Extended `EventRecord` to include approval audit events.
- Added 5 focused tests.

## Semantics

- `requires_approval` transition cannot mutate state directly.
- Approval decision must match the transition `trace_id`.
- Rejected approval cannot create an allowed transition.
- Approved transition is converted to a new `StateTransitionEvent` with verdict `allow`.
- Approval decision is audit-only and does not itself mutate state.
- Replay ignores audit-only approval events and blocked/pending transition events.
- Replay applies only allowed state-transition events.

## Authority Restored

Human approval authority.

High-sensitivity state surfaces such as `self_model` now require explicit approval before mutation.

## Explicit Non-Goals

- No approval UI
- No user authentication
- No durable approval store
- No approval timeout
- No HMAC/signature layer
- No production authorization
- No LLM integration

## Validation

```text
python -m pytest -q
23 passed
```

## Review Correction

Initial test coverage revealed that recording the original `requires_approval` transition would block replay if all transition events were replayed blindly.

The corrected rule is:

> Event log keeps all events for audit, but state replay consumes only allowed state-transition events.

## Next Candidate Cut

Stage 0 R5 should introduce a tiny deterministic planner interface:

- `PlanSpec`
- fake planner returns candidate patches
- policy evaluates candidate patches
- event log records accepted, blocked, and approval-required transitions

Do not use a real LLM until the deterministic planner path is stable.
