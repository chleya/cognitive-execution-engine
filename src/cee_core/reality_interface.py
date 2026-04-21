"""RealityInterface: bounded contact boundary between CEE and external reality.

The reality interface mediates all contact between the cognitive execution
engine and the external world. No state transition may claim external
knowledge without passing through this boundary.

Key invariant: the reality interface only proposes observations and records
results. It does not own execution authority. All state transitions must
still go through the policy engine and audit trail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Protocol, Tuple, TYPE_CHECKING

from .commitment import (
    CommitmentEvent,
    CommitmentKind,
    complete_commitment,
)
from .event_log import EventLog
from .events import Event
from .schemas import require_schema_version
from .tools import ToolCallSpec, ToolRegistry

if TYPE_CHECKING:
    from .tool_gateway import ToolGateway

logger = logging.getLogger(__name__)

REALITY_INTERFACE_SCHEMA_VERSION = "cee.reality_interface.v1"

RealityFn = Callable[[CommitmentEvent], str]


@dataclass(frozen=True)
class RealityContactResult:
    """Structured result from a single reality contact."""

    commitment_event_id: str
    commitment_kind: CommitmentKind
    success: bool
    result_summary: str
    observation_summaries: Tuple[str, ...] = ()
    risk_realized: float = 0.0
    cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REALITY_INTERFACE_SCHEMA_VERSION,
            "commitment_event_id": self.commitment_event_id,
            "commitment_kind": self.commitment_kind,
            "success": self.success,
            "result_summary": self.result_summary,
            "observation_summaries": list(self.observation_summaries),
            "risk_realized": self.risk_realized,
            "cost": self.cost,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RealityContactResult:
        require_schema_version(payload, REALITY_INTERFACE_SCHEMA_VERSION)
        return cls(
            commitment_event_id=payload["commitment_event_id"],
            commitment_kind=payload["commitment_kind"],
            success=payload["success"],
            result_summary=payload["result_summary"],
            observation_summaries=tuple(payload.get("observation_summaries", ())),
            risk_realized=payload.get("risk_realized", 0.0),
            cost=payload.get("cost", 0.0),
        )


class RealityInterface(Protocol):
    """Protocol for the reality contact boundary.

    Every method takes a pending CommitmentEvent and a reality_fn callable
    that simulates or performs the actual external contact. The interface
    is responsible for orchestration, logging, and error handling, not for
    owning execution authority.
    """

    def observe(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        """Execute an observation commitment through the reality boundary."""
        ...

    def act(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        """Execute an action commitment through the reality boundary."""
        ...

    def tool_contact(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        """Execute a tool contact commitment through the reality boundary."""
        ...


@dataclass(frozen=True)
class DefaultRealityInterface:
    """Default implementation connecting ToolRegistry and CommitmentEvent.

    Wraps reality contact with logging and error handling. For tool_contact
    commitments, validates the tool exists in the registry before proceeding.
    """

    registry: ToolRegistry = field(default_factory=ToolRegistry)

    def observe(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        if commitment.commitment_kind != "observe":
            raise ValueError(
                f"observe called with commitment_kind={commitment.commitment_kind!r}; expected 'observe'"
            )
        logger.info(
            "reality.observe.start event_id=%s intent=%s",
            commitment.event_id,
            commitment.intent_summary,
        )
        try:
            result_summary = reality_fn(commitment)
            completed = complete_commitment(
                commitment,
                success=True,
                external_result_summary=result_summary,
                observation_summaries=(result_summary,),
            )
            logger.info(
                "reality.observe.complete event_id=%s success=True",
                commitment.event_id,
            )
            return completed
        except Exception as exc:
            logger.error(
                "reality.observe.error event_id=%s error=%s",
                commitment.event_id,
                exc,
            )
            return complete_commitment(
                commitment,
                success=False,
                external_result_summary=f"observation failed: {exc}",
                risk_realized=commitment.risk_realized,
            )

    def act(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        if commitment.commitment_kind != "act":
            raise ValueError(
                f"act called with commitment_kind={commitment.commitment_kind!r}; expected 'act'"
            )
        logger.info(
            "reality.act.start event_id=%s intent=%s",
            commitment.event_id,
            commitment.intent_summary,
        )
        try:
            result_summary = reality_fn(commitment)
            completed = complete_commitment(
                commitment,
                success=True,
                external_result_summary=result_summary,
            )
            logger.info(
                "reality.act.complete event_id=%s success=True",
                commitment.event_id,
            )
            return completed
        except Exception as exc:
            logger.error(
                "reality.act.error event_id=%s error=%s",
                commitment.event_id,
                exc,
            )
            return complete_commitment(
                commitment,
                success=False,
                external_result_summary=f"action failed: {exc}",
                risk_realized=commitment.risk_realized,
            )

    def tool_contact(
        self,
        commitment: CommitmentEvent,
        reality_fn: RealityFn,
    ) -> CommitmentEvent:
        if commitment.commitment_kind != "tool_contact":
            raise ValueError(
                f"tool_contact called with commitment_kind={commitment.commitment_kind!r}; expected 'tool_contact'"
            )
        tool_name = commitment.action_summary
        if tool_name:
            tool_spec = self.registry.get(tool_name)
            if tool_spec is None:
                logger.warning(
                    "reality.tool_contact.unknown_tool event_id=%s tool=%s",
                    commitment.event_id,
                    tool_name,
                )
                return complete_commitment(
                    commitment,
                    success=False,
                    external_result_summary=f"unknown tool: {tool_name}",
                    risk_realized=commitment.risk_realized,
                )
        logger.info(
            "reality.tool_contact.start event_id=%s intent=%s",
            commitment.event_id,
            commitment.intent_summary,
        )
        try:
            result_summary = reality_fn(commitment)
            completed = complete_commitment(
                commitment,
                success=True,
                external_result_summary=result_summary,
                observation_summaries=(result_summary,),
            )
            logger.info(
                "reality.tool_contact.complete event_id=%s success=True",
                commitment.event_id,
            )
            return completed
        except Exception as exc:
            logger.error(
                "reality.tool_contact.error event_id=%s error=%s",
                commitment.event_id,
                exc,
            )
            return complete_commitment(
                commitment,
                success=False,
                external_result_summary=f"tool contact failed: {exc}",
                risk_realized=commitment.risk_realized,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REALITY_INTERFACE_SCHEMA_VERSION,
            "registered_tools": [
                {"name": t.name, "risk": t.risk} for t in self.registry.list()
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> DefaultRealityInterface:
        require_schema_version(payload, REALITY_INTERFACE_SCHEMA_VERSION)
        registry = ToolRegistry()
        for tool_entry in payload.get("registered_tools", []):
            from .tools import ToolSpec

            spec = ToolSpec(
                name=tool_entry["name"],
                description=tool_entry.get("description", ""),
                risk=tool_entry.get("risk", "read"),
            )
            registry.register(spec)
        return cls(registry=registry)


_KIND_DISPATCH: dict[CommitmentKind, str] = {
    "observe": "observe",
    "act": "act",
    "tool_contact": "tool_contact",
}


def execute_commitment(
    commitment: CommitmentEvent,
    reality_fn: RealityFn,
    interface: RealityInterface | None = None,
) -> CommitmentEvent:
    """Execute a commitment through the reality interface.

    Dispatches to the correct method on the interface based on
    commitment_kind. If no interface is provided, a DefaultRealityInterface
    is constructed.

    Raises ValueError for unsupported commitment kinds.
    """
    if commitment.commitment_kind not in _KIND_DISPATCH:
        raise ValueError(
            f"unsupported commitment_kind: {commitment.commitment_kind!r}; "
            f"expected one of {list(_KIND_DISPATCH.keys())}"
        )

    if interface is None:
        interface = DefaultRealityInterface()

    method_name = _KIND_DISPATCH[commitment.commitment_kind]
    method = getattr(interface, method_name)
    return method(commitment, reality_fn)


@dataclass(frozen=True)
class GatewayContactResult:
    """Result of executing a tool_contact commitment through the ToolGateway.

    This bridges the reality interface (commitment-level) with the tool
    gateway (policy + approval + audit level). The gateway provides the
    full safety pipeline, while the reality interface provides the
    commitment semantics.
    """

    commitment_event: CommitmentEvent
    gateway_succeeded: bool
    policy_verdict: str
    tool_result_summary: str = ""
    observation_summary: str = ""
    approval_verdict: str = ""

    @property
    def success(self) -> bool:
        return self.gateway_succeeded


def execute_commitment_via_gateway(
    commitment: CommitmentEvent,
    gateway: ToolGateway,
    event_log: EventLog,
    *,
    tool_arguments: dict[str, Any] | None = None,
    promote_to_belief_key: str | None = None,
    current_state_id: str = "ws_0",
) -> GatewayContactResult:
    """Execute a tool_contact commitment through the ToolGateway pipeline.

    This is the primary integration point between the reality interface
    (commitment-level semantics) and the tool gateway (policy + approval
    + audit pipeline).

    Key invariant: the gateway enforces policy, approval, and audit.
    The reality interface only provides commitment semantics. Neither
    owns execution authority independently.

    Pipeline:
    1. Validate commitment_kind is tool_contact
    2. Extract tool_name from commitment action_summary
    3. Build ToolCallSpec from commitment
    4. Execute through gateway (policy → approval → execution → audit)
    5. Record result in event log
    6. Return GatewayContactResult

    Raises ValueError if commitment_kind is not tool_contact.
    """
    if commitment.commitment_kind != "tool_contact":
        raise ValueError(
            f"execute_commitment_via_gateway requires commitment_kind='tool_contact'; "
            f"got {commitment.commitment_kind!r}"
        )

    tool_name = commitment.action_summary
    if not tool_name:
        return GatewayContactResult(
            commitment_event=complete_commitment(
                commitment,
                success=False,
                external_result_summary="no tool name in commitment action_summary",
            ),
            gateway_succeeded=False,
            policy_verdict="deny",
        )

    call = ToolCallSpec(
        tool_name=tool_name,
        arguments=tool_arguments or {},
    )

    gateway_result = gateway.execute(
        call,
        event_log=event_log,
        promote_to_belief_key=promote_to_belief_key,
        current_state_id=current_state_id,
    )

    event_log.append(Event(
        event_type="reality.gateway_contact.completed",
        payload={
            "commitment_event_id": commitment.event_id,
            "tool_name": tool_name,
            "gateway_succeeded": gateway_result.succeeded,
            "policy_verdict": gateway_result.policy_decision.verdict,
        },
        actor="reality_interface",
    ))

    observation_summary = ""
    if gateway_result.observation is not None:
        observation_summary = str(gateway_result.observation.content)[:200]

    approval_verdict = ""
    if gateway_result.approval_decision is not None:
        approval_verdict = gateway_result.approval_decision.verdict

    tool_result_summary = ""
    if gateway_result.tool_result is not None:
        tool_result_summary = str(gateway_result.tool_result.result)[:200]

    completed = complete_commitment(
        commitment,
        success=gateway_result.succeeded,
        external_result_summary=tool_result_summary or observation_summary,
        observation_summaries=(observation_summary,) if observation_summary else (),
    )

    return GatewayContactResult(
        commitment_event=completed,
        gateway_succeeded=gateway_result.succeeded,
        policy_verdict=gateway_result.policy_decision.verdict,
        tool_result_summary=tool_result_summary,
        observation_summary=observation_summary,
        approval_verdict=approval_verdict,
    )
