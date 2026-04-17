# Cognitive Execution Engine

An extensible cognitive execution engine with a fixed safety core.

CEE is not a model-first autonomous agent. It is a state-centered, event-sourced,
policy-guarded runtime where LLMs are constrained cognitive operators rather
than owners of system authority.

Core invariant:

```text
Input compiler structures.
Planner proposes.
Policy decides.
EventLog audits.
Replay applies only allowed transitions.
```

## Project Definition

CEE aims to be:

- more stable than a typical agent
- more flexible than a hard-coded workflow
- more continuous than pure RAG
- more realistic than an open-ended "universal system"

Its architecture is:

- `core-fixed`
- `primitive-general`
- `state-extensible`
- `domain-pluggable`

## Quick Start

```powershell
cd F:\cognitive-execution-engine
python -m pytest -q
python examples\stage0_demo.py
python examples\reasoning_step_demo.py
python examples\quality_report_demo.py
```

Current expected result:

```text
218 passed, 2 skipped
```

## Current Engine Surfaces

The engine currently provides:

- fixed core state trunk: `memory`, `goals`, `beliefs`, `self_model`, `policy`, `domain_data`, `meta`
- deterministic reducer and replay
- policy-mediated `StatePatch` transitions
- approval semantics for gated state mutations
- typed task and plan contracts
- constrained LLM task compiler boundary
- provider-neutral and env-gated provider boundaries
- tool contracts, read-only runner, planner-proposed read-only tool execution, observation flow, explicit observation promotion
- explicit domain context runtime entry
- replayable run artifacts and JSON event artifacts

## Example Flows

- `python examples\stage0_demo.py`: basic deterministic task -> plan -> policy -> replay demo
- `python examples\reasoning_step_demo.py`: small-step `TaskSpec -> ReasoningStep -> PlanSpec` demo, including a read-only docs tool path and deterministic narration output
- `python examples\quality_report_demo.py`: quality baseline report demo for replay, audit, narration, and policy metrics

## Test Philosophy

CEE treats tests as system-governance checks, not just module checks.

The repository now includes:

- contract tests for typed runtime objects
- boundary tests for authority and policy separation
- system invariant tests for replay, audit, and belief-promotion rules
- quality metric tests for replay, narration, audit coverage, and policy integrity
- probabilistic quality gates with evidence-aware thresholds

## Three-Layer Architecture

### 1. Core Layer

Fixed, safety-oriented surfaces:

- state storage `S(t)`
- event log
- permission policy
- approval and rollback semantics
- tool call contracts
- state transition rules

### 2. Cognitive Layer

General cognitive primitives:

- `observe`
- `interpret`
- `hypothesize`
- `plan`
- `act`
- `verify`
- `reflect`
- `escalate`

### 3. Domain Plugin Layer

Replaceable domain surfaces:

- tools
- glossary packs
- domain rules
- evaluators
- data connectors

## What This Project Is

- a fixed safety core for continuous task execution
- a bounded runtime for cognitive primitives
- an auditable and replayable execution engine
- a base for limited-domain migration through plugins

## What This Project Is Not

- not a universal autonomous agent
- not a digital human
- not a self-conscious system
- not a self-modifying core
- not a framework wrapper around chat history and tool calls

## Current Boundaries

- LLMs may structure input into `TaskSpec`
- LLMs may not generate `StatePatch`
- LLMs may not generate tool calls
- planner may propose tool calls
- only read-only in-memory tool execution exists
- runtime may enter explicit named domains
- tool results never become beliefs automatically
- belief promotion is explicit and still policy-mediated

## Canonical Direction

CEE is now defined as:

> an extensible cognitive execution engine for continuous tasks, with a fixed
> safety core, general cognitive primitives, extensible state graph semantics,
> and domain-pluggable surfaces.
