"""Policy decision primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schemas import POLICY_DECISION_SCHEMA_VERSION, require_schema_version
from .state import StatePatch


PolicyVerdict = Literal["allow", "deny", "requires_approval"]


@dataclass(frozen=True)
class PolicyDecision:
    """Result of policy evaluation for a proposed action or state patch."""

    verdict: PolicyVerdict
    reason: str
    policy_ref: str

    @property
    def allowed(self) -> bool:
        return self.verdict == "allow"

    @property
    def blocked(self) -> bool:
        return self.verdict in {"deny", "requires_approval"}

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": POLICY_DECISION_SCHEMA_VERSION,
            "verdict": self.verdict,
            "reason": self.reason,
            "policy_ref": self.policy_ref,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "PolicyDecision":
        require_schema_version(payload, POLICY_DECISION_SCHEMA_VERSION)
        return cls(
            verdict=payload["verdict"],
            reason=payload["reason"],
            policy_ref=payload["policy_ref"],
        )


def evaluate_patch_policy(patch: StatePatch) -> PolicyDecision:
    """Evaluate the minimal Stage 0 policy for a state patch."""

    if patch.section == "policy":
        return PolicyDecision(
            verdict="deny",
            reason="policy mutations require release governance",
            policy_ref="stage0.patch-policy:v1",
        )

    if patch.section == "self_model":
        return PolicyDecision(
            verdict="requires_approval",
            reason="self_model mutation changes system self-description",
            policy_ref="stage0.patch-policy:v1",
        )

    if patch.section == "meta":
        return PolicyDecision(
            verdict="deny",
            reason="meta is reducer-managed; version is auto-incremented",
            policy_ref="stage0.patch-policy:v1",
        )

    if patch.section == "tool_affordances":
        return PolicyDecision(
            verdict="requires_approval",
            reason="tool_affordances mutation changes system capability boundary",
            policy_ref="stage0.patch-policy:v1",
        )

    if patch.section in {"memory", "goals", "beliefs", "domain_data"}:
        return PolicyDecision(
            verdict="allow",
            reason=f"{patch.section} patch allowed by Stage 0 policy",
            policy_ref="stage0.patch-policy:v1",
        )

    return PolicyDecision(
        verdict="deny",
        reason=f"unknown state section: {patch.section}",
        policy_ref="stage0.patch-policy:v1",
    )


def build_transition_for_patch(
    patch: StatePatch,
    *,
    actor: str = "system",
    reason: str = "",
) -> "StateTransitionEvent":
    """Create a transition event with policy evaluated at construction time."""

    from .events import StateTransitionEvent

    return StateTransitionEvent(
        patch=patch,
        policy_decision=evaluate_patch_policy(patch),
        actor=actor,
        reason=reason,
    )
