# CEE Stage 1C10B — Anthropic-Compatible Provider Skeleton

## Status

Complete.

## Trigger

User provided a third-party Anthropic-compatible base URL and provider keys. Keys must not be committed or echoed.

## Security Note

The pasted keys should be treated as exposed and rotated in their provider consoles.

No key was written to code, docs, examples, or tests.

## Changes

- Added `anthropic_compatible_provider.py`.
- Added `build_anthropic_compatible_task_compiler_provider()`.
- Added `build_anthropic_compatible_request_body()`.
- Added `anthropic_compatible_messages_transport()`.
- Added `extract_anthropic_compatible_text()`.
- Added tests with fake transport/payloads only.
- Added `.env.example`.
- Updated `.gitignore` to exclude `.env` files.
- Added `CEE_SECRET_HANDLING_NOTICE_2026-04-16.md`.

## Environment Variables

```text
CEE_LLM_PROVIDER=minimax_anthropic
CEE_LLM_BASE_URL=<provider-base-url>
CEE_LLM_MODEL=<model-name>
CEE_LLM_API_KEY=<secret>
CEE_RUN_LIVE_LLM_TESTS=0
```

## Explicit Non-Goals

- No live network test
- No committed API keys
- No provider SDK dependency
- No tool calling
- No planner generation
- No patch generation
- No raw output audit by default

## Validation

```text
python -m pytest -q
105 passed
```

