# CEE Stage 1C2 — Execute Task With Compiler

## Status

Complete.

## Goal

Connect the LLM task compiler adapter to the deterministic runtime without giving the compiler planning, patching, tool, or execution authority.

## Changes

- Added `execute_task_with_compiler(raw_input, compiler, event_log=None)`.
- Exported it from `cee_core`.
- Added 7 focused tests.

## Runtime Flow

```text
raw input
→ LLMTaskCompiler protocol
→ TaskSpec
→ deterministic plan_from_task
→ execute_plan
→ policy evaluation
→ EventLog
→ replay_state
→ RunResult
```

## Semantics

- Compiler replaces only task compilation.
- Planner remains deterministic.
- Policy rules are unchanged.
- EventLog records transition attempts.
- Replay applies only allowed transitions.
- Forbidden compiler outputs such as `candidate_patches` and `tool_calls` are rejected before planning.
- `RunArtifact` remains compatible with compiler-produced tasks.

## Authority Restored

LLM operator boundary authority.

The LLM can structure input, but the system retains planning, policy, audit, replay, and artifact authority.

## Explicit Non-Goals

- No real model call
- No LLM-generated plan
- No LLM-generated patch
- No LLM tool calls
- No external execution
- No database
- No CLI

## Validation

```text
python -m pytest -q
78 passed
```

## Next Candidate Cut

Stage 1C3 should add event logging for compiler activity:

- `task.compiler.requested`
- `task.compiler.succeeded`
- `task.compiler.rejected`

This makes model-side failures auditable before any real LLM provider is introduced.

