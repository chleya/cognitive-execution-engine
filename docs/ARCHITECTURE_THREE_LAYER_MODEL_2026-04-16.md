# Three-Layer Architecture Model

## Status

Canonical.

## Definition

CEE is organized as:

```text
core-fixed
primitive-general
state-extensible
domain-pluggable
```

## Layer 1: Core Layer

Fixed for stability:

- state storage `S(t)`
- event log
- permission policy
- approval and rollback semantics
- tool call contracts
- state transition rules

## Layer 2: Cognitive Layer

General cognitive primitives:

- `observe`
- `interpret`
- `hypothesize`
- `plan`
- `act`
- `verify`
- `reflect`
- `escalate`

These primitives are not business workflows. They are bounded units the engine
can reuse across domains.

## Layer 3: Domain Plugin Layer

Replaceable domain surfaces:

- tools
- domain vocabulary
- domain constraints
- evaluators
- data connectors

## Design Rule

Do not put generality in a giant universal workflow.

Put generality in the primitive layer, and keep the core fixed.
