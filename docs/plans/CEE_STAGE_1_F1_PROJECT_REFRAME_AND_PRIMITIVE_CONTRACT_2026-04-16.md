## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: project-reframe-and-primitive-contract

# CEE Stage 1F1 Project Reframe And Primitive Contract

## Goal

Align the repository with the updated project definition:

- fixed safety core
- general cognitive primitives
- extensible state graph
- domain-pluggable execution surfaces

## Deliverables

- canonical docs rewritten to the new project definition
- corrupted / stale test-count text corrected
- `CognitivePrimitive` contract added in code
- `TaskSpec` upgraded with `requested_primitives`
- deterministic and LLM task compilers aligned to the primitive contract

## Validation

```text
python -m pytest -q
154 passed, 2 skipped
```

## Boundary Result

The project is no longer described as a fixed structure-first system only.

It is now described and typed as:

```text
core-fixed
primitive-general
state-extensible
domain-pluggable
```

## Important Constraint

This cut did not give primitives autonomous execution power.

Primitives are still task-level contracts, not free-running workflow nodes.
