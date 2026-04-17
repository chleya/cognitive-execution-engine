"""Domain policy overlay contracts."""

from __future__ import annotations

from .confidence_gate import ConfidenceGateConfig, evaluate_confidence_gate
from .domain_context import DomainContext
from .policy import PolicyDecision, evaluate_patch_policy
from .state import State, StatePatch


def evaluate_patch_policy_in_domain(
    patch: StatePatch,
    domain_context: DomainContext,
    *,
    current_state: State | None = None,
    confidence_gate_config: ConfidenceGateConfig | None = None,
) -> PolicyDecision:
    """Evaluate patch policy with domain and confidence overlays.

    Domain overlays may only tighten core policy. They may not loosen it.
    Confidence gate may escalate allow -> requires_approval when belief
    confidence is below threshold.
    """

    base = evaluate_patch_policy(patch)
    decision = _apply_domain_overlay(patch, base, domain_context)

    if current_state is not None and decision.verdict == "allow":
        decision = evaluate_confidence_gate(
            patch,
            decision,
            current_state.beliefs,
            config=confidence_gate_config,
            current_memory=current_state.memory,
        )

    return decision


def _apply_domain_overlay(
    patch: StatePatch,
    base: PolicyDecision,
    domain_context: DomainContext,
) -> PolicyDecision:
    pack = domain_context.plugin_pack
    if pack is None:
        return base

    if patch.section in pack.denied_patch_sections:
        return PolicyDecision(
            verdict="deny",
            reason=(
                f"domain policy denies patch section '{patch.section}' "
                f"in domain '{domain_context.domain_name}'"
            ),
            policy_ref=f"domain-overlay:{domain_context.domain_name}:deny",
        )

    if patch.section in pack.approval_required_patch_sections:
        if base.verdict == "deny":
            return base
        return PolicyDecision(
            verdict="requires_approval",
            reason=(
                f"domain policy requires approval for patch section "
                f"'{patch.section}' in domain '{domain_context.domain_name}'"
            ),
            policy_ref=f"domain-overlay:{domain_context.domain_name}:approval",
        )

    return base
