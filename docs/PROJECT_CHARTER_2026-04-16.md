# CEE Project Charter

## Status

Canonical.

## Name

Cognitive Execution Engine, abbreviated as CEE.

中文名：可扩展认知执行引擎
副标题：面向连续任务的状态化、可审计、可迁移智能执行内核

## Core Position

CEE is an extensible cognitive execution engine with a fixed safety core.

It is not a model-first autonomous agent. It is not a digital human. It is not
a self-conscious system.

## Product Thesis

LLMs are useful cognitive operators, but they are poor owners of authority.

Therefore, the system must assign authority to explicit structures:

- state owns continuity
- policy owns permission
- event log owns history
- audit owns accountability
- human gate owns high-risk authorization
- LLM owns only bounded proposal, interpretation, extraction, and narration

## Architecture Thesis

CEE has three layers:

1. core layer: fixed, safety-oriented
2. cognitive layer: general primitives, not business templates
3. domain plugin layer: replaceable tools, rules, evaluators, connectors

The system's generality comes from cognitive primitives, not from a single
"universal workflow."

## MVP Goal

Build a minimal engine that can:

1. accept a structured task
2. load explicit state
3. compile work into bounded cognitive primitives
4. ask a deterministic planner or constrained LLM compiler for candidate work
5. check policy
6. execute only approved or allowed actions
7. preserve an audit trail
8. replay the transition deterministically

## Non-Goals

- universal autonomous agent
- open-ended self-improvement
- autonomous permission expansion
- persistent persona simulation
- full digital human
- production deployment before replay and audit exist

## MVP Domain Boundary

The first domain must remain deliberately small:

- single agent runtime
- one to two task domains
- 8 or fewer cognitive primitives
- 10 to 20 controlled tools
- read-heavy workflows first
- write actions behind mandatory approval
- no self-expansion of core policy

## Success Criteria

- state replay success rate: 100%
- high-risk action approval coverage: 100%
- out-of-policy tool call rate: 0
- schema-valid event rate: >= 99%
- model-generated state patch accepted only after validation: 0 direct writes
- migration from domain A to domain B changes plugins, not the safety core

## Language Guardrail

Do not describe `self_model` as consciousness, personhood, or autonomous self.

`self_model` is only a structured runtime description of:

- capability limits
- permission limits
- tool affordances
- risk posture
- calibration state
