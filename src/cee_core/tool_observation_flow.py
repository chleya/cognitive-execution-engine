"""End-to-end read-only tool observation flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .domain_context import DomainContext
from .domain_policy import evaluate_patch_policy_in_domain
from .event_log import EventLog
from .events import StateTransitionEvent
from .observations import (
    ObservationCandidate,
    build_observation_event,
    observation_from_tool_result,
    promote_observation_to_patch,
)
from .policy import build_transition_for_patch
from .state import StatePatch
from .tool_runner import InMemoryReadOnlyToolRunner
from .tools import (
    ToolCallEvent,
    ToolCallSpec,
    ToolResultEvent,
    build_tool_call_event,
)


@dataclass(frozen=True)
class ToolObservationFlowResult:
    """Result of a read-only tool observation flow."""

    tool_call_event: ToolCallEvent
    tool_result_event: ToolResultEvent
    observation: ObservationCandidate | None
    promotion_patch: StatePatch | None


@dataclass(frozen=True)
class PlannerToolExecutionResult:
    """Result of executing planner-proposed read-only tool calls."""

    plan_result: object
    tool_flow_results: tuple[ToolObservationFlowResult, ...]


def run_read_only_tool_observation_flow(
    call: ToolCallSpec,
    runner: InMemoryReadOnlyToolRunner,
    *,
    event_log: EventLog,
    promote_to_belief_key: str | None = None,
    domain_context: DomainContext | None = None,
) -> ToolObservationFlowResult:
    """Run read-only tool call through observation and optional promotion."""

    tool_call_event = build_tool_call_event(call, runner.registry)
    event_log.append(tool_call_event)

    if not tool_call_event.decision.allowed:
        tool_result_event = ToolResultEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status="failed",
            error_message=(
                f"tool policy blocked execution: "
                f"{tool_call_event.decision.verdict}"
            ),
        )
        event_log.append(tool_result_event)
        return ToolObservationFlowResult(
            tool_call_event=tool_call_event,
            tool_result_event=tool_result_event,
            observation=None,
            promotion_patch=None,
        )

    return run_allowed_tool_call_observation_flow(
        tool_call_event,
        runner,
        event_log=event_log,
        promote_to_belief_key=promote_to_belief_key,
        domain_context=domain_context,
    )


def run_allowed_tool_call_observation_flow(
    tool_call_event: ToolCallEvent,
    runner: InMemoryReadOnlyToolRunner,
    *,
    event_log: EventLog,
    promote_to_belief_key: str | None = None,
    domain_context: DomainContext | None = None,
) -> ToolObservationFlowResult:
    """Continue a tool observation flow from an already-audited allowed call."""

    if not tool_call_event.decision.allowed:
        raise ValueError("tool_call_event must be allowed before execution")

    tool_result_event = runner.run(tool_call_event.call, event_log=event_log)
    if tool_result_event.status != "succeeded":
        return ToolObservationFlowResult(
            tool_call_event=tool_call_event,
            tool_result_event=tool_result_event,
            observation=None,
            promotion_patch=None,
        )

    observation = observation_from_tool_result(tool_result_event)
    event_log.append(build_observation_event(observation))

    promotion_patch = None
    if promote_to_belief_key is not None:
        promotion_patch = promote_observation_to_patch(
            observation,
            belief_key=promote_to_belief_key,
        )
        event_log.append(
            _build_promotion_transition_event(
                promotion_patch,
                observation=observation,
                domain_context=domain_context,
            )
        )

    return ToolObservationFlowResult(
        tool_call_event=tool_call_event,
        tool_result_event=tool_result_event,
        observation=observation,
        promotion_patch=promotion_patch,
    )


def execute_plan_with_read_only_tools(
    plan,
    runner: InMemoryReadOnlyToolRunner,
    *,
    event_log: EventLog,
    promote_to_belief_keys: Mapping[str, str] | None = None,
    domain_context: DomainContext | None = None,
) -> PlannerToolExecutionResult:
    """Execute a plan and run only its allowed read-only tool proposals."""

    from .planner import execute_plan

    promotion_map = dict(promote_to_belief_keys or {})
    plan_result = execute_plan(plan, event_log=event_log, tool_registry=runner.registry)
    flow_results: list[ToolObservationFlowResult] = []

    for tool_call_event in plan_result.allowed_tool_calls:
        flow_results.append(
            run_allowed_tool_call_observation_flow(
                tool_call_event,
                runner,
                event_log=event_log,
                promote_to_belief_key=promotion_map.get(tool_call_event.call.call_id),
                domain_context=domain_context,
            )
        )

    return PlannerToolExecutionResult(
        plan_result=plan_result,
        tool_flow_results=tuple(flow_results),
    )


def _build_promotion_transition_event(
    promotion_patch: StatePatch,
    *,
    observation: ObservationCandidate,
    domain_context: DomainContext | None,
) -> StateTransitionEvent:
    reason = f"promote observation from {observation.source_tool}"
    if domain_context is None:
        return build_transition_for_patch(
            promotion_patch,
            actor="observation_promoter",
            reason=reason,
        )

    return StateTransitionEvent(
        patch=promotion_patch,
        policy_decision=evaluate_patch_policy_in_domain(promotion_patch, domain_context),
        actor="observation_promoter",
        reason=reason,
    )
