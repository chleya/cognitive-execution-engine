# CEE Stage 1D9 — Read-Only Tool Observation Flow

## Status

Complete.

## Goal

Connect the read-only tool path from proposed call to optional explicit belief promotion without giving automatic state authority to tools.

## Changes

- Added `tool_observation_flow.py`.
- Added `ToolObservationFlowResult`.
- Added `run_read_only_tool_observation_flow()`.
- Added 4 focused tests.

## Flow

```text
ToolCallSpec
→ ToolCallEvent
→ InMemoryReadOnlyToolRunner
→ ToolResultEvent
→ ObservationCandidate
→ ObservationEvent
→ optional promote_observation_to_patch
→ build_transition_for_patch
→ EventLog
→ replay
```

## Semantics

- Tool call proposal is audited.
- Tool result is audited.
- Successful result becomes observation candidate.
- Observation candidate is audited.
- Belief promotion happens only if `promote_to_belief_key` is supplied.
- Promotion creates a belief patch.
- Belief patch still goes through policy and replay.
- Blocked or unknown tools do not produce observations.
- Blocked or unknown tools do not promote beliefs.

## Authority Restored

End-to-end evidence flow authority.

Tool output can now become belief only through an explicit, auditable, policy-mediated path.

## Explicit Non-Goals

- No write tools
- No external side effects
- No network
- No database
- No automatic promotion
- No LLM tool calls
- No planner tool calls

## Validation

```text
python -m pytest -q
141 passed, 2 skipped
```

## Next Candidate Cut

Stage 1D10 should be architecture review for the tool/observation line before any planner or LLM is allowed to propose tool calls.

