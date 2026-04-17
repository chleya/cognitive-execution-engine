# CEE Stage 1C11 — Live Provider Integration Test Shell

## Status

Complete.

## Goal

Add live provider integration tests that are skipped by default and never require secrets in repository files.

## Changes

- Added `tests/test_live_provider_integration.py`.
- Added pytest `integration` marker.
- Added live tests for:
  - OpenAI provider
  - Anthropic-compatible provider

## Default Behavior

Live tests are skipped unless:

```text
CEE_RUN_LIVE_LLM_TESTS=1
CEE_LLM_API_KEY=<secret>
```

Anthropic-compatible live test also requires:

```text
CEE_LLM_BASE_URL=<provider-base-url>
```

## Safety Rules

- No key is stored in code.
- No key is stored in docs.
- No key is printed.
- Tests validate only accepted `TaskSpec` shape and replay safety.
- Tests do not allow tool calls, patch generation, or planner generation.

## Example Commands

OpenAI:

```powershell
$env:CEE_RUN_LIVE_LLM_TESTS="1"
$env:CEE_LLM_API_KEY="<secret>"
$env:CEE_LLM_MODEL="gpt-4o-mini"
python -m pytest tests\test_live_provider_integration.py -q
```

Anthropic-compatible:

```powershell
$env:CEE_RUN_LIVE_LLM_TESTS="1"
$env:CEE_LLM_API_KEY="<secret>"
$env:CEE_LLM_BASE_URL="<provider-base-url>"
$env:CEE_LLM_MODEL="<model-name>"
$env:CEE_LLM_PROVIDER="anthropic-compatible"
python -m pytest tests\test_live_provider_integration.py -q
```

## Validation

Default no-secret baseline:

```text
python -m pytest -q
105 passed, 2 skipped
```

