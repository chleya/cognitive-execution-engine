# CEE Stage 1E1 — Planner-Proposed Tool Calls

## Status

Complete.

## Goal

Allow deterministic planner output to include proposed tool calls as an auditable, policy-mediated contract without executing tools.

## Changes

- Added `PlanSpec.proposed_tool_calls`.
- Added plan serialization support for proposed tool calls.
- Extended `PlanExecutionResult` with `tool_call_events`.
- Added `allowed_tool_calls` and `blocked_tool_calls`.
- `execute_plan()` now accepts `tool_registry`.
- Added 4 focused tests.

## Semantics

- Planner may propose tool calls.
- Proposed tool calls are audited as `ToolCallEvent`.
- Proposed tool calls are policy-evaluated.
- Read tool proposals are allowed.
- Write tool proposals are blocked with `requires_approval`.
- Proposed tool calls are not executed.
- Missing `tool_registry` is rejected when tool calls are present.
- Replay still ignores tool call audit events.

## Authority Restored

Planner tool proposal authority under policy.

The planner can now express tool intent, but not execution. Tool execution authority still remains outside planner and LLM.

## Explicit Non-Goals

- No tool execution
- No tool runner invocation
- No LLM-generated tool calls
- No write/external tool execution
- No automatic observation flow

## Validation

```text
python -m pytest -q
145 passed, 2 skipped
```

## Next Candidate Cut

Stage 1E2 should review whether deterministic planner-proposed tool calls are stable enough to connect to the existing read-only runner.

