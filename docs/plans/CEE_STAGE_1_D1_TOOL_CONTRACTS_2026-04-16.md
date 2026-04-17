# CEE Stage 1D1 — Tool Contracts

## Status

Complete.

## Goal

Introduce tool availability as an explicit structure without executing tools.

## Changes

- Added `tools.py`.
- Added `ToolSpec`.
- Added `ToolCallSpec`.
- Added `ToolPolicyDecision`.
- Added `ToolRegistry`.
- Added `evaluate_tool_call_policy()`.
- Added 7 focused tests.

## Semantics

- Tool declaration is not execution.
- Tool call proposal is not execution.
- Unknown tools are denied.
- Read tools are allowed.
- Write tools require approval.
- External side-effect tools require approval.

## Authority Restored

Tool availability authority.

Tools become declared capabilities under policy instead of prompt-level affordances.

## Explicit Non-Goals

- No tool execution
- No tool result events
- No external side effects
- No network calls
- No planner-generated tool calls
- No LLM tool calling

## Validation

```text
python -m pytest -q
112 passed, 2 skipped
```

## Next Candidate Cut

Stage 1D2 should add `ToolCallEvent` and audit-only recording of proposed tool calls, still without execution.

