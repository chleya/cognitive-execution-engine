## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: none-plugin-pack-boundary

# CEE Stage 1F5d None Plugin Pack Boundary

## Goal

Prove domain context with no plugin pack does not change core policy decisions —
the identity boundary of the overlay.

## What Was Done

Added `test_execute_task_in_domain_with_no_plugin_pack_equals_core_policy` in
`tests/test_runtime_orchestrator.py`.

The test:
1. Builds a domain context with no registry (returns plugin_pack=None)
2. Executes a low-risk task through `execute_task_in_domain`
3. Verifies beliefs and memory patches remain core-allow

## Why This Step

Completes the overlay boundary proof:
- F5a: allow→deny (tightening)
- F5b: registry integration (wiring)
- F5c: allow→requires_approval (tightening)
- F5d: None→identity (no change when no plugin pack)

Without F5d, the overlay path has an untested implicit assumption: that None plugin_pack
is handled correctly and does not break execution.

## Codex Principle

Minimal incision: one assertion, one identity boundary case.

## Validation

```text
python -m pytest tests/test_runtime_orchestrator.py -v
9 passed in 0.44s
```
