"""LLM Proposal Adapters: bounded boundary between LLM output and state transitions.

The LLM Proposal Adapter enforces the core invariant from AGENTS.md:

    "LLMs only propose, summarize, extract, or narrate.
     They do not own execution authority."

Every LLM output must flow through this pipeline before any state change:

1. Validation: raw LLM output is parsed and validated against the world schema
2. Policy: each proposed RevisionDelta is evaluated against the policy engine
3. Approval: deltas requiring approval are routed to the approval gate
4. Audit: every decision is recorded in the EventLog
5. Execution: only policy-approved (and approval-gated) deltas produce events

The proposal pipeline is deterministic and replayable. Given the same LLM
output, policy, and approval provider, the result is always identical.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence
from uuid import uuid4

from .approval import ApprovalDecision, ApprovalProvider, ApprovalRequest
from .commitment import CommitmentEvent
from .event_log import EventLog
from .events import Event
from .planner import DeltaPolicyDecision, evaluate_delta_policy
from .revision import ModelRevisionEvent
from .tools import ToolCallSpec, ToolPolicyDecision, ToolRegistry, evaluate_tool_call_policy
from .world_schema import RevisionDelta, RevisionTargetKind

LLM_PROPOSAL_SCHEMA_VERSION = "cee.llm_proposal.v1"

FORBIDDEN_LLM_FIELDS: frozenset[str] = frozenset({
    "execute",
    "run",
    "apply",
    "commit",
    "force",
    "override",
    "bypass",
    "sudo",
    "admin",
    "escalate_permission",
    "expand_permission",
    "grant",
    "authorize",
    "direct_state_write",
    "raw_sql",
    "shell_command",
    "system_command",
})

VALID_TARGET_KINDS: frozenset[str] = frozenset({
    "entity_add",
    "entity_update",
    "entity_remove",
    "relation_add",
    "relation_update",
    "relation_remove",
    "hypothesis_add",
    "hypothesis_update",
    "hypothesis_remove",
    "goal_update",
    "tension_update",
    "anchor_add",
    "self_update",
})

VALID_PATCH_OPS: frozenset[str] = frozenset({
    "set",
    "append",
    "merge",
    "delete",
})


@dataclass(frozen=True)
class LLMProposal:
    """A typed, validated proposal from an LLM.

    LLM output is NEVER applied directly to state. It becomes a proposal
    that must pass through policy evaluation and approval before any
    state transition occurs.
    """

    proposal_id: str = field(default_factory=lambda: f"prop_{uuid4().hex}")
    source: str = "llm_adapter"
    objective: str = ""
    rationale: str = ""
    candidate_deltas: tuple[RevisionDelta, ...] = ()
    proposed_tool_calls: tuple[ToolCallSpec, ...] = ()
    raw_llm_output: str = ""
    validation_errors: tuple[str, ...] = ()
    is_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LLM_PROPOSAL_SCHEMA_VERSION,
            "proposal_id": self.proposal_id,
            "source": self.source,
            "objective": self.objective,
            "rationale": self.rationale,
            "candidate_deltas": [d.to_dict() for d in self.candidate_deltas],
            "proposed_tool_calls": [
                {
                    "call_id": c.call_id,
                    "tool_name": c.tool_name,
                    "arguments": c.arguments,
                }
                for c in self.proposed_tool_calls
            ],
            "is_valid": self.is_valid,
            "validation_errors": list(self.validation_errors),
        }


@dataclass(frozen=True)
class DeltaProposalDecision:
    """Policy + approval decision for a single proposed delta."""

    delta: RevisionDelta
    policy_decision: DeltaPolicyDecision
    approval_decision: ApprovalDecision | None = None

    @property
    def is_allowed(self) -> bool:
        if self.policy_decision.requires_approval:
            return self.approval_decision is not None and self.approval_decision.approved
        return self.policy_decision.allowed

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed


@dataclass(frozen=True)
class ToolProposalDecision:
    """Policy + approval decision for a single proposed tool call."""

    call: ToolCallSpec
    policy_decision: ToolPolicyDecision
    approval_decision: ApprovalDecision | None = None

    @property
    def is_allowed(self) -> bool:
        if self.policy_decision.verdict == "allow":
            return True
        if self.policy_decision.verdict == "requires_approval":
            return self.approval_decision is not None and self.approval_decision.approved
        return False

    @property
    def is_blocked(self) -> bool:
        return not self.is_allowed


@dataclass(frozen=True)
class LLMProposalResult:
    """Complete result of processing an LLM proposal through the safety pipeline.

    Every decision is recorded. The result is deterministic and replayable
    given the same inputs.
    """

    proposal: LLMProposal
    delta_decisions: tuple[DeltaProposalDecision, ...] = ()
    tool_decisions: tuple[ToolProposalDecision, ...] = ()
    commitment_events: tuple[CommitmentEvent, ...] = ()
    revision_events: tuple[ModelRevisionEvent, ...] = ()
    allowed_delta_count: int = 0
    blocked_delta_count: int = 0
    requires_approval_delta_count: int = 0
    allowed_tool_count: int = 0
    blocked_tool_count: int = 0

    @property
    def all_deltas_blocked(self) -> bool:
        return len(self.delta_decisions) > 0 and self.allowed_delta_count == 0

    @property
    def all_tools_blocked(self) -> bool:
        return len(self.tool_decisions) > 0 and self.allowed_tool_count == 0


class LLMProposalAdapter(Protocol):
    """Protocol for adapters that produce validated proposals from LLM output."""

    def adapt(self, raw_llm_output: str, *, objective: str) -> LLMProposal:
        """Convert raw LLM output to a validated proposal."""


@dataclass(frozen=True)
class PlanFormatAdapter:
    """Adapter for LLM output in plan compiler format (patches + tool_calls)."""

    source: str = "plan_compiler"

    def adapt(self, raw_llm_output: str, *, objective: str) -> LLMProposal:
        return parse_llm_proposal(raw_llm_output, source=self.source, objective=objective)


@dataclass(frozen=True)
class RawFormatAdapter:
    """Adapter for unstructured LLM output requiring best-effort parsing."""

    source: str = "raw_llm"

    def adapt(self, raw_llm_output: str, *, objective: str) -> LLMProposal:
        return parse_llm_proposal(raw_llm_output, source=self.source, objective=objective)


def _reject_forbidden_fields(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    present = FORBIDDEN_LLM_FIELDS.intersection(payload)
    if present:
        errors.append(
            "LLM output contains forbidden execution fields: "
            + ", ".join(sorted(present))
        )
    return errors


def _validate_deltas(deltas_data: list[dict[str, Any]]) -> tuple[list[RevisionDelta], list[str]]:
    deltas: list[RevisionDelta] = []
    errors: list[str] = []

    for idx, patch_data in enumerate(deltas_data):
        if not isinstance(patch_data, dict):
            errors.append(f"patch[{idx}] must be a JSON object")
            continue

        section = str(patch_data.get("section", ""))
        key = str(patch_data.get("key", ""))
        op = str(patch_data.get("op", ""))
        value = patch_data.get("value")

        if not section:
            errors.append(f"patch[{idx}] missing section")
            continue
        if not key:
            errors.append(f"patch[{idx}] missing key")
            continue
        if op not in VALID_PATCH_OPS:
            errors.append(f"patch[{idx}] invalid op: {op}")
            continue

        target_kind = _section_key_to_target_kind(section, key)
        target_ref = f"{section}.{key}"

        deltas.append(RevisionDelta(
            delta_id=f"delta-llm-{idx}",
            target_kind=target_kind,
            target_ref=target_ref,
            before_summary="unknown",
            after_summary=str(value)[:200] if value is not None else "null",
            justification=patch_data.get("rationale", f"LLM proposal: {op} {target_ref}"),
            raw_value=value,
        ))

    return deltas, errors


def _validate_tool_calls(
    tool_calls_data: list[dict[str, Any]],
    tool_registry: ToolRegistry | None,
) -> tuple[list[ToolCallSpec], list[str]]:
    calls: list[ToolCallSpec] = []
    errors: list[str] = []

    for idx, tc_data in enumerate(tool_calls_data):
        if not isinstance(tc_data, dict):
            errors.append(f"tool_call[{idx}] must be a JSON object")
            continue

        tool_name = tc_data.get("tool_name")
        arguments = tc_data.get("arguments")

        if not isinstance(tool_name, str) or not tool_name.strip():
            errors.append(f"tool_call[{idx}] missing tool_name")
            continue
        if not isinstance(arguments, dict):
            errors.append(f"tool_call[{idx}] arguments must be a JSON object")
            continue

        if tool_registry is not None and tool_registry.get(tool_name) is None:
            errors.append(f"tool_call[{idx}] unknown tool: {tool_name}")
            continue

        calls.append(ToolCallSpec(
            tool_name=tool_name,
            arguments=arguments,
        ))

    return calls, errors


def _section_key_to_target_kind(section: str, key: str) -> str:
    if section == "goals":
        return "goal_update"
    if section == "self_model":
        return "self_update"
    if section == "memory":
        return "entity_update"
    if section == "beliefs":
        if key == "hypotheses":
            return "hypothesis_update"
        if key == "anchored_facts":
            return "anchor_add"
        return "entity_update"
    if section == "domain_data":
        return "entity_update"
    return "entity_update"


def parse_llm_proposal(
    raw_llm_output: str,
    *,
    source: str = "llm_adapter",
    objective: str = "",
    tool_registry: ToolRegistry | None = None,
) -> LLMProposal:
    """Parse and validate raw LLM output into a typed LLMProposal.

    This is the primary validation boundary. No LLM output reaches the
    policy engine without passing through this function.
    """

    cleaned = raw_llm_output.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return LLMProposal(
            source=source,
            objective=objective,
            raw_llm_output=raw_llm_output,
            validation_errors=(f"invalid JSON: {exc}",),
            is_valid=False,
        )

    if not isinstance(payload, dict):
        return LLMProposal(
            source=source,
            objective=objective,
            raw_llm_output=raw_llm_output,
            validation_errors=("LLM output must be a JSON object",),
            is_valid=False,
        )

    all_errors: list[str] = []
    all_errors.extend(_reject_forbidden_fields(payload))

    patches_data = payload.get("patches", [])
    if not isinstance(patches_data, list):
        patches_data = []

    deltas, delta_errors = _validate_deltas(patches_data)
    all_errors.extend(delta_errors)

    tool_calls_data = payload.get("tool_calls", [])
    if not isinstance(tool_calls_data, list):
        tool_calls_data = []

    calls, call_errors = _validate_tool_calls(tool_calls_data, tool_registry)
    all_errors.extend(call_errors)

    rationale = str(payload.get("rationale", ""))

    return LLMProposal(
        source=source,
        objective=objective or str(payload.get("objective", "")),
        rationale=rationale,
        candidate_deltas=tuple(deltas),
        proposed_tool_calls=tuple(calls),
        raw_llm_output=raw_llm_output,
        validation_errors=tuple(all_errors),
        is_valid=len(all_errors) == 0,
    )


def propose_from_llm(
    proposal: LLMProposal,
    *,
    event_log: EventLog,
    approval_provider: ApprovalProvider | None = None,
    tool_registry: ToolRegistry | None = None,
    current_state_id: str = "ws_0",
) -> LLMProposalResult:
    """Process an LLM proposal through the full safety pipeline.

    Pipeline:
    1. Record proposal received event
    2. Evaluate policy for each delta
    3. Route requires_approval deltas to approval gate
    4. Evaluate policy for each tool call
    5. Route requires_approval tool calls to approval gate
    6. Record commitment events for allowed deltas
    7. Record revision events for approved deltas
    8. Record complete audit trail

    Key invariant: this function only proposes and records.
    It does not modify WorldState directly.
    """

    event_log.append(Event(
        event_type="llm.proposal.received",
        payload={
            "proposal_id": proposal.proposal_id,
            "source": proposal.source,
            "objective": proposal.objective,
            "delta_count": len(proposal.candidate_deltas),
            "tool_call_count": len(proposal.proposed_tool_calls),
            "is_valid": proposal.is_valid,
        },
        actor="llm_proposal_adapter",
    ))

    if not proposal.is_valid:
        event_log.append(Event(
            event_type="llm.proposal.rejected",
            payload={
                "proposal_id": proposal.proposal_id,
                "validation_errors": list(proposal.validation_errors),
            },
            actor="llm_proposal_adapter",
        ))
        return LLMProposalResult(proposal=proposal)

    delta_decisions, commitment_events, revision_events = _process_deltas(
        proposal, event_log, approval_provider, current_state_id,
    )

    tool_decisions = _process_tool_calls(
        proposal, event_log, approval_provider, tool_registry,
    )

    allowed_delta_count = sum(1 for d in delta_decisions if d.is_allowed)
    blocked_delta_count = sum(1 for d in delta_decisions if d.is_blocked and not d.policy_decision.requires_approval)
    requires_approval_delta_count = sum(1 for d in delta_decisions if d.policy_decision.requires_approval)

    allowed_tool_count = sum(1 for t in tool_decisions if t.is_allowed)
    blocked_tool_count = sum(1 for t in tool_decisions if t.is_blocked)

    event_log.append(Event(
        event_type="llm.proposal.processed",
        payload={
            "proposal_id": proposal.proposal_id,
            "allowed_delta_count": allowed_delta_count,
            "blocked_delta_count": blocked_delta_count,
            "requires_approval_delta_count": requires_approval_delta_count,
            "allowed_tool_count": allowed_tool_count,
            "blocked_tool_count": blocked_tool_count,
        },
        actor="llm_proposal_adapter",
    ))

    return LLMProposalResult(
        proposal=proposal,
        delta_decisions=tuple(delta_decisions),
        tool_decisions=tuple(tool_decisions),
        commitment_events=tuple(commitment_events),
        revision_events=tuple(revision_events),
        allowed_delta_count=allowed_delta_count,
        blocked_delta_count=blocked_delta_count,
        requires_approval_delta_count=requires_approval_delta_count,
        allowed_tool_count=allowed_tool_count,
        blocked_tool_count=blocked_tool_count,
    )


def _process_deltas(
    proposal: LLMProposal,
    event_log: EventLog,
    approval_provider: ApprovalProvider | None,
    current_state_id: str,
) -> tuple[list[DeltaProposalDecision], list[CommitmentEvent], list[ModelRevisionEvent]]:
    decisions: list[DeltaProposalDecision] = []
    commitments: list[CommitmentEvent] = []
    revisions: list[ModelRevisionEvent] = []
    state_id = current_state_id

    for i, delta in enumerate(proposal.candidate_deltas):
        policy_decision = evaluate_delta_policy(delta)

        approval_decision = None
        if policy_decision.requires_approval:
            request = ApprovalRequest.from_delta(delta, policy_decision)
            if approval_provider is not None:
                approval_decision = approval_provider.decide_request(request)
            else:
                approval_decision = ApprovalDecision(
                    transition_trace_id=request.request_id,
                    verdict="rejected",
                    decided_by="llm_proposal_adapter",
                    reason="no approval provider configured",
                    request=request,
                )
            event_log.append(approval_decision.to_event())

        decision = DeltaProposalDecision(
            delta=delta,
            policy_decision=policy_decision,
            approval_decision=approval_decision,
        )
        decisions.append(decision)

        commitment = CommitmentEvent(
            event_id=f"ce-prop-{proposal.proposal_id}-{i}",
            source_state_id=state_id,
            commitment_kind=policy_decision.commitment_kind,
            intent_summary=f"proposal:{proposal.proposal_id}:{proposal.objective}",
            action_summary=f"{delta.target_kind} {delta.target_ref}",
            success=decision.is_allowed,
            reversibility=policy_decision.reversibility,
            requires_approval=policy_decision.requires_approval,
        )
        commitments.append(commitment)
        event_log.append(commitment)

        if decision.is_allowed:
            resulting_state_id = f"ws_{int(state_id.split('_')[-1]) + 1}"
            revision_kind = "expansion"
            if delta.target_kind == "self_update":
                revision_kind = "recalibration"
            elif delta.target_kind == "goal_update":
                revision_kind = "confirmation"

            revision = ModelRevisionEvent(
                revision_id=f"rev-{commitment.event_id}",
                prior_state_id=state_id,
                caused_by_event_id=commitment.event_id,
                revision_kind=revision_kind,
                deltas=(delta,),
                resulting_state_id=resulting_state_id,
                revision_summary=delta.justification or f"Delta: {delta.target_kind} {delta.target_ref}",
            )
            revisions.append(revision)
            event_log.append(revision)
            state_id = resulting_state_id

    return decisions, commitments, revisions


def _process_tool_calls(
    proposal: LLMProposal,
    event_log: EventLog,
    approval_provider: ApprovalProvider | None,
    tool_registry: ToolRegistry | None,
) -> list[ToolProposalDecision]:
    decisions: list[ToolProposalDecision] = []

    for call in proposal.proposed_tool_calls:
        if tool_registry is not None:
            policy_decision = evaluate_tool_call_policy(call, tool_registry)
        else:
            policy_decision = ToolPolicyDecision(
                verdict="allow",
                reason="no tool registry configured; defaulting to allow",
                risk="read",
            )

        approval_decision = None
        if policy_decision.verdict == "requires_approval":
            request = ApprovalRequest.from_tool_call(call, policy_decision)
            if approval_provider is not None:
                approval_decision = approval_provider.decide_request(request)
            else:
                approval_decision = ApprovalDecision(
                    transition_trace_id=request.request_id,
                    verdict="rejected",
                    decided_by="llm_proposal_adapter",
                    reason="no approval provider configured",
                    request=request,
                )
            event_log.append(approval_decision.to_event())

        decisions.append(ToolProposalDecision(
            call=call,
            policy_decision=policy_decision,
            approval_decision=approval_decision,
        ))

        event_log.append(Event(
            event_type="llm.proposal.tool_call.evaluated",
            payload={
                "proposal_id": proposal.proposal_id,
                "tool_name": call.tool_name,
                "call_id": call.call_id,
                "policy_verdict": policy_decision.verdict,
                "allowed": ToolProposalDecision(
                    call=call,
                    policy_decision=policy_decision,
                    approval_decision=approval_decision,
                ).is_allowed,
            },
            actor="llm_proposal_adapter",
        ))

    return decisions
