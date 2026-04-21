"""CommitmentEvent: reality commitment events for the CEE layer.

The CEE side owns: reality commitment events, reality contact result collection,
commitment recording, model revision after reality feedback, and anchored fact
updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Tuple

from .world_state import WorldState

COMMITMENT_SCHEMA_VERSION = "cee.commitment.v1"

CommitmentKind = Literal[
    "observe",
    "act",
    "tool_contact",
    "internal_commit",
]

Reversibility = Literal[
    "reversible",
    "partially_reversible",
    "irreversible",
]


@dataclass(frozen=True)
class CommitmentEvent:
    event_id: str
    source_state_id: str

    commitment_kind: CommitmentKind

    intent_summary: str
    expected_world_change: Tuple[str, ...] = ()
    expected_self_change: Tuple[str, ...] = ()

    affected_entity_ids: Tuple[str, ...] = ()
    affected_relation_ids: Tuple[str, ...] = ()

    action_summary: str = ""
    external_result_summary: str = ""

    observation_summaries: Tuple[str, ...] = ()

    success: bool = True
    reversibility: Reversibility = "reversible"
    requires_approval: bool = False

    cost: float = 0.0
    risk_realized: float = 0.0

    event_type: str = "commitment"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMMITMENT_SCHEMA_VERSION,
            "event_type": "commitment",
            "event_id": self.event_id,
            "source_state_id": self.source_state_id,
            "commitment_kind": self.commitment_kind,
            "intent_summary": self.intent_summary,
            "expected_world_change": list(self.expected_world_change),
            "expected_self_change": list(self.expected_self_change),
            "affected_entity_ids": list(self.affected_entity_ids),
            "affected_relation_ids": list(self.affected_relation_ids),
            "action_summary": self.action_summary,
            "external_result_summary": self.external_result_summary,
            "observation_summaries": list(self.observation_summaries),
            "success": self.success,
            "reversibility": self.reversibility,
            "requires_approval": self.requires_approval,
            "cost": self.cost,
            "risk_realized": self.risk_realized,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CommitmentEvent:
        return cls(
            event_id=payload["event_id"],
            source_state_id=payload["source_state_id"],
            commitment_kind=payload["commitment_kind"],
            intent_summary=payload["intent_summary"],
            expected_world_change=tuple(payload.get("expected_world_change", ())),
            expected_self_change=tuple(payload.get("expected_self_change", ())),
            affected_entity_ids=tuple(payload.get("affected_entity_ids", ())),
            affected_relation_ids=tuple(payload.get("affected_relation_ids", ())),
            action_summary=payload.get("action_summary", ""),
            external_result_summary=payload.get("external_result_summary", ""),
            observation_summaries=tuple(payload.get("observation_summaries", ())),
            success=payload.get("success", True),
            reversibility=payload.get("reversibility", "reversible"),
            requires_approval=payload.get("requires_approval", False),
            cost=payload.get("cost", 0.0),
            risk_realized=payload.get("risk_realized", 0.0),
        )


def make_observation_commitment(
    state: WorldState,
    *,
    event_id: str,
    intent_summary: str,
    target_entity_ids: Tuple[str, ...] = (),
) -> CommitmentEvent:
    return CommitmentEvent(
        event_id=event_id,
        source_state_id=state.state_id,
        commitment_kind="observe",
        intent_summary=intent_summary,
        affected_entity_ids=target_entity_ids,
        action_summary="request observation from reality interface",
    )


def make_act_commitment(
    state: WorldState,
    *,
    event_id: str,
    intent_summary: str,
    action_summary: str,
    target_entity_ids: Tuple[str, ...] = (),
    expected_world_change: Tuple[str, ...] = (),
    reversibility: Reversibility = "reversible",
) -> CommitmentEvent:
    return CommitmentEvent(
        event_id=event_id,
        source_state_id=state.state_id,
        commitment_kind="act",
        intent_summary=intent_summary,
        affected_entity_ids=target_entity_ids,
        action_summary=action_summary,
        expected_world_change=expected_world_change,
        reversibility=reversibility,
    )


def make_tool_contact_commitment(
    state: WorldState,
    *,
    event_id: str,
    intent_summary: str,
    action_summary: str,
    target_entity_ids: Tuple[str, ...] = (),
) -> CommitmentEvent:
    return CommitmentEvent(
        event_id=event_id,
        source_state_id=state.state_id,
        commitment_kind="tool_contact",
        intent_summary=intent_summary,
        affected_entity_ids=target_entity_ids,
        action_summary=action_summary,
    )


def complete_commitment(
    event: CommitmentEvent,
    *,
    success: bool,
    external_result_summary: str,
    observation_summaries: Tuple[str, ...] = (),
    risk_realized: float = 0.0,
) -> CommitmentEvent:
    from dataclasses import replace
    return replace(
        event,
        success=success,
        external_result_summary=external_result_summary,
        observation_summaries=observation_summaries,
        risk_realized=risk_realized,
    )
