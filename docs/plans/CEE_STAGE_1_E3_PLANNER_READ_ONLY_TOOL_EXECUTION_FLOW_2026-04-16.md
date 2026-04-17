## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: planner-read-only-tool-execution-flow

# CEE Stage 1E3 Planner Read-Only Tool Execution Flow

## Goal

Add the first deterministic plan-level tool execution flow while preserving the
existing authority boundaries:

- planner may propose tool calls
- policy must still evaluate them
- only allowed read-only calls may execute
- execution must remain explicit
- tool results must still go through observation before any belief promotion

## Deliverables

- `execute_plan_with_read_only_tools()`
- `run_allowed_tool_call_observation_flow()`
- focused tests for allowed, blocked, and non-promoted paths

## Architecture Result

The active chain is now:

```text
PlanSpec
-> execute_plan(..., tool_registry=runner.registry)
-> ToolCallEvent
-> run only allowed read-only calls
-> ToolResultEvent
-> ObservationCandidate
-> ObservationEvent
-> optional explicit promotion patch
-> policy
-> replay
```

## Important Boundary

`run_read_only_tool_observation_flow()` still exists for single-call direct
usage, but the plan-level path does not duplicate the `ToolCallEvent`.

That duplication would have polluted audit truth, so plan-level execution now
continues from the already-audited `ToolCallEvent`.

## Validation

```text
python -m pytest -q
145 passed, 2 skipped
```

## Preserved Invariants

- planner tool proposal is not implicit execution
- blocked tool calls are audited but not run
- only read-only runner is used
- tool result is not belief
- observation is not belief
- belief promotion is explicit and still policy-mediated
- LLM compiler still cannot generate tool calls
