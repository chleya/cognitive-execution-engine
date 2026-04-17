## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: domain-overlay-execution-proof

# CEE Stage 1F5a Domain Overlay Execution Proof

## Goal

Prove the domain policy overlay participates in actual runtime execution traces,
not just type-checks in isolation.

## What Was Done

Added `test_execute_task_in_domain_overlay_tightens_policy` in
`tests/test_runtime_orchestrator.py`.

The test:
1. Builds a domain context with an inline `DomainPluginPack` that denies `memory` section
2. Executes a medium-risk task ("update the project belief summary") through `execute_task_in_domain`
3. Verifies `memory` patch goes from core-allow → domain-deny
4. Verifies `self_model` stays `requires_approval` (domain cannot loosen)

## Why This Step

The overlay function `evaluate_patch_policy_in_domain` was tested in unit isolation
(`test_domain_policy.py`). But unit tests of the overlay function do not prove
it participates in the runtime pipeline. This integration test closes that gap.

## Codex Principle

Minimal incision: one test, one assertion about one concrete behavior.
No dynamic loading, no framework, no expanded scope.

## Validation

```text
python -m pytest -q
169 passed, 2 skipped
```
