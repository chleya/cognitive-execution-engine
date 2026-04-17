"""Typed event primitives for the Cognitive Execution Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .deliberation import ReasoningStep
from .policy import PolicyDecision
from .schemas import (
    DELIBERATION_EVENT_SCHEMA_VERSION,
    STATE_TRANSITION_EVENT_SCHEMA_VERSION,
    require_schema_version,
)
from .state import StatePatch


@dataclass(frozen=True)
class Event:
    """Append-only event used to explain a state transition."""

    event_type: str
    payload: dict[str, Any]
    trace_id: str = field(default_factory=lambda: f"tr_{uuid4().hex}")
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    actor: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "actor": self.actor,
        }


@dataclass(frozen=True)
class StateTransitionEvent:
    """Auditable event that can be replayed into a state transition."""

    patch: StatePatch
    policy_decision: PolicyDecision
    trace_id: str = field(default_factory=lambda: f"tr_{uuid4().hex}")
    actor: str = "system"
    reason: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def event_type(self) -> str:
        return "state.patch.requested"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_TRANSITION_EVENT_SCHEMA_VERSION,
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "created_at": self.created_at,
            "reason": self.reason,
            "policy_decision": self.policy_decision.to_dict(),
            "patch": self.patch.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StateTransitionEvent":
        require_schema_version(payload, STATE_TRANSITION_EVENT_SCHEMA_VERSION)
        if payload.get("event_type") != "state.patch.requested":
            raise ValueError("Not a state transition event payload")

        return cls(
            patch=StatePatch.from_dict(payload["patch"]),
            policy_decision=PolicyDecision.from_dict(payload["policy_decision"]),
            trace_id=payload["trace_id"],
            actor=payload.get("actor", "system"),
            reason=payload.get("reason", ""),
            created_at=payload["created_at"],
        )


@dataclass(frozen=True)
class DeliberationEvent:
    """Audit event for a bounded reasoning step."""

    reasoning_step: ReasoningStep
    trace_id: str = field(default_factory=lambda: f"tr_{uuid4().hex}")
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    actor: str = "deliberation_engine"

    @property
    def event_type(self) -> str:
        return "reasoning.step.selected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DELIBERATION_EVENT_SCHEMA_VERSION,
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "actor": self.actor,
            "reasoning_step": self.reasoning_step.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeliberationEvent":
        require_schema_version(payload, DELIBERATION_EVENT_SCHEMA_VERSION)
        if payload.get("event_type") != "reasoning.step.selected":
            raise ValueError("Not a deliberation event payload")
        return cls(
            reasoning_step=ReasoningStep.from_dict(payload["reasoning_step"]),
            trace_id=payload["trace_id"],
            created_at=payload["created_at"],
            actor=payload.get("actor", "deliberation_engine"),
        )
