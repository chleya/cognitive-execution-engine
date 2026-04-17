# CEE Stage 1C5 — LLM Provider Interface Stub

## Status

Complete.

## Goal

Define a provider-neutral LLM boundary before adding any real networked provider integration.

## Changes

- Added `llm_provider.py`.
- Added `LLMProviderRequest`.
- Added `LLMProviderResponse`.
- Added `LLMProviderError`.
- Added `LLMProvider` protocol.
- Added `StaticLLMProvider`.
- Added `FailingLLMProvider`.
- Added `ProviderBackedTaskCompiler`.
- Added 4 focused tests.

## Semantics

- Provider receives a structured task compiler prompt envelope.
- Provider returns raw response text only.
- Task compiler parser still enforces TaskSpec-only output.
- Provider-backed compiler cannot bypass plan/patch/tool restrictions.
- Failure path has a provider-neutral error envelope.

## Authority Restored

Provider boundary authority.

Future vendor-specific model calls must fit behind a provider-neutral interface and cannot leak provider behavior into runtime, planner, policy, or replay logic.

## Explicit Non-Goals

- No network call
- No OpenAI/Anthropic/local provider binding
- No API key handling
- No retry
- No timeout implementation
- No streaming
- No tool calling

## Validation

```text
python -m pytest -q
88 passed
```

## Next Candidate Cut

Stage 1C6 should add compiler/provider audit events for provider request and response metadata, without recording full model output by default.

