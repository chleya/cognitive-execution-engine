# Next Agent Start Here

Primary machine-readable source:

- `handoff_state.json`

Read that first. This file is a human-readable mirror only.

## Current State

- Repo: `F:\cognitive-execution-engine`
- Validation: `python -m pytest -q` -> `1349 passed, 2 skipped`
- Current architecture includes:
  - `TaskSpec -> ReasoningStep -> PlanSpec` (legacy core, still used internally)
  - `WorldState + CommitmentEvent + ModelRevisionEvent` (primary architecture)
  - `bridge_state_to_world / bridge_world_to_state` (compatible, enhanced with raw_value and memory/domain_data round-trip)
  - `event_format` config: new (default) / dual (compat); legacy mode removed
  - Runtime produces CommitmentEvent/ModelRevisionEvent as primary event stream
  - `RunResult.world_state` populated from `EventLog.replay_world_state()`
  - `RunResult.replayed_state` derived from WorldState via `bridge_world_to_state` (not from StateTransitionEvent replay)
  - `runtime._execute_plan_in_domain` accepts WorldState directly (no State bridging for current_state)
  - `domain_policy.evaluate_patch_policy_in_domain` accepts current_beliefs/current_memory dicts (no State dependency)
  - `extract_beliefs_and_memory_from_world` in world_state.py extracts dicts from WorldState
  - `RevisionDelta.raw_value` carries original patch value for lossless replay
  - Only policy-allowed patches generate ModelRevisionEvent
  - `/tasks` endpoint: WorldState as primary state, saves directly, bridges back to legacy
  - `GET /world`: loads directly-saved WorldState first, falls back to bridge
  - `GET /tasks`: returns actual run_id list from store
  - `RunArtifact` includes `world_state_snapshot`
  - `RunArtifact.replay_state()` deprecated; use `world_state_snapshot` with `WorldState.from_dict()` instead
  - `EventLog.replay_state()` removed; use `replay(log.transition_events())` or `log.replay_world_state()`
  - Deprecated API endpoints removed (GET/POST /state, GET /report)
  - app-scoped StateStore (no module-level globals)
  - safe-by-default API (`auto_approve=False`)

## Migration Phase

The project is in **Phase 2 cutover**: WorldState is the primary state representation.

- Legacy: `State`, `StatePatch`, `StateTransitionEvent`, `PolicyDecision` (still used internally for policy evaluation)
- Primary: `WorldState`, `CommitmentEvent`, `ModelRevisionEvent`, `CommitmentPolicyDecision`
- WorldState is the sole state container (bridge.py removed; State/StatePatch retired)
- `event_format="new"` is the default; `"dual"` available for compat; `"legacy"` removed
- `EventLog.replay_state()` is deprecated; use `replay_world_state()` instead

See `docs/migration_plan.md` for the full migration strategy.

## Already Completed

- domain-aware observation promotion
- strict LLM task compiler field validation
- runtime integration for planner-proposed read-only tool flow
- deterministic `ReasoningStep` and `DeliberationEvent`
- narration renderer from audit events
- narration persisted into `RunArtifact`
- quality metrics and probabilistic quality gates
- task-level quality baselines
- belief confidence and evidence-weight updates
- machine-readable handoff state
- handoff validator
- handoff readiness report
- approval gate with runtime integration
- confidence gate connecting belief confidence to policy decisions
- explore mode with propose_redirect action
- dependency map for cross-module impact analysis
- self-observation and self-model calibration pipeline
- CLI entry point (cee run / report / validate / calibrate)
- end-to-end demo with full pipeline
- WorldState structured representation with entities, relations, hypotheses, anchored facts
- CommitmentEvent with observe/act/tool_contact/internal_commit kinds
- ModelRevisionEvent with expansion/correction/refinement kinds
- CommitmentPolicy: observe default allow, act requires reversibility, irreversible blocked
- bridge.py: compatible bidirectional State <-> WorldState conversion (enhanced: raw_value, memory/domain_data round-trip)
- API: /world GET, /world/commitment POST with full closed loop
- API: /reports/{run_id} with RunArtifact lookup and fallback to event log
- API: safe-by-default (auto_approve=False, CommitmentRequest Pydantic model)
- API-level integration tests covering /tasks, /world, /world/commitment, /reports/{run_id}
- Migration invariant tests: domain_data roundtrip, belief type preservation, dual path consistency
- Experiment 1: new structure eliminates repeated errors vs baseline
- Experiment 3: new architecture outperforms stacked solution
- TASKS-NEW-STATE-001: /tasks operates on WorldState directly
- PHASE2-CUTOVER-001: event_format default flipped to 'new', legacy mode removed
- RunResult.world_state field populated from EventLog.replay_world_state()
- RunArtifact.world_state_snapshot field
- EventLog.replay_state() deprecated with DeprecationWarning
- BehavioralSnapshot.commitment_count field, allow_rate considers commitments
- GET /world loads directly-saved WorldState first
- GET /tasks returns actual run_id list from store

## One Current Task

No active implementation task is assigned.

Validate current state and wait for the next explicit instruction.

If this file and `handoff_state.json` disagree, `handoff_state.json` wins.

## Next Task Candidates

1. ~~Remove bridge.py~~ DONE - all consumers use WorldState directly
2. Migrate RunResult.replayed_state from State to WorldState-native (breaking change, needs versioning) (STATE-INTERNALS-002)
3. Clean up legacy tests that still use State/StatePatch directly (LEGACY-TEST-CLEANUP-001)
4. Migrate persistence.py StateStore to WorldState-native storage (PERSISTENCE-MIGRATION-001)

## Control Philosophy

- Control the mode before the action surface.
- Control outcomes and gates, not just editable files.
- Use explicit stage gates so progress is checkable and reversible.
- Use task packets and claim metadata so completion and truthfulness are machine-checkable.
- Escalate to diagnosis instead of widening scope after repeated failure.

## Task Packet

- task ID: `HANDOFF-VALIDATE-001`
- owner: `next-agent`
- fallback plan: Switch to diagnose_only mode, produce blocker summary, and stop expanding scope.
- commands:
  - python -m pytest -q tests\test_handoff_validator.py
  - python -m pytest -q tests\test_handoff_stage_checker.py
  - python -m pytest -q
- artifact paths:
  - handoff_state.json
  - NEXT_AGENT_START_HERE.md
- acceptance gates:
  - focused handoff tests pass
  - handoff report Ready == yes
  - handoff report Warning count == 0
  - full test suite passes
- hold conditions:
  - a required change falls outside primary_files without a focused failing check proving it
  - a requested change would modify runtime or policy authority semantics
  - focused validation fails twice on the same issue
- required update format:
  - Task ID
  - Status
  - Commands run
  - Artifact paths
  - Key metrics
  - Gate pass/fail
  - Blocker
  - Next action

## Claim Metadata

- validation source: `local_pytest`
- validation scope: `focused_handoff_plus_full_suite`
- cost model: `not_applicable`
- oracle assumption: `false`
- notes:
  - handoff readiness is based on validator, stage checker, and local test execution
  - report cleanliness is local and does not imply remote/runtime control coverage
  - project is in Phase 2 cutover: event_format='new' is default, legacy mode removed
  - WorldState is the primary state representation; legacy State is derived via bridge

## Red-Line Rules

- do not change runtime authority boundaries
- do not change policy semantics
- do not treat narration as execution authority
- do not claim focused checks replace full verification
- do not present handoff readiness as proof of runtime safety outside the checked handoff path
- do not claim bridge is lossless (it is compatible, with known limitations documented in migration_plan.md)
- do not re-introduce legacy event_format as default

## Global Acceptance Gates

- task packet acceptance_gates all satisfied
- no red_line_rules violated
- stage_gates all report ready
- claim_metadata remains truthful to the executed validation scope

## Execution Mode

- `validate_only`
- fallback mode: `diagnose_only`

## Module Map

### Legacy Core
- ~~`state.py`~~: REMOVED - WorldState is the sole state container
- `events.py`: event model (Event, StateTransitionEvent, DeliberationEvent)
- `event_log.py`: event log (EventLog, replay_transition_events, replay_serialized_transition_events)
- `audit_policy.py`: audit policy (CompilerAuditPolicy)
- `approval.py`: human approval (ApprovalDecision, approve_transition, ApprovalGate, ApprovalGateResult, StaticApprovalProvider, CallbackApprovalProvider)
- `planner.py`: planner (PlanSpec, plan_from_task, execute_plan)
- `tasks.py`: task spec (TaskSpec, TaskLevel, compile_task, classify_task_level)

### LLM Integration
- `llm_task_adapter.py`: LLM task compiler adapter (LLMTaskCompiler, compile_task_with_llm_adapter)
- `llm_provider.py`: LLM provider interface (LLMProvider, LLMProviderRequest, LLMProviderResponse)
- `openai_provider.py`: OpenAI provider
- `anthropic_compatible_provider.py`: Anthropic-compatible provider
- `optional_provider.py`: optional provider boundary (EnvironmentLLMProvider)

### Tools & Observation
- `tools.py`: tool contracts (ToolSpec, ToolCallSpec, ToolRegistry, evaluate_tool_call_policy)
- `tool_runner.py`: read-only tool runner (InMemoryReadOnlyToolRunner, ReadToolHandler)
- `tool_observation_flow.py`: tool observation flow
- `observations.py`: observation candidates and promotion
- `deliberation.py`: reasoning steps (ReasoningStep, deliberate_next_action)
- `belief_update.py`: belief confidence updates

### Quality & Reporting
- `narration.py`: narration renderer (render_event_narration)
- `artifacts.py`: artifact serialization
- `run_artifact.py`: run artifact (RunArtifact, run_result_to_artifact, replay_run_artifact_json)
- `quality_metrics.py`: quality metrics (QualityMetrics, compute_quality_metrics)
- `quality_report.py`: quality report (build_quality_report, render_quality_report)
- `quality_thresholds.py`: quality thresholds and gates
- `report_generator.py`: Markdown report generation from RunArtifact or event log

### Domain & Configuration
- `domain_context.py`: domain context runtime entry (DomainContext, build_domain_context)
- `domain_plugins.py`: domain plugin contracts (DomainPluginRegistry, DomainPluginPack)
- ~~`domain_policy.py`~~: REMOVED - domain policy now handled through domain plugins
- `config.py`: YAML/JSON configuration with env var overrides (CEEConfig, PersistenceConfig, etc.)
- `schemas.py`: schema versioning (require_schema_version, SCHEMA_MAJOR_VERSION)
- `primitives.py`: cognitive primitives (CognitivePrimitive, validate_primitives)

### Handoff & Calibration
- `handoff_validator.py`: handoff validation (validate_handoff_state, validate_handoff_state_file)
- `handoff_stage_checker.py`: handoff stage gates (assess_handoff_stage_gates)
- `handoff_report.py`: handoff readiness report (build_handoff_report, render_handoff_report)
- `confidence_gate.py`: confidence-aware policy escalation
- `self_observation.py`: behavioral pattern extraction
- `calibration.py`: self-model calibration pipeline

### Infrastructure
- `runtime.py`: runtime orchestrator (execute_task, execute_task_in_domain, approval_gate integration)
- `cli.py`: CLI entry point (cee run, cee report, cee validate, cee calibrate)
- `web_api.py`: FastAPI REST + WebSocket API with /world, /world/commitment, /reports/{run_id}
- `persistence.py`: file-based persistence for State, WorldState, CommitmentEvent, RevisionEvent, RunArtifact
- `observability.py`: execution observer with metrics collection and debugging
- `import_export.py`: import/export manager for execution state packages

### New Architecture (World Model)
- `world_schema.py`: shared protocol types (WorldEntity, WorldRelation, WorldHypothesis, RevisionDelta) [NEW]
- `world_state.py`: WorldState with entities, relations, hypotheses, anchored facts [PRIMARY]
- `commitment_policy.py`: commitment policy evaluation (DefaultCommitmentPolicy, evaluate_commitment_policy)
- `revision_policy.py`: revision policy evaluation (DefaultRevisionPolicy, evaluate_revision_policy)
- `llm_proposal.py`: LLM proposal adapters with validation, policy, approval pipeline
- `memory_promotion.py`: memory promotion pipeline with policy validation
- `calibration.py`: self-model calibration with forbidden key/value pattern enforcement
- `tool_gateway.py`: bounded tool execution boundary with policy + approval + audit

### Specialized Modules
- `failure_modes.py`: unified failure classification (FailureMode, classify_exception, record_failure)
- `change_test.py`: change test automation (ChangeProposal, evaluate_change_test)
- `principles.py`: physics principles (Noether, least action, free energy, replay symmetry, state-policy duality)
- `common_sense.py`: common sense cognition (conservation law, ground state, second law, equipartition, uncertainty principle)
- `hypothesis.py`: hypothesis generation and verification cycle

## Primary Files

- `handoff_state.json`
- `NEXT_AGENT_START_HERE.md`
- `TASK_CHECKLIST.md`
- `RECOVERY_PLAYBOOK.md`
- `HANDOFF_PROMPT.md`
- `src/cee_core/handoff_stage_checker.py`
- `src/cee_core/handoff_validator.py`
- `src/cee_core/handoff_report.py`
- `tests/test_handoff_validator.py`
- `tests/test_handoff_stage_checker.py`

If `allowed_files` is not specified, it defaults to `primary_files`.

## Expansion Rule

Only expand beyond `primary_files` if a focused failure directly proves another file must change, and stop before editing more than 3 files outside `primary_files`.

## Forbidden Scope

- do not change runtime authority boundaries
- do not change policy semantics
- do not change planner authority semantics
- do not add network or write-capable tools
- do not refactor unrelated modules
- do not rewrite existing docs beyond small synchronization edits

## Required Checks

Run these after changes:

```powershell
python -m pytest -q tests\test_handoff_validator.py
python -m pytest -q tests\test_handoff_stage_checker.py
python -m pytest -q
```

## Success Predicates

- `tests/test_handoff_validator.py` passes
- `tests/test_handoff_stage_checker.py` passes
- handoff report shows `Ready: yes`
- handoff report warning count == 0
- only handoff files change in `validate_only` mode

## Failure Predicates

- focused validation fails twice on the same issue
- scope expansion is needed without a focused failing check proving it
- a requested change would modify runtime or policy authority semantics
- the handoff mirror drifts from `handoff_state.json`

## Stage Gates

1. `read_state`
2. `restate_scope`
3. `inspect_minimum_context`
4. `edit_if_needed`
5. `focused_verify`
6. `full_verify`
7. `emit_handoff_report`

## Stop Conditions

Stop and hand off if any of these happen:

- more than 3 files outside the allowed list need edits
- a change appears to require modifying policy or runtime authority rules
- tests fail for reasons unrelated to the current task
- import cycles appear in unrelated modules

## Source Of Truth

If you are unsure, prefer these in order:

1. `docs/PRINCIPLE_BASELINE_2026-04-16.md`
2. `ARCHITECTURE.md`
3. `docs/migration_plan.md`
4. `README.md`
5. tests
6. current code contracts

## First Command Sequence

```powershell
cd F:\cognitive-execution-engine
python -m pytest -q tests\test_handoff_validator.py
```
