# CEE Stage 1C10 — OpenAI Provider Transport Skeleton

## Status

Complete.

## Goal

Add one env-gated OpenAI provider transport skeleton while preserving the provider-neutral runtime boundary.

## Official Documentation Basis

This cut follows OpenAI's official Responses API and Structured Outputs guidance:

- Responses API is the provider call boundary.
- Structured Outputs with `json_schema` are used to constrain the task compiler response.
- The project still validates model output through `parse_llm_task_response()`.

## Changes

- Added `openai_provider.py`.
- Added `OPENAI_ENV_KEY = "CEE_LLM_API_KEY"`.
- Added `OPENAI_MODEL_ENV = "CEE_LLM_MODEL"`.
- Added `OPENAI_DEFAULT_MODEL = "gpt-4o-mini"`.
- Added `TASK_SPEC_JSON_SCHEMA`.
- Added `build_openai_task_compiler_provider()`.
- Added `openai_responses_task_compiler_transport()`.
- Added `openai_responses_task_compiler_transport_with_client()`.
- Added 4 network-free tests with fake client/transport.

## Semantics

- No network call is made by tests.
- OpenAI SDK is imported lazily only if the transport is actually used.
- Provider is still env-gated through `EnvironmentLLMProvider`.
- Provider output is response text only.
- Provider output still passes through the TaskSpec parser.
- Tool calls, plans, patches, and execution fields remain forbidden.
- Runtime is unchanged.

## Explicit Non-Goals

- No live integration test yet
- No API key committed or required
- No streaming
- No tool calling
- No Responses API stateful thread usage
- No retry policy
- No provider fallback
- No model-output audit logging by default

## Validation

```text
python -m pytest -q
99 passed
```

## Next Candidate Cut

Stage 1C11 should add a skipped-by-default live integration test:

- skip unless `CEE_LLM_API_KEY` and `CEE_RUN_LIVE_LLM_TESTS=1`
- assert provider returns TaskSpec-compatible JSON or fails safely
- no tool calling
- no state patch generation

