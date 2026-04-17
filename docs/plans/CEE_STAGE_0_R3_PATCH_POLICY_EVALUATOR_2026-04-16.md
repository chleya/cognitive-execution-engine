# CEE Stage 0 R3 — Patch Policy Evaluator

## Status

Complete.

## Goal

Move patch permission decisions out of call sites and into a minimal policy evaluator.

## Changes

- Added `evaluate_patch_policy(patch)`.
- Added `build_transition_for_patch(patch, actor, reason)`.
- Exported both helpers from `cee_core`.
- Added 6 focused tests.

## Stage 0 Policy

| Section | Verdict | Reason |
|---|---|---|
| `memory` | allow | Safe Stage 0 mutable state |
| `goals` | allow | Safe Stage 0 mutable state |
| `beliefs` | allow | Safe Stage 0 mutable state |
| `meta` | allow | Safe Stage 0 mutable state |
| `self_model` | requires_approval | Changes system self-description |
| `policy` | deny | Policy mutation requires release governance |
| unknown | deny | Unknown state surface |

## Authority Restored

Policy authority.

Call sites no longer need to invent their own `PolicyDecision` for basic state patches.

## Explicit Non-Goals

- No role model
- No user identity model
- No approval service
- No policy persistence
- No production authorization
- No LLM integration

## Validation

```text
python -m pytest -q
18 passed
```

## Next Candidate Cut

Stage 0 R4 should add approval semantics without UI:

- `ApprovalDecision`
- approve a `requires_approval` transition
- reject a `requires_approval` transition
- audit both outcomes
- replay only approved transitions

Do not add external human UI yet.

