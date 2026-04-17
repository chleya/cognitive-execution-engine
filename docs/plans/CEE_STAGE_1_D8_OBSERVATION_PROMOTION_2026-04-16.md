# CEE Stage 1D8 — Observation Promotion

## Status

Complete.

## Goal

Allow an observation candidate to become a candidate belief patch while preserving policy and replay authority.

## Changes

- Added `promote_observation_to_patch(observation, belief_key)`.
- Added 3 focused tests.

## Semantics

- Observation promotion creates a `StatePatch`.
- Observation promotion does not mutate state.
- Belief patch includes content, confidence, provenance, source tool, and call id.
- Empty belief key is rejected.
- The returned patch still requires policy evaluation.
- State mutation occurs only after the patch becomes an allowed transition and is replayed.

## Authority Restored

Belief promotion boundary authority.

The project now has an explicit path from observation to belief candidate without allowing tool results to become facts automatically.

## Explicit Non-Goals

- No automatic promotion
- No LLM promotion decision
- No confidence calibration
- No conflict resolution
- No belief graph
- No memory write beyond existing state patch mechanism

## Validation

```text
python -m pytest -q
137 passed, 2 skipped
```

## Next Candidate Cut

Stage 1D9 should add an end-to-end read-only tool observation flow:

```text
ToolCallSpec
→ ToolCallEvent
→ InMemoryReadOnlyToolRunner
→ ToolResultEvent
→ ObservationCandidate
→ ObservationEvent
→ explicit promotion patch
→ policy
→ replay
```

