## Status: current
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: principle-baseline

# CEE Principle Baseline

## Purpose

This document is the short operating baseline for future changes.

If code, plans, or prompts drift from these principles, this document wins until
an explicit architecture record replaces it.

## Core Principle

CEE is an extensible cognitive execution engine with a fixed safety core.

Its purpose is not to make an LLM behave like a person.

Its purpose is to keep system authority in explicit state, policy, audit, and
human approval while allowing bounded cognitive assistance from models.

## Authority Baseline

- `State` owns continuity.
- The reducer owns valid state evolution.
- Policy owns permission.
- The event log owns audit history.
- Human approval owns high-risk authorization.
- LLMs own only bounded proposal, extraction, interpretation, and narration.

## Boundary Baseline

- Raw input must become typed structure before planning.
- LLM output may not directly become `StatePatch`, tool execution, or canonical belief.
- Planner output is proposal, not execution.
- Tool execution must remain explicit and policy-mediated.
- Tool result is not belief.
- Belief promotion must remain explicit, auditable, and policy-mediated.
- Domain plugins may tighten authority, not loosen it.
- `self_model` is calibration and capability description only, not personhood.

## Small-Step Execution Baseline

The runtime may use bounded intermediate contracts when they improve audit and
control.

Current accepted example:

- `TaskSpec -> ReasoningStep -> PlanSpec`

This is acceptable only because:

- `ReasoningStep` is typed
- it selects the next bounded action only
- it does not mutate canonical state directly
- it does not execute tools directly
- it does not bypass planner, policy, or approval
- it is recorded in the audit trail

## Change Test

Every meaningful change should answer:

1. What authority is clarified or restored?
2. What typed contract becomes more explicit?
3. What audit or replay property improves?
4. What model freedom is still constrained?
5. What boundary remains forbidden after this change?

If those answers are weak, the change is probably not aligned with CEE.

## Current Validation Snapshot

```text
python -m pytest -q
341 passed, 2 skipped
```
