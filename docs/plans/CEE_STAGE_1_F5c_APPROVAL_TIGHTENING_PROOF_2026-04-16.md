## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: approval-tightening-proof

# CEE Stage 1F5c Approval Tightening Proof

## Goal

Prove the domain overlay can tighten `allow → requires_approval` (the second
tightening direction), completing coverage of the two tightening paths.

## What Was Done

Added `test_execute_task_in_domain_overlay_requires_approval_tightening` in
`tests/test_runtime_orchestrator.py`.

The test:
1. Builds a domain context with `approval_required_patch_sections=("beliefs",)`
2. Executes a low-risk task through `execute_task_in_domain`
3. Verifies both beliefs patches (objective + domain_name) go from core-allow → domain-requires_approval

## Why This Step

F5a tested `allow → deny` (denied_patch_sections).
F5c tests `allow → requires_approval` (approval_required_patch_sections).

Together they cover the two tightening directions defined in F4:
- `allow -> requires_approval`
- `allow -> deny`

The third `deny -> deny` case was implicitly covered by F5a's
`cannot loosen core deny` behavior (self_model stays requires_approval).

## Codex Principle

Minimal incision: one test for one tightening direction. No other changes.

## Validation

```text
python -m pytest tests/test_runtime_orchestrator.py -v
8 passed in 0.38s
```
