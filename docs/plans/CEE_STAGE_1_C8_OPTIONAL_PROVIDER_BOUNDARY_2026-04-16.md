# CEE Stage 1C8 — Optional Provider Boundary

## Status

Complete.

## Goal

Add an optional provider implementation boundary without adding network I/O, vendor SDKs, or API-key-dependent tests.

## Changes

- Added `optional_provider.py`.
- Added `ProviderTransport`.
- Added `EnvironmentLLMProvider`.
- Added `build_disabled_provider_transport(provider_name)`.
- Added 4 focused tests.

## Semantics

- Provider requires an environment variable before use.
- Provider uses injected transport for all response generation.
- No network code exists in this implementation.
- Disabled transport fails explicitly and states that no network call was made.
- Provider integrates with `ProviderBackedTaskCompiler` and the existing runtime.

## Authority Restored

Provider implementation boundary authority.

Real provider work must now pass through an environment gate and an injected transport instead of leaking SDK/network behavior into runtime.

## Explicit Non-Goals

- No real network call
- No provider SDK
- No API key committed to code
- No retry policy
- No streaming
- No tool calling
- No vendor-specific request schema

## Validation

```text
python -m pytest -q
95 passed
```

## Next Candidate Cut

Stage 1C9 should be a real-provider readiness review:

- decide whether to add a vendor transport
- require official SDK/docs review before implementation
- require skipped-by-default integration tests
- require env var documentation
- preserve no-tool-call and TaskSpec-only restrictions

