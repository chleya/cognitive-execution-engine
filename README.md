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
pip install -e .
python -m pytest -q
python examples\workflow_demo.py
```

Current expected result:

```text
1125 passed, 2 skipped
```

### CLI Usage

```bash
# Run a task
cee run "analyze the codebase" --domain code_review --auto-approve

# With LLM provider
cee run "analyze the codebase" --llm-provider openai --model gpt-4

# With config file
cee run "analyze the codebase" --config cee_config.yaml

# Generate execution report
cee exec-report --log-file events.json --output-file report.md

# Calibrate self-model
cee calibrate
```

### API Usage

```bash
# Start API server
python -m cee_core.web_api

# Endpoints:
# POST /tasks              - Execute task
# GET  /state              - Get current state
# POST /state              - Update state (policy-gated)
# GET  /world              - Get WorldState (new architecture)
# POST /world/commitment   - Execute commitment (new architecture)
# GET  /reports/{run_id}   - Get execution report by run_id
# GET  /events             - Get event log
# WS   /ws/events          - Real-time event stream
# GET  /docs               - Swagger UI
```

## Current Engine Surfaces

The engine currently provides:

- fixed core state trunk: `memory`, `goals`, `beliefs`, `self_model`, `policy`, `domain_data`, `meta`
- deterministic reducer and replay
- policy-mediated `StatePatch` transitions
- approval semantics for gated state mutations
- typed task and plan contracts
- constrained LLM task compiler boundary
- provider-neutral and env-gated provider boundaries (OpenAI, Anthropic-compatible, static)
- tool contracts, read-only runner, planner-proposed read-only tool execution, observation flow, explicit observation promotion
- explicit domain context runtime entry
- replayable run artifacts and JSON event artifacts
- workflow orchestration with multi-step execution, variable passing, conditional steps
- YAML/JSON configuration management with environment variable overrides
- Markdown report generation with execution summary, decision trace, tool call history
- FastAPI REST + WebSocket API with real-time event streaming
- CLI with `run`, `exec-report`, `calibrate`, `validate`, `export`, `import` commands
- state persistence with event replay and snapshot support
- observability with metrics collection and debugging
- external gateway with HTTP and webhook integration

### New Architecture (World Model + Reality Commitment)

The engine is migrating to a generative world layer + reality commitment layer:

- `WorldState`: structured representation with entities, relations, hypotheses, anchored facts
- `CommitmentEvent`: reality interaction events (observe/act/tool_contact/internal_commit)
- `ModelRevisionEvent`: state corrections (expansion/correction/refinement)
- `CommitmentPolicy`: observe default allow, act requires reversibility, irreversible blocked
- `bridge.py`: compatible (not lossless) bidirectional State <-> WorldState conversion
- API: `/world` GET, `/world/commitment` POST with full closed loop
- API: `/reports/{run_id}` with RunArtifact lookup keyed by run_id
- safe-by-default API (`auto_approve=False`)

Migration phase: **Phase 1 bridge** (new architecture coexists with legacy).
See `docs/migration_plan.md` for the full migration strategy.

## Example Flows

- `python examples\workflow_demo.py`: multi-step workflow orchestration (document analysis, code review, report generation)
- `python examples\stage0_demo.py`: basic deterministic task -> plan -> policy -> replay demo
- `python examples\reasoning_step_demo.py`: small-step `TaskSpec -> ReasoningStep -> PlanSpec` demo
- `python examples\quality_report_demo.py`: quality baseline report demo
- `python examples\demo_document_analysis.py`: document analysis domain demo
- `python examples\demo_image_generation.py`: image generation domain demo

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
