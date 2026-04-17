# CEE Stage 1C1 — LLM Task Compiler Adapter Contract

## Status

Complete.

## Goal

Introduce the LLM task compiler boundary without calling a real model.

## Changes

- Added `llm_task_adapter.py`.
- Added `LLMTaskCompiler` protocol.
- Added `StaticLLMTaskCompiler`.
- Added `build_task_compiler_prompt(raw_input)`.
- Added `parse_llm_task_response(response_json, raw_input)`.
- Added `compile_task_with_llm_adapter(raw_input, compiler)`.
- Added 10 focused tests.

## Semantics

- The adapter accepts only TaskSpec-like JSON.
- The adapter rejects plans, patches, tools, tool calls, and execution fields.
- The adapter rejects malformed JSON.
- The adapter rejects invalid `kind` and `risk_level`.
- The adapter preserves raw input only as provenance.

## Authority Restored

LLM boundary authority.

The LLM is allowed to structure input. It is not allowed to plan, patch, call tools, or execute.

## Explicit Non-Goals

- No real LLM call
- No prompt tuning
- No tool gateway
- No state mutation
- No planner replacement
- No fallback model

## Validation

```text
python -m pytest -q
71 passed
```

## Next Candidate Cut

Stage 1C2 should connect the adapter to `execute_task` through a separate entry point:

- `execute_task_with_compiler(raw_input, compiler)`
- compiler produces `TaskSpec`
- existing deterministic planner consumes `TaskSpec`
- all existing policy/replay/artifact rules remain unchanged

