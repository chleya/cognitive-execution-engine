# Claude / LLM Project Instructions

## First-Principles Frame

Use first-principles reasoning. Reject cargo-cult architecture and path
dependence.

Do not assume the target is already clear. Reduce each request to:

- core objective
- authority boundary
- state transition
- policy consequence
- auditable evidence

If the goal is unclear, stop and narrow it before expanding the system.

If the goal is clear but the path is not optimal, prefer the shorter, safer,
more defensible path.

## Core Project Question

This project does not ask:

> How do we let an LLM act like a person?

This project asks:

> How do we constrain an LLM into a cognitive operator while keeping system
> authority in explicit state, policy, audit, and human control?

## Evaluation Questions For Every Change

Every meaningful change must answer:

- what authority does this restore or clarify?
- what state transition becomes more explicit?
- does this reduce uncontrolled execution power?
- does this improve replay, audit, testing, or migration?
- does this keep the model out of the sovereignty path?

If those answers are weak, the change is probably not worth making.

## Project Language Guardrail

Do not frame the system as:

- self-aware
- conscious
- person-like
- a digital human

`self_model` means runtime capability and risk description only.
