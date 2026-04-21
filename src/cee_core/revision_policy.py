"""RevisionPolicy: policy evaluation for model revision deltas.

Ensures that every revision delta carries justification, prohibits
re-anchoring already-anchored facts, and only allows recognized
revision kinds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Tuple

from .revision import RevisionKind
from .schemas import require_schema_version
from .world_schema import RevisionDelta, RevisionTargetKind
from .world_state import WorldState

REVISION_POLICY_SCHEMA_VERSION = "cee.revision_policy.v1"

ALLOWED_REVISION_KINDS: frozenset[RevisionKind] = frozenset({
    "confirmation",
    "correction",
    "expansion",
    "compression",
    "recalibration",
})


@dataclass(frozen=True)
class RevisionPolicyDecision:
    allowed: bool
    reason: str
    violated_rules: Tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REVISION_POLICY_SCHEMA_VERSION,
            "allowed": self.allowed,
            "reason": self.reason,
            "violated_rules": list(self.violated_rules),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RevisionPolicyDecision:
        require_schema_version(payload, REVISION_POLICY_SCHEMA_VERSION)
        return cls(
            allowed=payload["allowed"],
            reason=payload["reason"],
            violated_rules=tuple(payload.get("violated_rules", ())),
        )


class RevisionPolicy(Protocol):
    def evaluate(
        self,
        deltas: Tuple[RevisionDelta, ...],
        state: WorldState,
        revision_kind: RevisionKind,
    ) -> RevisionPolicyDecision: ...


class DefaultRevisionPolicy:
    def evaluate(
        self,
        deltas: Tuple[RevisionDelta, ...],
        state: WorldState,
        revision_kind: RevisionKind,
    ) -> RevisionPolicyDecision:
        violated: list[str] = []

        if revision_kind not in ALLOWED_REVISION_KINDS:
            violated.append(f"revision_kind_not_allowed:{revision_kind}")

        for delta in deltas:
            if not delta.justification.strip():
                violated.append(f"empty_justification:{delta.delta_id}")

            if delta.target_kind == "anchor_add":
                if state.is_fact_anchored(delta.after_summary):
                    violated.append(f"anchor_already_exists:{delta.delta_id}")

        if violated:
            return RevisionPolicyDecision(
                allowed=False,
                reason="revision policy violated",
                violated_rules=tuple(violated),
            )

        return RevisionPolicyDecision(
            allowed=True,
            reason="revision policy satisfied",
            violated_rules=(),
        )


def evaluate_revision_policy(
    deltas: Tuple[RevisionDelta, ...],
    state: WorldState,
    revision_kind: RevisionKind,
    *,
    policy: RevisionPolicy | None = None,
) -> RevisionPolicyDecision:
    effective = policy if policy is not None else DefaultRevisionPolicy()
    return effective.evaluate(deltas, state, revision_kind)
