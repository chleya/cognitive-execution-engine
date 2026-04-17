# CEE Stage 1C6 — Provider Audit Events

## Status

Complete.

## Goal

Audit provider request/response metadata before adding any real provider implementation.

## Changes

- `ProviderBackedTaskCompiler` can now receive an `EventLog`.
- Runtime attaches the current `EventLog` to provider-backed compilers when missing.
- Added `llm.provider.requested`.
- Added `llm.provider.succeeded`.
- Added `llm.provider.failed`.
- Added 4 focused tests.

## Semantics

- Provider request event records request id, provider name, timeout, and prompt role.
- Provider success event records request id, provider name, model name, and response length.
- Provider success event does not record full model output.
- Provider failure event records provider-neutral failure metadata.
- Provider audit events are audit-only and do not mutate state replay.

## Authority Restored

Provider audit authority.

Future provider calls will be observable without allowing provider-specific behavior to leak into planner, policy, replay, or state mutation.

## Explicit Non-Goals

- No real provider
- No network call
- No retry
- No timeout enforcement
- No streaming
- No model output storage by default
- No prompt redaction policy beyond existing compiler audit policy

## Validation

```text
python -m pytest -q
90 passed
```

## Next Candidate Cut

Stage 1C7 should be an architecture review before real provider integration:

- check event ordering
- check audit payloads
- check no raw output leakage
- check provider failures are visible
- decide if a real provider is allowed yet
