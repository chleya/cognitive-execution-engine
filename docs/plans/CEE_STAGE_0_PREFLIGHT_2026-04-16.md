# CEE Stage 0 Preflight

## Trigger

The project needs a new root structure before any agent or LLM integration. Without a state-first kernel, future work will drift into model-first tool calling.

## Chosen Entry

Stage 0: minimal state/event/policy kernel.

## Authority Restored

State authority and policy authority.

The system must make state transition and permission decision explicit before any LLM is allowed to propose actions.

## Why Bounded

Only these surfaces are in scope:

- `src/cee_core/state.py`
- `src/cee_core/events.py`
- `src/cee_core/policy.py`
- documentation under `docs/`

No external services, no model calls, no database, no UI.

## Forbidden Scope

- No LLM API integration
- No RAG
- No web tools
- No autonomous goal generation
- No production deployment
- No multi-agent runtime

## Stop Conditions

Stop after:

- State schema exists
- Event schema exists
- Policy decision schema exists
- Reducer can apply a simple patch
- Invalid patch is rejected
- Project charter and architecture docs exist

## Review Question

Does the first kernel make this project more state-first, policy-guarded, and replayable?

If not, the implementation is wrong even if it appears functional.

