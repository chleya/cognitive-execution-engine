# CEE Stage 0 R6 — TaskSpec Compiler

## Status

Complete.

## Goal

Introduce a structured `TaskSpec` boundary so raw user input is normalized before planner execution.

## Changes

- Added `TaskSpec`.
- Added `compile_task(raw_input, event_log=None)`.
- Added `plan_from_task(task)`.
- Added 8 focused tests.

## Semantics

- Raw user input is not passed directly to planner logic.
- `compile_task` normalizes text into `TaskSpec`.
- `task.received` event is written when an `EventLog` is supplied.
- `plan_from_task` consumes `TaskSpec`, not raw input.
- Low-risk analysis tasks produce allowed state patches.
- Medium-risk update-like tasks produce one `self_model` patch requiring approval.

## Authority Restored

Input authority and planner boundary authority.

User text is downgraded into a structured task before planning. Planner receives task structure, not unconstrained natural language.

## Explicit Non-Goals

- No LLM task compiler
- No prompt parsing
- No semantic intent classifier
- No tool execution
- No durable task store
- No approval UI

## Validation

```text
python -m pytest -q
40 passed
```

## Next Candidate Cut

Stage 0 R7 should introduce a small `RunResult` / `execute_task` orchestrator:

- compile raw input
- plan from task
- execute plan
- return task, plan, event log, replayed state, and blocked transitions

This becomes the first end-to-end deterministic kernel entry point.
