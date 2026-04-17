"""Confidence-aware policy overlay.

This module connects belief and memory confidence to policy decisions.
When a patch targets the beliefs or memory section, the confidence of
the underlying data determines whether the patch should be auto-approved
or escalated to human review.

For beliefs: checks the existing belief value's confidence/evidence_count.
For memory: checks the patch value's confidence/evidence_count. Memory
patches without evidence metadata are escalated to requires_approval,
enforcing the "no direct model-written memory" boundary.

This is a policy overlay, not a base policy change. It may only tighten
decisions (allow -> requires_approval), never loosen them (deny -> allow).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .policy import PolicyDecision
from .state import StatePatch


DEFAULT_CONFIDENCE_APPROVAL_THRESHOLD = 0.7
DEFAULT_EVIDENCE_COUNT_THRESHOLD = 2

_GATED_SECTIONS = {"beliefs", "memory"}


@dataclass(frozen=True)
class ConfidenceGateConfig:
    """Configuration for confidence-based policy escalation."""

    approval_threshold: float = DEFAULT_CONFIDENCE_APPROVAL_THRESHOLD
    evidence_count_threshold: int = DEFAULT_EVIDENCE_COUNT_THRESHOLD
    enabled: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.approval_threshold <= 1.0:
            raise ValueError("approval_threshold must be between 0.0 and 1.0")
        if self.evidence_count_threshold < 1:
            raise ValueError("evidence_count_threshold must be at least 1")


def evaluate_confidence_gate(
    patch: StatePatch,
    base_decision: PolicyDecision,
    current_beliefs: dict[str, object],
    config: ConfidenceGateConfig | None = None,
    *,
    current_memory: dict[str, object] | None = None,
) -> PolicyDecision:
    """Apply confidence-based escalation to a policy decision.

    For beliefs: checks the existing belief value's confidence/evidence.
    For memory: checks the patch value's confidence/evidence. Memory
    patches without evidence metadata are escalated to requires_approval.

    This never loosens a decision. If base is deny, it stays deny.
    """

    if config is None:
        config = ConfidenceGateConfig()

    if not config.enabled:
        return base_decision

    if base_decision.verdict != "allow":
        return base_decision

    if patch.section not in _GATED_SECTIONS:
        return base_decision

    if patch.section == "beliefs":
        return _evaluate_beliefs_gate(patch, base_decision, current_beliefs, config)

    if patch.section == "memory":
        return _evaluate_memory_gate(patch, base_decision, config)

    return base_decision


def _evaluate_beliefs_gate(
    patch: StatePatch,
    base_decision: PolicyDecision,
    current_beliefs: dict[str, object],
    config: ConfidenceGateConfig,
) -> PolicyDecision:
    belief_value = current_beliefs.get(patch.key)
    if not isinstance(belief_value, dict):
        return base_decision

    confidence = belief_value.get("confidence")
    if not isinstance(confidence, (int, float)):
        return base_decision

    if float(confidence) < config.approval_threshold:
        return PolicyDecision(
            verdict="requires_approval",
            reason=(
                f"belief confidence {float(confidence):.2f} is below "
                f"approval threshold {config.approval_threshold:.2f}"
            ),
            policy_ref="confidence-gate:low-confidence-escalation",
        )

    evidence_count = belief_value.get("evidence_count")
    if isinstance(evidence_count, (int, float)):
        if int(evidence_count) < config.evidence_count_threshold:
            return PolicyDecision(
                verdict="requires_approval",
                reason=(
                    f"belief evidence count {int(evidence_count)} is below "
                    f"evidence threshold {config.evidence_count_threshold}"
                ),
                policy_ref="confidence-gate:insufficient-evidence-escalation",
            )

    return base_decision


def _evaluate_memory_gate(
    patch: StatePatch,
    base_decision: PolicyDecision,
    config: ConfidenceGateConfig,
) -> PolicyDecision:
    patch_value = patch.value
    if not isinstance(patch_value, dict):
        return PolicyDecision(
            verdict="requires_approval",
            reason=(
                "memory patch without evidence metadata requires approval "
                "(direct model-written memory boundary)"
            ),
            policy_ref="confidence-gate:memory-no-evidence-escalation",
        )

    confidence = patch_value.get("confidence")
    if not isinstance(confidence, (int, float)):
        return PolicyDecision(
            verdict="requires_approval",
            reason=(
                "memory patch without confidence metadata requires approval "
                "(direct model-written memory boundary)"
            ),
            policy_ref="confidence-gate:memory-no-evidence-escalation",
        )

    if float(confidence) < config.approval_threshold:
        return PolicyDecision(
            verdict="requires_approval",
            reason=(
                f"memory confidence {float(confidence):.2f} is below "
                f"approval threshold {config.approval_threshold:.2f}"
            ),
            policy_ref="confidence-gate:memory-low-confidence-escalation",
        )

    evidence_count = patch_value.get("evidence_count")
    if isinstance(evidence_count, (int, float)):
        if int(evidence_count) < config.evidence_count_threshold:
            return PolicyDecision(
                verdict="requires_approval",
                reason=(
                    f"memory evidence count {int(evidence_count)} is below "
                    f"evidence threshold {config.evidence_count_threshold}"
                ),
                policy_ref="confidence-gate:memory-insufficient-evidence-escalation",
            )

    return base_decision


def extract_belief_confidence(belief_value: object) -> float | None:
    """Extract confidence from a belief payload, if present."""

    if not isinstance(belief_value, dict):
        return None

    confidence = belief_value.get("confidence")
    if isinstance(confidence, (int, float)):
        return float(confidence)

    return None
