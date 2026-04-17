## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: domain-policy-overlay

# CEE Stage 1F4 Domain Policy Overlay

## Goal

Allow the domain layer to add explicit constraints to core policy without
letting domain plugins loosen core safety rules.

## Deliverables

- `evaluate_patch_policy_in_domain()`
- domain plugin pack support for:
  - `denied_patch_sections`
  - `approval_required_patch_sections`
- runtime path updated to apply domain overlay for patch transitions

## Rule

Domain overlay may only tighten policy:

- `allow -> requires_approval`
- `allow -> deny`
- `deny -> deny`

It may not loosen:

- `deny -> allow`
- `requires_approval -> allow`

## Validation

```text
python -m pytest -q
163 passed, 2 skipped
```
