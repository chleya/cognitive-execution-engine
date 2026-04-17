## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: artifact-domain-proof

# CEE Stage 1F5f Artifact Domain Proof

## Goal

Prove the run artifact faithfully records domain-overlay policy decisions and
preserves them through JSON round-trip.

## What Was Done

Added `test_run_artifact_captures_domain_tightened_decisions` in
`tests/test_run_artifact.py`.

The test:
1. Builds a domain context with `denied_patch_sections=("memory",)`
2. Executes a medium-risk task through `execute_task_in_domain`
3. Converts result to artifact
4. Verifies artifact counts reflect domain-tightened decisions (denied=1 for memory)
5. Verifies TaskSpec carries domain_name into artifact
6. Verifies JSON round-trip preserves domain-tightened counts

## Why This Step

F5a–F5e proved domain overlay decisions exist in runtime events and event log.
F5f proves those decisions survive serialization into a portable artifact.

The MVP acceptance test "replay of the event stream reconstructs the same state"
is already covered by existing artifact tests. F5f extends that to the domain-aware
execution path.

## Codex Principle

Minimal incision: one integration test for artifact fidelity under domain overlay.

## Validation

```text
python -m pytest tests/test_run_artifact.py -v
8 passed in 0.07s
```
