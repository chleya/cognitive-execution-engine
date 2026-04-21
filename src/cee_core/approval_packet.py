"""Approval packet module for structured human review.

Provides a structured format for presenting execution requests to human
reviewers, including all necessary context, evidence, and rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, UTC
from enum import Enum

from .world_schema import RevisionDelta
from .retriever import RetrievalResult
from .evidence_graph import EvidenceGraph, EvidenceGraphAnalyzer
from .uncertainty_router import RoutingResult


class ApprovalVerdict(Enum):
    """Possible verdicts for an approval request."""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_INFO = "needs_more_info"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ApprovalPacket:
    """Structured approval request package.

    Contains all information needed for a human reviewer to make an
    informed decision about whether to approve an execution request.
    """

    original_task: str
    proposed_actions: str

    state_diff: Dict[str, Any]
    deltas: List[RevisionDelta]

    evidence_used: List[RetrievalResult]
    precedent_summary: List[Dict[str, Any]]
    router_result: Optional[RoutingResult]
    evidence_graph: Optional[EvidenceGraph]

    risk_level: str
    reversible: bool

    packet_id: str = field(default_factory=lambda: f"approval_{uuid4().hex}")
    created_at: float = field(default_factory=lambda: datetime.now(UTC).timestamp())
    rollback_instructions: str = ""

    reviewer_notes: str = ""
    verdict: Optional[ApprovalVerdict] = None
    reviewed_at: Optional[float] = None
    reviewer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert approval packet to dictionary for serialization."""
        return {
            "packet_id": self.packet_id,
            "created_at": self.created_at,
            "original_task": self.original_task,
            "proposed_actions": self.proposed_actions,
            "state_diff": self.state_diff,
            "deltas": [d.to_dict() for d in self.deltas],
            "evidence_used": [
                {
                    "content": e.content,
                    "relevance_score": e.relevance_score,
                    "result_type": e.result_type,
                    "source_id": e.source_id,
                    "metadata": e.metadata,
                    "match_reason": e.match_reason
                }
                for e in self.evidence_used
            ],
            "precedent_summary": self.precedent_summary,
            "router_result": self.router_result.to_dict() if self.router_result else None,
            "evidence_graph": self.evidence_graph.to_dict() if self.evidence_graph else None,
            "risk_level": self.risk_level,
            "reversible": self.reversible,
            "rollback_instructions": self.rollback_instructions,
            "reviewer_notes": self.reviewer_notes,
            "verdict": self.verdict.value if self.verdict else None,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer
        }

    def format_for_human_review(self, max_length: int = 6000) -> str:
        """Format the approval packet into a human-readable summary."""
        parts = []

        parts.append("=" * 60)
        parts.append("APPROVAL REQUEST")
        parts.append("=" * 60)
        parts.append(f"Packet ID: {self.packet_id}")
        parts.append(f"Created: {datetime.fromtimestamp(self.created_at).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        parts.append(f"Risk Level: {self.risk_level.upper()}")
        parts.append(f"Reversible: {'YES' if self.reversible else 'NO'}")
        parts.append("")

        if self.router_result:
            parts.append(f"Router Recommendation: {self.router_result.decision.value.upper()}")
            parts.append(f"Router Confidence: {self.router_result.confidence:.2f}")
            parts.append("")

        parts.append("-" * 60)
        parts.append("TASK & PROPOSED ACTIONS")
        parts.append("-" * 60)
        parts.append(self.original_task[:200] + "..." if len(self.original_task) > 200 else self.original_task)
        parts.append("")
        parts.append("Proposed Actions:")
        parts.append(self.proposed_actions[:300] + "..." if len(self.proposed_actions) > 300 else self.proposed_actions)
        parts.append("")

        parts.append("-" * 60)
        parts.append("STATE IMPACT")
        parts.append("-" * 60)
        state_diff_str = str(self.state_diff)[:400] + "..." if len(str(self.state_diff)) > 400 else str(self.state_diff)
        parts.append(f"Changes: {len(self.deltas)} delta(s)")
        parts.append(f"State Diff: {state_diff_str}")
        parts.append("")

        if self.evidence_used:
            parts.append("-" * 60)
            parts.append(f"EVIDENCE USED ({len(self.evidence_used)})")
            parts.append("-" * 60)
            for i, ev in enumerate(self.evidence_used[:5], 1):
                parts.append(f"{i}. [{ev.result_type.upper()}] (relevance: {ev.relevance_score:.2f})")
                parts.append(f"   {ev.content[:150]}...")
            if len(self.evidence_used) > 5:
                parts.append(f"   ... and {len(self.evidence_used) - 5} more")
            parts.append("")

        if self.precedent_summary:
            parts.append("-" * 60)
            parts.append(f"PRECEDENTS ({len(self.precedent_summary)})")
            parts.append("-" * 60)
            for i, prec in enumerate(self.precedent_summary[:3], 1):
                outcome = prec.get('outcome', 'unknown')
                parts.append(f"{i}. [{outcome.upper()}] {prec.get('task', '')[:100]}...")
            if len(self.precedent_summary) > 3:
                parts.append(f"   ... and {len(self.precedent_summary) - 3} more")
            parts.append("")

        if self.evidence_graph:
            parts.append("-" * 60)
            parts.append("EVIDENCE GRAPH QUALITY")
            parts.append("-" * 60)
            analyzer = EvidenceGraphAnalyzer(self.evidence_graph)
            audit = analyzer.generate_audit_summary()
            parts.append(f"Total Conclusions: {audit['node_counts_by_type']['conclusion']}")
            parts.append(f"Avg Conclusion Confidence: {audit['average_conclusion_confidence']:.2f}")
            parts.append(f"Evidence Coverage: {audit['average_evidence_coverage']:.2f}")
            parts.append(f"Contradictions Found: {audit['contradictions_found']}")
            parts.append(f"Overall Quality Score: {audit['quality_score']:.2f}")
            parts.append("")

        if self.rollback_instructions:
            parts.append("-" * 60)
            parts.append("ROLLBACK INSTRUCTIONS")
            parts.append("-" * 60)
            parts.append(self.rollback_instructions[:300] + "..." if len(self.rollback_instructions) > 300 else self.rollback_instructions)
            parts.append("")

        parts.append("=" * 60)
        parts.append("REVIEWER DECISION")
        parts.append("=" * 60)

        if self.verdict:
            parts.append(f"Verdict: {self.verdict.value.upper()}")
            if self.reviewer:
                parts.append(f"Reviewed by: {self.reviewer}")
            if self.reviewed_at:
                parts.append(f"Reviewed at: {datetime.fromtimestamp(self.reviewed_at).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            if self.reviewer_notes:
                parts.append(f"Notes: {self.reviewer_notes}")
        else:
            parts.append("Please review and select: [APPROVED | REJECTED | NEEDS_MORE_INFO]")
            parts.append("Add notes below:")

        full_text = "\n".join(parts)
        if len(full_text) > max_length:
            full_text = full_text[:max_length] + "\n[TRUNCATED - too long for preview]"

        return full_text

    def record_verdict(
        self,
        verdict: ApprovalVerdict,
        reviewer: str,
        notes: str = ""
    ) -> None:
        """Record the reviewer's verdict."""
        self.verdict = verdict
        self.reviewer = reviewer
        self.reviewer_notes = notes
        self.reviewed_at = datetime.now(UTC).timestamp()

    @property
    def is_resolved(self) -> bool:
        """Check if the approval request has been resolved."""
        return self.verdict is not None

    @property
    def is_approved(self) -> bool:
        """Check if the request was approved (either manually or automatically)."""
        return self.verdict in (ApprovalVerdict.APPROVED, ApprovalVerdict.AUTO_APPROVED)
