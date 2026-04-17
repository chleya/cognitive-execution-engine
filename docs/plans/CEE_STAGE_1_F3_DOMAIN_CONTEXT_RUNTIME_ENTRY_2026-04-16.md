## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: domain-context-runtime-entry

# CEE Stage 1F3 Domain Context Runtime Entry

## Goal

Make the domain plugin layer participate in runtime entry without introducing
dynamic plugin loading or automatic domain selection.

## Deliverables

- `DomainContext`
- `build_domain_context()`
- `TaskSpec.domain_name`
- `execute_task_in_domain()`
- `execute_task_with_compiler_in_domain()`

## Result

The runtime now has an explicit domain entry boundary:

```text
raw input
-> DomainContext
-> TaskSpec(domain_name=...)
-> planner / compiler path
-> replayed state annotated with domain context
```

## Important Constraint

The model still does not choose the domain.

The runtime still requires an explicit domain context from the caller.

## Validation

```text
python -m pytest -q
163 passed, 2 skipped
```
