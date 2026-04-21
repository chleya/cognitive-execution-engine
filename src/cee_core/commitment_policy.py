"""Commitment policy: governs which commitment kinds are allowed and which require approval.

The commitment policy evaluates proposed commitments based on their kind and
reversibility, producing a bounded decision that is auditable and replayable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .commitment import CommitmentKind, Reversibility
from .schemas import COMMITMENT_POLICY_SCHEMA_VERSION, require_schema_version


@dataclass(frozen=True)
class CommitmentPolicyDecision:
    """Result of evaluating a commitment against policy."""

    allowed: bool
    reason: str
    requires_approval: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMMITMENT_POLICY_SCHEMA_VERSION,
            "allowed": self.allowed,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CommitmentPolicyDecision:
        require_schema_version(payload, COMMITMENT_POLICY_SCHEMA_VERSION)
        return cls(
            allowed=payload["allowed"],
            reason=payload["reason"],
            requires_approval=payload["requires_approval"],
        )


class CommitmentPolicy(Protocol):
    """Protocol for commitment policy evaluation."""

    def evaluate(
        self,
        commitment_kind: CommitmentKind,
        reversibility: Reversibility | None = None,
    ) -> CommitmentPolicyDecision: ...


@dataclass(frozen=True)
class DefaultCommitmentPolicy:
    """Default commitment policy following the CEE safety rules.

    - observe: default allow
    - act with reversible: allow
    - act with partially_reversible: allow with warning
    - act with irreversible: require human approval
    - tool_contact: default allow
    - internal_commit: default allow
    """

    policy_ref: str = "commitment.default.v1"

    def evaluate(
        self,
        commitment_kind: CommitmentKind,
        reversibility: Reversibility | None = None,
    ) -> CommitmentPolicyDecision:
        if commitment_kind == "observe":
            return CommitmentPolicyDecision(
                allowed=True,
                reason="observe commitment allowed by default policy",
                requires_approval=False,
            )

        if commitment_kind == "act":
            if reversibility is None:
                return CommitmentPolicyDecision(
                    allowed=False,
                    reason="act commitment requires explicit reversibility",
                    requires_approval=True,
                )
            if reversibility == "reversible":
                return CommitmentPolicyDecision(
                    allowed=True,
                    reason="reversible act allowed by default policy",
                    requires_approval=False,
                )
            if reversibility == "partially_reversible":
                return CommitmentPolicyDecision(
                    allowed=True,
                    reason="partially_reversible act allowed with warning by default policy",
                    requires_approval=False,
                )
            if reversibility == "irreversible":
                return CommitmentPolicyDecision(
                    allowed=False,
                    reason="irreversible act requires human approval",
                    requires_approval=True,
                )

        if commitment_kind == "tool_contact":
            return CommitmentPolicyDecision(
                allowed=True,
                reason="tool_contact commitment allowed by default policy",
                requires_approval=False,
            )

        if commitment_kind == "internal_commit":
            return CommitmentPolicyDecision(
                allowed=True,
                reason="internal_commit allowed by default policy",
                requires_approval=False,
            )

        return CommitmentPolicyDecision(
            allowed=False,
            reason=f"unknown commitment kind: {commitment_kind}",
            requires_approval=True,
        )


def evaluate_commitment_policy(
    commitment_kind: CommitmentKind,
    reversibility: Reversibility | None = None,
    policy: CommitmentPolicy | None = None,
) -> CommitmentPolicyDecision:
    """Evaluate a commitment against the given policy (or the default)."""
    effective = policy if policy is not None else DefaultCommitmentPolicy()
    return effective.evaluate(commitment_kind, reversibility)
