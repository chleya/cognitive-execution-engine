"""Uncertainty router module.

Routes execution decisions based on uncertainty signals:
- Evidence coverage
- Precedent similarity
- Tool risk level
- Historical success rate
- Model self-assessment

Outputs one of three decisions:
- auto_execute: Proceed without human review
- needs_more_evidence: Request additional information before proceeding
- needs_human_review: Escalate to human approval
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any
from enum import Enum


class RoutingDecision(Enum):
    """Routing decisions for execution."""
    AUTO_EXECUTE = "auto_execute"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


@dataclass
class RoutingSignals:
    """Input signals for the uncertainty router."""
    
    evidence_coverage: float  # 0-1, percentage of required evidence available
    precedent_similarity: float  # 0-1, similarity to successful precedents
    tool_risk_level: Literal["low", "medium", "high", "critical"]
    historical_success_rate: float  # 0-1, success rate for similar tasks
    model_self_confidence: float  # 0-1, model's self-reported confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_coverage": self.evidence_coverage,
            "precedent_similarity": self.precedent_similarity,
            "tool_risk_level": self.tool_risk_level,
            "historical_success_rate": self.historical_success_rate,
            "model_self_confidence": self.model_self_confidence,
        }


@dataclass
class RoutingResult:
    """Result of the uncertainty routing decision."""
    
    decision: RoutingDecision
    confidence: float  # 0-1, confidence in this routing decision
    reasoning: str  # Human-readable explanation of the decision
    signals: RoutingSignals  # Input signals used for decision
    thresholds_used: Dict[str, float]  # Threshold values applied
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "signals": self.signals.to_dict(),
            "thresholds_used": self.thresholds_used,
        }


@dataclass
class RouterConfig:
    """Configuration for the uncertainty router thresholds."""
    
    # Evidence coverage thresholds
    min_evidence_for_auto: float = 0.7
    min_evidence_for_review: float = 0.4
    
    # Precedent similarity thresholds
    min_precedent_for_auto: float = 0.6
    
    # Historical success rate thresholds
    min_success_rate_for_auto: float = 0.8
    min_success_rate_for_review: float = 0.5
    
    # Model confidence thresholds
    min_model_confidence_for_auto: float = 0.8
    min_model_confidence_for_review: float = 0.5
    
    # Combined confidence threshold for auto-execute
    min_combined_confidence: float = 0.75
    
    # Risk level mapping
    risk_level_scores: Dict[str, float] = None
    
    def __post_init__(self):
        if self.risk_level_scores is None:
            self.risk_level_scores = {
                "low": 1.0,
                "medium": 0.7,
                "high": 0.3,
                "critical": 0.0
            }


class UncertaintyRouter:
    """Routes execution based on uncertainty signals."""
    
    def __init__(self, config: Optional[RouterConfig] = None):
        """Initialize the uncertainty router.
        
        Args:
            config: Router configuration with thresholds
        """
        self.config = config or RouterConfig()
    
    def route(self, signals: RoutingSignals) -> RoutingResult:
        """Make a routing decision based on input signals.
        
        Args:
            signals: Input signals for routing
            
        Returns:
            RoutingResult with decision and reasoning
        """
        reasoning_parts = []
        
        # Calculate individual signal scores (0-1, higher means safer for auto-execute)
        evidence_score = self._calculate_evidence_score(signals.evidence_coverage, reasoning_parts)
        precedent_score = self._calculate_precedent_score(signals.precedent_similarity, reasoning_parts)
        risk_score = self._calculate_risk_score(signals.tool_risk_level, reasoning_parts)
        success_score = self._calculate_success_score(signals.historical_success_rate, reasoning_parts)
        confidence_score = self._calculate_confidence_score(signals.model_self_confidence, reasoning_parts)
        
        # Calculate combined confidence (weighted average)
        weights = {
            "evidence": 0.25,
            "precedent": 0.15,
            "risk": 0.30,
            "success": 0.15,
            "confidence": 0.15
        }
        
        combined_confidence = (
            evidence_score * weights["evidence"] +
            precedent_score * weights["precedent"] +
            risk_score * weights["risk"] +
            success_score * weights["success"] +
            confidence_score * weights["confidence"]
        )
        
        # Make decision
        decision, decision_reason = self._make_decision(
            combined_confidence,
            signals,
            reasoning_parts
        )
        
        return RoutingResult(
            decision=decision,
            confidence=combined_confidence,
            reasoning="\n".join(reasoning_parts + [f"\nFinal decision: {decision_reason}"]),
            signals=signals,
            thresholds_used={
                "min_evidence_for_auto": self.config.min_evidence_for_auto,
                "min_precedent_for_auto": self.config.min_precedent_for_auto,
                "min_success_rate_for_auto": self.config.min_success_rate_for_auto,
                "min_model_confidence_for_auto": self.config.min_model_confidence_for_auto,
                "min_combined_confidence": self.config.min_combined_confidence,
            }
        )
    
    def _calculate_evidence_score(self, coverage: float, reasoning: list) -> float:
        """Calculate evidence coverage score."""
        if coverage >= self.config.min_evidence_for_auto:
            reasoning.append(f"✓ Evidence coverage: {coverage:.2f} (sufficient for auto-execute)")
            return 1.0
        elif coverage >= self.config.min_evidence_for_review:
            reasoning.append(f"⚠ Evidence coverage: {coverage:.2f} (marginal)")
            return 0.5
        else:
            reasoning.append(f"✗ Evidence coverage: {coverage:.2f} (insufficient)")
            return 0.0
    
    def _calculate_precedent_score(self, similarity: float, reasoning: list) -> float:
        """Calculate precedent similarity score."""
        if similarity >= self.config.min_precedent_for_auto:
            reasoning.append(f"✓ Precedent similarity: {similarity:.2f} (good precedents available)")
            return 1.0
        elif similarity > 0.3:
            reasoning.append(f"⚠ Precedent similarity: {similarity:.2f} (some precedents)")
            return 0.5
        else:
            reasoning.append(f"ℹ Precedent similarity: {similarity:.2f} (few/no precedents)")
            return 0.3
    
    def _calculate_risk_score(self, risk_level: str, reasoning: list) -> float:
        """Calculate tool risk score."""
        score = self.config.risk_level_scores.get(risk_level, 0.5)
        if risk_level == "low":
            reasoning.append(f"✓ Tool risk: {risk_level} (safe)")
        elif risk_level == "medium":
            reasoning.append(f"⚠ Tool risk: {risk_level} (moderate)")
        elif risk_level == "high":
            reasoning.append(f"✗ Tool risk: {risk_level} (high - human review recommended)")
        else:  # critical
            reasoning.append(f"✗✗ Tool risk: {risk_level} (CRITICAL - requires human review)")
        return score
    
    def _calculate_success_score(self, success_rate: float, reasoning: list) -> float:
        """Calculate historical success rate score."""
        if success_rate >= self.config.min_success_rate_for_auto:
            reasoning.append(f"✓ Historical success rate: {success_rate:.2f} (excellent track record)")
            return 1.0
        elif success_rate >= self.config.min_success_rate_for_review:
            reasoning.append(f"⚠ Historical success rate: {success_rate:.2f} (mixed track record)")
            return 0.5
        else:
            reasoning.append(f"✗ Historical success rate: {success_rate:.2f} (poor track record)")
            return 0.0
    
    def _calculate_confidence_score(self, confidence: float, reasoning: list) -> float:
        """Calculate model self-confidence score."""
        if confidence >= self.config.min_model_confidence_for_auto:
            reasoning.append(f"✓ Model confidence: {confidence:.2f} (high)")
            return 1.0
        elif confidence >= self.config.min_model_confidence_for_review:
            reasoning.append(f"⚠ Model confidence: {confidence:.2f} (moderate)")
            return 0.5
        else:
            reasoning.append(f"✗ Model confidence: {confidence:.2f} (low)")
            return 0.0
    
    def _make_decision(
        self,
        combined_confidence: float,
        signals: RoutingSignals,
        reasoning: list
    ) -> tuple[RoutingDecision, str]:
        """Make final routing decision based on combined confidence."""
        
        # Critical risk always requires human review
        if signals.tool_risk_level == "critical":
            return (
                RoutingDecision.NEEDS_HUMAN_REVIEW,
                "Critical risk tools always require human review"
            )
        
        # Very low evidence coverage needs more evidence
        if signals.evidence_coverage < self.config.min_evidence_for_review:
            return (
                RoutingDecision.NEEDS_MORE_EVIDENCE,
                f"Insufficient evidence coverage ({signals.evidence_coverage:.2f} < {self.config.min_evidence_for_review:.2f})"
            )
        
        # High risk needs human review
        if signals.tool_risk_level == "high":
            return (
                RoutingDecision.NEEDS_HUMAN_REVIEW,
                "High-risk tools require human review"
            )
        
        # Good combined confidence allows auto-execute
        if combined_confidence >= self.config.min_combined_confidence:
            return (
                RoutingDecision.AUTO_EXECUTE,
                f"Combined confidence {combined_confidence:.2f} meets threshold for auto-execution"
            )
        
        # Otherwise, need human review
        return (
            RoutingDecision.NEEDS_HUMAN_REVIEW,
            f"Combined confidence {combined_confidence:.2f} below auto-execute threshold"
        )
