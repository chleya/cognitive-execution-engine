# Agent Operating Rules

## Project Identity

This repository builds an extensible cognitive execution engine with a fixed
safety core.

The system authority belongs to:

1. Explicit state `S(t)`
2. Event log
3. Policy engine
4. Audit trail
5. Human approval boundary

LLMs only propose, summarize, extract, or narrate. They do not own execution authority.

The system's generality should come from cognitive primitives and plugin
boundaries, not from open-ended model freedom.

## First-Principles Rule

Always reason from the primitive question:

> What state transition is being authorized, by whom, under which policy, with what evidence, and how can it be replayed?

If a proposed change does not improve state clarity, policy clarity, auditability, replayability, or bounded execution, do not do it.

## Red Lines

- Do not build open-ended autonomous goal generation.
- Do not allow the model to expand its own permissions.
- Do not treat chat history as canonical state.
- Do not write memory directly from model output without validation.
- Do not make high-risk tool execution model-owned.
- Do not describe `self_model` as consciousness or personhood.
- Do not add framework dependencies before the core state semantics are stable.

## Required Preflight For Any Non-Trivial Change

Before implementation, state:

- Trigger: why this work is needed now
- Chosen entry: exact bounded surface
- Authority restored: state, policy, audit, memory, or human approval
- Why bounded: files/modules/contracts touched
- Forbidden scope: what must not be changed
- Stop conditions: when to stop and review

## Development Order

1. State schema
2. Event model
3. Reducer semantics
4. Policy checks
5. Audit/replay
6. Tool gateway
7. Human approval
8. LLM proposal adapters
9. Memory promotion
10. Self-model calibration

Do not invert this order without an explicit architecture record.

## Acceptance Standard

A feature is not accepted because it "works once".

It is accepted when:

- Inputs and outputs are typed
- State transition is explicit
- Policy decision is recorded
- Audit trail is complete
- Replay behavior is deterministic
- Failure mode is defined
