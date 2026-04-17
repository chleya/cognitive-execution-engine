# CEE Stage 1D2 — ToolCallEvent

## Status

Complete.

## Goal

Record proposed tool calls and their policy verdicts as audit events without executing tools.

## Changes

- Added `ToolPolicyDecision.to_dict()`.
- Added `ToolCallEvent`.
- Added `build_tool_call_event()`.
- Extended `EventRecord` to include `ToolCallEvent`.
- Added 5 focused tests.

## Semantics

- Tool call event is audit-only.
- Tool call event records proposed call and policy verdict.
- Tool call event does not execute the tool.
- Tool call event does not mutate state.
- `EventLog.replay_state()` ignores tool call events.

## Authority Restored

Tool audit authority.

The system can now record what tool would have been called and whether policy would allow it before any execution layer exists.

## Explicit Non-Goals

- No tool execution
- No tool result
- No external side effect
- No approval fulfillment for tool calls
- No LLM tool calling
- No planner tool generation

## Validation

```text
python -m pytest -q
117 passed, 2 skipped
```

## Next Candidate Cut

Stage 1D3 should add `ToolResultEvent` contract for future read-only tool execution, but still no actual tool runner.

