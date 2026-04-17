"""Deterministic planning pipeline for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import uuid4

from .deliberation import ReasoningStep
from .event_log import EventLog
from .events import StateTransitionEvent
from .policy import build_transition_for_patch
from .schemas import PLAN_SCHEMA_VERSION, require_schema_version
from .state import StatePatch
from .tasks import TaskSpec
from .tools import ToolCallEvent, ToolCallSpec, ToolRegistry, build_tool_call_event


@dataclass(frozen=True)
class PlanSpec:
    """A bounded plan expressed as candidate state patches.

    Stage 0 plans are deterministic and contain no model output. Later LLM
    adapters must compile into this shape before policy evaluation.
    """

    objective: str
    candidate_patches: tuple[StatePatch, ...]
    proposed_tool_calls: tuple[ToolCallSpec, ...] = ()
    plan_id: str = field(default_factory=lambda: f"pl_{uuid4().hex}")
    actor: str = "planner"

    @classmethod
    def from_patches(
        cls,
        *,
        objective: str,
        candidate_patches: Iterable[StatePatch],
        actor: str = "planner",
    ) -> "PlanSpec":
        return cls(
            objective=objective,
            candidate_patches=tuple(candidate_patches),
            proposed_tool_calls=(),
            actor=actor,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "plan_id": self.plan_id,
            "objective": self.objective,
            "actor": self.actor,
            "candidate_patches": [
                patch.to_dict() for patch in self.candidate_patches
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
        patches = payload.get("candidate_patches", ())
        return cls(
            plan_id=str(payload["plan_id"]),
            objective=str(payload["objective"]),
            actor=str(payload.get("actor", "planner")),
            candidate_patches=tuple(
                StatePatch.from_dict(patch) for patch in patches  # type: ignore[arg-type]
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
    """Result of compiling a plan into audited transition events."""

    plan: PlanSpec
    events: tuple[StateTransitionEvent, ...]
    tool_call_events: tuple[ToolCallEvent, ...] = ()

    @property
    def allowed(self) -> tuple[StateTransitionEvent, ...]:
        return tuple(event for event in self.events if event.policy_decision.allowed)

    @property
    def blocked(self) -> tuple[StateTransitionEvent, ...]:
        return tuple(event for event in self.events if event.policy_decision.blocked)

    @property
    def requires_approval(self) -> tuple[StateTransitionEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.policy_decision.verdict == "requires_approval"
        )

    @property
    def denied(self) -> tuple[StateTransitionEvent, ...]:
        return tuple(
            event for event in self.events if event.policy_decision.verdict == "deny"
        )

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
    """Evaluate a deterministic plan and append all transition attempts."""

    log = event_log or EventLog()
    events: list[StateTransitionEvent] = []
    tool_call_events: list[ToolCallEvent] = []

    for patch in plan.candidate_patches:
        event = build_transition_for_patch(
            patch,
            actor=plan.actor,
            reason=f"plan:{plan.plan_id}:{plan.objective}",
        )
        log.append(event)
        events.append(event)

    if plan.proposed_tool_calls:
        if tool_registry is None:
            raise ValueError("tool_registry is required when plan has proposed_tool_calls")
        for call in plan.proposed_tool_calls:
            tool_event = build_tool_call_event(call, tool_registry, actor=plan.actor)
            log.append(tool_event)
            tool_call_events.append(tool_event)

    return PlanExecutionResult(
        plan=plan,
        events=tuple(events),
        tool_call_events=tuple(tool_call_events),
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
            candidate_patches=(),
            proposed_tool_calls=(),
            actor=actor,
        )

    patches = [
        StatePatch(section="goals", key="active", op="set", value=[task.task_id]),
        StatePatch(
            section="beliefs",
            key=f"task.{task.task_id}.objective",
            op="set",
            value=task.objective,
        ),
        StatePatch(
            section="beliefs",
            key=f"task.{task.task_id}.domain_name",
            op="set",
            value=task.domain_name,
        ),
        StatePatch(
            section="memory",
            key="working",
            op="append",
            value={
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
        patches.append(
            StatePatch(
                section="self_model",
                key="last_medium_or_high_risk_task",
                op="set",
                value=task.task_id,
            )
        )

    proposed_tool_calls = _propose_read_only_tool_calls(
        task,
        tool_registry,
        reasoning_step,
    )

    return PlanSpec(
        objective=task.objective,
        candidate_patches=tuple(patches),
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
