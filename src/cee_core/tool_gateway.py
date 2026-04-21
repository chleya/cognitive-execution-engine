"""Tool Gateway: bounded execution boundary for all tool contacts.

The Tool Gateway is the single entry point for all tool execution in the
cognitive execution engine. It enforces:

1. Policy check before execution (evaluate_tool_call_policy)
2. Approval gate for write/external_side_effect tools
3. Bounded execution with timeout and error handling
4. Complete audit trail via EventLog (CommitmentEvent + ToolResultEvent)
5. Automatic RevisionDelta promotion from observation results
6. ModelRevisionEvent recording for state transitions

Key invariant: the gateway only proposes and records. It does not own
execution authority. All state transitions must still go through the
policy engine and audit trail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .commitment import CommitmentEvent, complete_commitment
from .event_log import EventLog
from .observations import (
    ObservationCandidate,
    build_observation_event,
    observation_from_tool_result,
    promote_observation_to_delta,
)
from .planner import DeltaPolicyDecision, evaluate_delta_policy
from .revision import ModelRevisionEvent
from .tools import (
    ToolCallSpec,
    ToolPolicyDecision,
    ToolRegistry,
    ToolResultEvent,
    ToolRisk,
    evaluate_tool_call_policy,
)
from .world_schema import RevisionDelta

logger = logging.getLogger(__name__)

TOOL_GATEWAY_SCHEMA_VERSION = "cee.tool_gateway.v1"

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolGatewayResult:
    """Complete result of a tool execution through the gateway."""

    call: ToolCallSpec
    policy_decision: ToolPolicyDecision
    commitment_event: CommitmentEvent | None
    tool_result: ToolResultEvent | None
    observation: ObservationCandidate | None
    promotion_delta: RevisionDelta | None
    revision_event: ModelRevisionEvent | None
    approved: bool = True

    @property
    def succeeded(self) -> bool:
        return (
            self.tool_result is not None
            and self.tool_result.status == "succeeded"
        )

    @property
    def blocked_by_policy(self) -> bool:
        return self.policy_decision.blocked

    @property
    def blocked_by_approval(self) -> bool:
        return not self.approved and self.policy_decision.verdict == "requires_approval"


class ApprovalProvider(Protocol):
    """Protocol for approval decisions on tool calls."""

    def check_approval(
        self,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
    ) -> bool:
        """Return True if the tool call is approved, False otherwise."""
        ...


@dataclass
class StaticApprovalProvider:
    """Always approves or always denies."""

    verdict: bool = True

    def check_approval(
        self,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
    ) -> bool:
        return self.verdict


@dataclass
class ToolGateway:
    """Bounded execution gateway for all tool contacts.

    Every tool call must pass through this gateway. The gateway:
    - Checks tool policy before execution
    - Routes to approval gate for write/external_side_effect tools
    - Executes via registered handlers
    - Records complete audit trail in EventLog
    - Optionally promotes observation results to RevisionDelta
    """

    registry: ToolRegistry
    handlers: dict[str, ToolHandler] = field(default_factory=dict)
    approval_provider: ApprovalProvider | None = None
    timeout_ms: float = 30000.0

    def register_handler(self, tool_name: str, handler: ToolHandler) -> None:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Cannot register handler for unknown tool: {tool_name}")
        if tool_name in self.handlers:
            raise ValueError(f"Handler already registered for tool: {tool_name}")
        self.handlers[tool_name] = handler

    def execute(
        self,
        call: ToolCallSpec,
        *,
        event_log: EventLog,
        promote_to_belief_key: str | None = None,
        current_state_id: str = "ws_0",
    ) -> ToolGatewayResult:
        """Execute a tool call through the full gateway pipeline.

        Pipeline:
        1. Policy check
        2. Approval gate (if required)
        3. Handler execution
        4. Audit trail recording
        5. Observation promotion (if requested)
        """

        policy_decision = evaluate_tool_call_policy(call, self.registry)

        if policy_decision.verdict == "deny":
            return self._record_denied(call, policy_decision, event_log)

        if policy_decision.verdict == "requires_approval":
            approved = self._check_approval(call, policy_decision)
            if not approved:
                return self._record_approval_denied(
                    call, policy_decision, event_log
                )

        commitment = CommitmentEvent(
            event_id=f"ce_{call.call_id}",
            source_state_id=current_state_id,
            commitment_kind="tool_contact",
            intent_summary=f"Execute tool: {call.tool_name}",
            action_summary=call.tool_name,
        )
        event_log.append(commitment)

        tool_result = self._execute_handler(call)
        event_log.append(tool_result)

        observation = None
        promotion_delta = None
        revision_event = None

        if tool_result.status == "succeeded":
            observation = observation_from_tool_result(tool_result)
            event_log.append(build_observation_event(observation))

            completed_commitment = complete_commitment(
                commitment,
                success=True,
                external_result_summary=f"Tool {call.tool_name} succeeded",
                observation_summaries=(f"result from {call.tool_name}",),
            )

            if promote_to_belief_key is not None:
                promotion_delta = promote_observation_to_delta(
                    observation,
                    belief_key=promote_to_belief_key,
                )
                delta_decision = evaluate_delta_policy(promotion_delta)

                if delta_decision.allowed and not delta_decision.requires_approval:
                    revision_count = sum(
                        1 for e in event_log.all()
                        if isinstance(e, ModelRevisionEvent)
                    )
                    resulting_state_id = f"ws_{revision_count + 1}"
                    revision_event = ModelRevisionEvent(
                        revision_id=f"rev_{call.call_id}",
                        prior_state_id=current_state_id,
                        caused_by_event_id=commitment.event_id,
                        revision_kind="expansion",
                        deltas=(promotion_delta,),
                        resulting_state_id=resulting_state_id,
                        revision_summary=f"Promote observation from {call.tool_name}",
                    )
                    event_log.append(revision_event)
        else:
            completed_commitment = complete_commitment(
                commitment,
                success=False,
                external_result_summary=tool_result.error_message,
            )

        return ToolGatewayResult(
            call=call,
            policy_decision=policy_decision,
            commitment_event=commitment,
            tool_result=tool_result,
            observation=observation,
            promotion_delta=promotion_delta,
            revision_event=revision_event,
        )

    def execute_batch(
        self,
        calls: tuple[ToolCallSpec, ...],
        *,
        event_log: EventLog,
        promote_to_belief_keys: dict[str, str] | None = None,
        current_state_id: str = "ws_0",
    ) -> tuple[ToolGatewayResult, ...]:
        """Execute multiple tool calls through the gateway."""
        promotion_map = dict(promote_to_belief_keys or {})
        results = []
        state_id = current_state_id

        for call in calls:
            result = self.execute(
                call,
                event_log=event_log,
                promote_to_belief_key=promotion_map.get(call.call_id),
                current_state_id=state_id,
            )
            results.append(result)
            if result.revision_event is not None:
                state_id = result.revision_event.resulting_state_id

        return tuple(results)

    def _check_approval(
        self,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
    ) -> bool:
        if self.approval_provider is None:
            return False
        return self.approval_provider.check_approval(call, policy_decision)

    def _execute_handler(self, call: ToolCallSpec) -> ToolResultEvent:
        handler = self.handlers.get(call.tool_name)
        if handler is None:
            return ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=f"no handler registered for tool: {call.tool_name}",
            )

        try:
            result = handler(call.arguments)
        except Exception as exc:
            logger.error(
                "tool_gateway.handler.error call_id=%s tool=%s error=%s",
                call.call_id,
                call.tool_name,
                exc,
            )
            return ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=str(exc),
            )

        return ToolResultEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status="succeeded",
            result=result,
        )

    def _record_denied(
        self,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
        event_log: EventLog,
    ) -> ToolGatewayResult:
        tool_result = ToolResultEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status="failed",
            error_message=f"tool policy denied: {policy_decision.reason}",
        )
        event_log.append(tool_result)

        return ToolGatewayResult(
            call=call,
            policy_decision=policy_decision,
            commitment_event=None,
            tool_result=tool_result,
            observation=None,
            promotion_delta=None,
            revision_event=None,
        )

    def _record_approval_denied(
        self,
        call: ToolCallSpec,
        policy_decision: ToolPolicyDecision,
        event_log: EventLog,
    ) -> ToolGatewayResult:
        tool_result = ToolResultEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status="failed",
            error_message=f"tool requires approval but was not approved: {policy_decision.reason}",
        )
        event_log.append(tool_result)

        return ToolGatewayResult(
            call=call,
            policy_decision=policy_decision,
            commitment_event=None,
            tool_result=tool_result,
            observation=None,
            promotion_delta=None,
            revision_event=None,
            approved=False,
        )


def build_tool_gateway(
    registry: ToolRegistry,
    *,
    handlers: dict[str, ToolHandler] | None = None,
    approval_provider: ApprovalProvider | None = None,
) -> ToolGateway:
    """Build a ToolGateway with optional handlers and approval provider."""
    gateway = ToolGateway(
        registry=registry,
        approval_provider=approval_provider,
    )
    if handlers:
        for tool_name, handler in handlers.items():
            gateway.register_handler(tool_name, handler)
    return gateway
