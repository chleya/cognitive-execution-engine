"""Deterministic planning pipeline for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import uuid4

from .commitment import CommitmentEvent, CommitmentKind, Reversibility
from .commitment_policy import CommitmentPolicyDecision
from .deliberation import ReasoningStep
from .event_log import EventLog
from .revision import ModelRevisionEvent
from .schemas import PLAN_SCHEMA_VERSION, require_schema_version
from .tasks import TaskSpec
from .tools import ToolCallEvent, ToolCallSpec, ToolRegistry, build_tool_call_event
from .world_schema import RevisionDelta


@dataclass(frozen=True)
class DeltaPolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    commitment_kind: CommitmentKind = "act"
    reversibility: Reversibility = "reversible"


def evaluate_delta_policy(delta: RevisionDelta) -> DeltaPolicyDecision:
    target_kind = delta.target_kind
    target_ref = delta.target_ref

    if target_ref.startswith("policy.") or target_ref.startswith("meta."):
        return DeltaPolicyDecision(
            allowed=False,
            requires_approval=False,
            reason=f"policy/meta patch denied by Stage 0 policy: {target_ref}",
            commitment_kind="internal_commit",
            reversibility="irreversible",
        )

    if target_ref.startswith("tool_affordances."):
        return DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason=f"tool_affordances patch requires approval: {target_ref}",
            commitment_kind="internal_commit",
            reversibility="reversible",
        )

    if target_kind == "self_update":
        return DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason=f"self_model patch requires approval: {target_ref}",
            commitment_kind="internal_commit",
            reversibility="reversible",
        )

    if target_kind == "goal_update":
        return DeltaPolicyDecision(
            allowed=True,
            requires_approval=False,
            reason="goals patch allowed by Stage 0 policy",
            commitment_kind="act",
            reversibility="partially_reversible",
        )

    if target_kind in ("entity_update", "entity_add"):
        if target_ref.startswith("memory."):
            return DeltaPolicyDecision(
                allowed=True,
                requires_approval=False,
                reason="memory patch allowed by Stage 0 policy",
                commitment_kind="internal_commit",
                reversibility="reversible",
            )
        return DeltaPolicyDecision(
            allowed=True,
            requires_approval=False,
            reason="beliefs patch allowed by Stage 0 policy",
            commitment_kind="observe",
            reversibility="reversible",
        )

    if target_kind in ("hypothesis_add", "hypothesis_update", "anchor_add"):
        return DeltaPolicyDecision(
            allowed=True,
            requires_approval=False,
            reason=f"{target_kind} allowed by Stage 0 policy",
            commitment_kind="observe",
            reversibility="reversible",
        )

    return DeltaPolicyDecision(
        allowed=True,
        requires_approval=False,
        reason=f"{target_kind} patch allowed by default policy",
        commitment_kind="internal_commit",
        reversibility="reversible",
    )


def evaluate_delta_policy_in_domain(
    delta: RevisionDelta,
    domain_context: "DomainContext",
    *,
    current_beliefs: dict[str, object] | None = None,
    current_memory: dict[str, object] | None = None,
) -> DeltaPolicyDecision:
    base = evaluate_delta_policy(delta)
    decision = _apply_domain_overlay(delta, base, domain_context)
    return decision


def _apply_domain_overlay(
    delta: RevisionDelta,
    base: DeltaPolicyDecision,
    domain_context: "DomainContext",
) -> DeltaPolicyDecision:
    pack = domain_context.plugin_pack
    if pack is None:
        return base

    section = _infer_section_from_delta(delta)

    if section in pack.denied_patch_sections:
        return DeltaPolicyDecision(
            allowed=False,
            requires_approval=False,
            reason=(
                f"domain policy denies patch section '{section}' "
                f"in domain '{domain_context.domain_name}'"
            ),
            commitment_kind=base.commitment_kind,
            reversibility=base.reversibility,
        )

    if section in pack.approval_required_patch_sections:
        if not base.allowed:
            return base
        return DeltaPolicyDecision(
            allowed=False,
            requires_approval=True,
            reason=(
                f"domain policy requires approval for patch section "
                f"'{section}' in domain '{domain_context.domain_name}'"
            ),
            commitment_kind=base.commitment_kind,
            reversibility=base.reversibility,
        )

    return base


def _infer_section_from_delta(delta: RevisionDelta) -> str:
    if delta.target_kind == "goal_update":
        return "goals"
    if delta.target_kind == "self_update":
        return "self_model"
    if delta.target_ref.startswith("memory."):
        return "memory"
    if delta.target_ref.startswith("domain."):
        return "domain_data"
    return "beliefs"


@dataclass(frozen=True)
class PlanSpec:
    """A bounded plan expressed as candidate revision deltas.

    Stage 0 plans are deterministic and contain no model output. Later LLM
    adapters must compile into this shape before policy evaluation.
    """

    objective: str
    candidate_deltas: tuple[RevisionDelta, ...]
    proposed_tool_calls: tuple[ToolCallSpec, ...] = ()
    plan_id: str = field(default_factory=lambda: f"pl_{uuid4().hex}")
    actor: str = "planner"

    @classmethod
    def from_deltas(
        cls,
        *,
        objective: str,
        candidate_deltas: Iterable[RevisionDelta],
        actor: str = "planner",
    ) -> "PlanSpec":
        return cls(
            objective=objective,
            candidate_deltas=tuple(candidate_deltas),
            proposed_tool_calls=(),
            actor=actor,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "objective": self.objective,
            "actor": self.actor,
            "candidate_deltas": [
                delta.to_dict() for delta in self.candidate_deltas
            ],
            "proposed_tool_calls": [
                {
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "arguments": call.arguments,
                }
                for call in self.proposed_tool_calls
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PlanSpec":
        require_schema_version(payload, PLAN_SCHEMA_VERSION)
        deltas_data = payload.get("candidate_deltas", ())
        if not deltas_data:
            deltas_data = payload.get("candidate_patches", ())
        return cls(
            plan_id=str(payload["plan_id"]),
            objective=str(payload["objective"]),
            actor=str(payload.get("actor", "planner")),
            candidate_deltas=tuple(
                RevisionDelta.from_dict(d) for d in deltas_data  # type: ignore[arg-type]
            ),
            proposed_tool_calls=tuple(
                ToolCallSpec(
                    call_id=str(call["call_id"]),
                    tool_name=str(call["tool_name"]),
                    arguments=call["arguments"],  # type: ignore[index]
                )
                for call in payload.get("proposed_tool_calls", ())  # type: ignore[arg-type]
            ),
        )


@dataclass(frozen=True)
class PlanExecutionResult:
    """Result of compiling a plan into audited commitment/revision events."""

    plan: PlanSpec
    commitment_events: tuple[CommitmentEvent, ...] = ()
    revision_events: tuple[ModelRevisionEvent, ...] = ()
    policy_decisions: tuple[DeltaPolicyDecision, ...] = ()
    tool_call_events: tuple[ToolCallEvent, ...] = ()

    @property
    def allowed_count(self) -> int:
        return sum(1 for d in self.policy_decisions if d.allowed and not d.requires_approval)

    @property
    def blocked_count(self) -> int:
        return sum(1 for d in self.policy_decisions if not d.allowed and not d.requires_approval)

    @property
    def requires_approval_count(self) -> int:
        return sum(1 for d in self.policy_decisions if d.requires_approval)

    @property
    def allowed_tool_calls(self) -> tuple[ToolCallEvent, ...]:
        return tuple(event for event in self.tool_call_events if event.decision.allowed)

    @property
    def blocked_tool_calls(self) -> tuple[ToolCallEvent, ...]:
        return tuple(event for event in self.tool_call_events if event.decision.blocked)


def execute_plan(
    plan: PlanSpec,
    event_log: EventLog | None = None,
    *,
    tool_registry: ToolRegistry | None = None,
) -> PlanExecutionResult:
    """Evaluate a deterministic plan and append all commitment/revision events."""

    log = event_log or EventLog()
    commitment_events: list[CommitmentEvent] = []
    revision_events: list[ModelRevisionEvent] = []
    policy_decisions: list[DeltaPolicyDecision] = []
    tool_call_events: list[ToolCallEvent] = []
    prior_state_id = "ws_0"

    for i, delta in enumerate(plan.candidate_deltas):
        decision = evaluate_delta_policy(delta)
        policy_decisions.append(decision)

        ce = _build_commitment_from_delta(delta, decision, plan, i)
        commitment_events.append(ce)
        log.append(ce)

        if decision.allowed and not decision.requires_approval:
            resulting_state_id = f"ws_{i + 1}"
            rev = _build_revision_from_delta(delta, prior_state_id, resulting_state_id, ce, plan)
            revision_events.append(rev)
            log.append(rev)
            prior_state_id = resulting_state_id

    if plan.proposed_tool_calls:
        if tool_registry is None:
            raise ValueError("tool_registry is required when plan has proposed_tool_calls")
        for call in plan.proposed_tool_calls:
            tool_event = build_tool_call_event(call, tool_registry, actor=plan.actor)
            log.append(tool_event)
            tool_call_events.append(tool_event)

    return PlanExecutionResult(
        plan=plan,
        commitment_events=tuple(commitment_events),
        revision_events=tuple(revision_events),
        policy_decisions=tuple(policy_decisions),
        tool_call_events=tuple(tool_call_events),
    )


def _build_commitment_from_delta(
    delta: RevisionDelta,
    decision: DeltaPolicyDecision,
    plan: PlanSpec,
    index: int,
) -> CommitmentEvent:
    return CommitmentEvent(
        event_id=f"ce-pl-{plan.plan_id}-{index}",
        source_state_id="",
        commitment_kind=decision.commitment_kind,
        intent_summary=f"plan:{plan.plan_id}:{plan.objective}",
        action_summary=f"{delta.target_kind} {delta.target_ref}",
        success=decision.allowed and not decision.requires_approval,
        reversibility=decision.reversibility,
        requires_approval=decision.requires_approval,
    )


def _build_revision_from_delta(
    delta: RevisionDelta,
    prior_state_id: str,
    resulting_state_id: str,
    commitment: CommitmentEvent,
    plan: PlanSpec,
) -> ModelRevisionEvent:
    revision_kind = "expansion"
    if delta.target_kind == "self_update":
        revision_kind = "recalibration"
    elif delta.target_kind == "goal_update":
        revision_kind = "confirmation"

    return ModelRevisionEvent(
        revision_id=f"rev-{commitment.event_id}",
        prior_state_id=prior_state_id,
        caused_by_event_id=commitment.event_id,
        revision_kind=revision_kind,
        deltas=(delta,),
        resulting_state_id=resulting_state_id,
        revision_summary=delta.justification or f"Delta: {delta.target_kind} {delta.target_ref}",
    )


def plan_from_task(
    task: TaskSpec,
    *,
    actor: str = "deterministic-planner",
    tool_registry: ToolRegistry | None = None,
    reasoning_step: ReasoningStep | None = None,
) -> PlanSpec:
    """Create a deterministic Stage 0 plan from a structured task."""

    if reasoning_step is not None and reasoning_step.chosen_action == "propose_redirect":
        return PlanSpec(
            objective=f"redirect: {task.objective}",
            candidate_deltas=(),
            proposed_tool_calls=(),
            actor=actor,
        )

    deltas = [
        RevisionDelta(
            delta_id=f"delta-goals-active-{task.task_id}",
            target_kind="goal_update",
            target_ref="goals.active",
            before_summary="no active goal",
            after_summary=f"active goal: {task.task_id}",
            justification=f"set active goal from task {task.task_id}",
            raw_value=[task.task_id],
        ),
        RevisionDelta(
            delta_id=f"delta-beliefs-obj-{task.task_id}",
            target_kind="entity_update",
            target_ref=f"beliefs.task.{task.task_id}.objective",
            before_summary="objective not set",
            after_summary=task.objective,
            justification=f"set task objective from task {task.task_id}",
            raw_value=task.objective,
        ),
        RevisionDelta(
            delta_id=f"delta-beliefs-domain-{task.task_id}",
            target_kind="entity_update",
            target_ref=f"beliefs.task.{task.task_id}.domain_name",
            before_summary="domain not set",
            after_summary=task.domain_name,
            justification=f"set task domain from task {task.task_id}",
            raw_value=task.domain_name,
        ),
        RevisionDelta(
            delta_id=f"delta-memory-working-{task.task_id}",
            target_kind="entity_update",
            target_ref="memory.working",
            before_summary="no working memory entry",
            after_summary=f"task {task.task_id} working memory",
            justification=f"append working memory from task {task.task_id}",
            raw_value={
                "task_id": task.task_id,
                "domain_name": task.domain_name,
                "kind": task.kind,
                "risk_level": task.risk_level,
                "task_level": task.task_level,
                "requested_primitives": list(task.requested_primitives),
                "confidence": 1.0,
                "evidence_count": 2,
                "provenance": "deterministic_planner",
            },
        ),
    ]

    if task.risk_level != "low":
        deltas.append(
            RevisionDelta(
                delta_id=f"delta-self-risk-{task.task_id}",
                target_kind="self_update",
                target_ref="self_model.last_medium_or_high_risk_task",
                before_summary="no recent risk task",
                after_summary=task.task_id,
                justification=f"record medium/high risk task {task.task_id}",
                raw_value=task.task_id,
            )
        )

    proposed_tool_calls = _propose_read_only_tool_calls(
        task,
        tool_registry,
        reasoning_step,
    )

    return PlanSpec(
        objective=task.objective,
        candidate_deltas=tuple(deltas),
        proposed_tool_calls=proposed_tool_calls,
        actor=actor,
    )


def _propose_read_only_tool_calls(
    task: TaskSpec,
    tool_registry: ToolRegistry | None,
    reasoning_step: ReasoningStep | None,
) -> tuple[ToolCallSpec, ...]:
    if tool_registry is None:
        return ()
    if tool_registry.get("read_docs") is None:
        return ()
    if reasoning_step is not None and reasoning_step.chosen_action != "request_read_tool":
        return ()
    if task.kind != "analysis" or "observe" not in task.requested_primitives:
        return ()

    lowered_objective = task.objective.lower()
    doc_tokens = ("read docs", "read documentation", "search docs", "search documentation")
    if not any(token in lowered_objective for token in doc_tokens):
        return ()

    query = task.objective
    for prefix in doc_tokens:
        if prefix in lowered_objective:
            start = lowered_objective.index(prefix) + len(prefix)
            extracted = task.objective[start:].strip(" :,-")
            if extracted:
                query = extracted
            break

    return (ToolCallSpec(tool_name="read_docs", arguments={"query": query}),)
