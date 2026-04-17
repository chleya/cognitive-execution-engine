# Next Agent Start Here

Primary machine-readable source:

- `handoff_state.json`

Read that first. This file is a human-readable mirror only.

## Current State

- Repo: `F:\cognitive-execution-engine`
- Validation: `python -m pytest -q` -> `382 passed, 2 skipped`
- Current architecture includes:
  - `TaskSpec -> ReasoningStep -> PlanSpec`
  - deterministic narration derived from the audit log
  - `RunArtifact.narration_lines`
  - `task_level`-based quality baselines
  - confidence-bearing belief promotion

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

## One Current Task

No active implementation task is assigned.

Validate current state and wait for the next explicit instruction.

If this file and `handoff_state.json` disagree, `handoff_state.json` wins.

## Next Task Candidates

None. Awaiting explicit instruction.

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

## Red-Line Rules

- do not change runtime authority boundaries
- do not change policy semantics
- do not treat narration as execution authority
- do not claim focused checks replace full verification
- do not present handoff readiness as proof of runtime safety outside the checked handoff path

## Global Acceptance Gates

- task packet acceptance_gates all satisfied
- no red_line_rules violated
- stage_gates all report ready
- claim_metadata remains truthful to the executed validation scope

## Execution Mode

- `validate_only`
- fallback mode: `diagnose_only`

## Module Map

- `state.py`: core state kernel (State, StatePatch, apply_patch, reduce_event, replay)
- `events.py`: event model (Event, StateTransitionEvent, DeliberationEvent)
- `event_log.py`: event log (EventLog, replay_transition_events, replay_serialized_transition_events)
- `policy.py`: policy engine (evaluate_patch_policy, build_transition_for_patch)
- `audit_policy.py`: audit policy (CompilerAuditPolicy)
- `approval.py`: human approval (ApprovalDecision, approve_transition, ApprovalGate, ApprovalGateResult, StaticApprovalProvider, CallbackApprovalProvider)
- `planner.py`: planner (PlanSpec, plan_from_task, execute_plan)
- `tasks.py`: task spec (TaskSpec, TaskLevel, compile_task, classify_task_level)
- `llm_task_adapter.py`: LLM task compiler adapter (LLMTaskCompiler, compile_task_with_llm_adapter)
- `llm_provider.py`: LLM provider interface (LLMProvider, LLMProviderRequest, LLMProviderResponse)
- `openai_provider.py`: OpenAI provider (build_openai_task_compiler_provider, openai_responses_task_compiler_transport)
- `anthropic_compatible_provider.py`: Anthropic-compatible provider
- `optional_provider.py`: optional provider boundary (EnvironmentLLMProvider)
- `tools.py`: tool contracts (ToolSpec, ToolCallSpec, ToolRegistry, evaluate_tool_call_policy)
- `tool_runner.py`: read-only tool runner (InMemoryReadOnlyToolRunner, ReadToolHandler)
- `tool_observation_flow.py`: tool observation flow (run_read_only_tool_observation_flow, execute_plan_with_read_only_tools)
- `observations.py`: observation candidates and promotion (ObservationCandidate, promote_observation_to_patch)
- `deliberation.py`: reasoning steps (ReasoningStep, deliberate_next_action)
- `belief_update.py`: belief confidence updates (promote_observation_to_belief_patch)
- `narration.py`: narration renderer (render_event_narration)
- `artifacts.py`: artifact serialization (events_to_payloads, replay_event_payload_artifact)
- `run_artifact.py`: run artifact (RunArtifact, run_result_to_artifact, replay_run_artifact_json)
- `schemas.py`: schema versioning (require_schema_version, SCHEMA_MAJOR_VERSION)
- `primitives.py`: cognitive primitives (CognitivePrimitive, validate_primitives)
- `domain_context.py`: domain context runtime entry (DomainContext, build_domain_context)
- `domain_plugins.py`: domain plugin contracts (DomainPluginRegistry, DomainPluginPack)
- `domain_policy.py`: domain policy overrides (evaluate_patch_policy_in_domain)
- `quality_metrics.py`: quality metrics (QualityMetrics, compute_quality_metrics)
- `quality_report.py`: quality report (build_quality_report, render_quality_report)
- `quality_thresholds.py`: quality thresholds and gates (assess_quality_gates, assess_quality_gates_for_run)
- `handoff_validator.py`: handoff validation (validate_handoff_state, validate_handoff_state_file)
- `handoff_stage_checker.py`: handoff stage gates (assess_handoff_stage_gates)
- `handoff_report.py`: handoff readiness report (build_handoff_report, render_handoff_report)
- `runtime.py`: runtime orchestrator (execute_task, execute_task_in_domain, approval_gate integration)
- `confidence_gate.py`: confidence-aware policy escalation (evaluate_confidence_gate, ConfidenceGateConfig)
- `self_observation.py`: behavioral pattern extraction (extract_behavioral_snapshot, BehavioralSnapshot, CalibrationProposal)
- `calibration.py`: self-model calibration pipeline (run_calibration_cycle, CalibrationResult)
- `cli.py`: CLI entry point (cee run, cee report, cee validate, cee calibrate)

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
2. `README.md`
3. tests
4. current code contracts

## First Command Sequence

```powershell
cd F:\cognitive-execution-engine
python -m pytest -q tests\test_handoff_validator.py
```
