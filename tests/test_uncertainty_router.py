"""Tests for uncertainty_router module."""

import pytest
from src.cee_core.uncertainty_router import (
    UncertaintyRouter,
    RoutingSignals,
    RoutingResult,
    RoutingDecision,
    RouterConfig,
)


class TestRouterConfig:
    """Tests for RouterConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RouterConfig()
        
        assert config.min_evidence_for_auto == 0.7
        assert config.min_evidence_for_review == 0.4
        assert config.min_precedent_for_auto == 0.6
        assert config.min_success_rate_for_auto == 0.8
        assert config.min_model_confidence_for_auto == 0.8
        assert config.min_combined_confidence == 0.75
        assert config.risk_level_scores == {
            "low": 1.0,
            "medium": 0.7,
            "high": 0.3,
            "critical": 0.0
        }

    def test_custom_config(self):
        """Test custom configuration."""
        config = RouterConfig(
            min_evidence_for_auto=0.8,
            min_combined_confidence=0.8,
            risk_level_scores={"low": 0.9, "medium": 0.5, "high": 0.1, "critical": 0.0}
        )
        
        assert config.min_evidence_for_auto == 0.8
        assert config.min_combined_confidence == 0.8
        assert config.risk_level_scores["low"] == 0.9


class TestRoutingSignals:
    """Tests for RoutingSignals dataclass."""

    def test_create_signals(self):
        """Test creating routing signals."""
        signals = RoutingSignals(
            evidence_coverage=0.8,
            precedent_similarity=0.7,
            tool_risk_level="low",
            historical_success_rate=0.9,
            model_self_confidence=0.85
        )
        
        assert signals.evidence_coverage == 0.8
        assert signals.precedent_similarity == 0.7
        assert signals.tool_risk_level == "low"
        assert signals.historical_success_rate == 0.9
        assert signals.model_self_confidence == 0.85

    def test_to_dict(self):
        """Test converting signals to dict."""
        signals = RoutingSignals(
            evidence_coverage=0.8,
            precedent_similarity=0.7,
            tool_risk_level="medium",
            historical_success_rate=0.9,
            model_self_confidence=0.85
        )
        
        sig_dict = signals.to_dict()
        
        assert sig_dict["evidence_coverage"] == 0.8
        assert sig_dict["tool_risk_level"] == "medium"


class TestUncertaintyRouter:
    """Tests for UncertaintyRouter class."""

    @pytest.fixture
    def router(self):
        """Create a default router for testing."""
        return UncertaintyRouter()

    def test_auto_execute_decision(self, router):
        """Test auto-execute decision when all signals are good."""
        signals = RoutingSignals(
            evidence_coverage=0.9,
            precedent_similarity=0.8,
            tool_risk_level="low",
            historical_success_rate=0.95,
            model_self_confidence=0.9
        )
        
        result = router.route(signals)
        
        assert result.decision == RoutingDecision.AUTO_EXECUTE
        assert result.confidence >= 0.75
        assert "auto-execute" in result.reasoning.lower()

    def test_needs_human_review_critical_risk(self, router):
        """Test that critical risk always requires human review."""
        signals = RoutingSignals(
            evidence_coverage=1.0,
            precedent_similarity=1.0,
            tool_risk_level="critical",
            historical_success_rate=1.0,
            model_self_confidence=1.0
        )
        
        result = router.route(signals)
        
        assert result.decision == RoutingDecision.NEEDS_HUMAN_REVIEW
        assert "critical" in result.reasoning.lower()

    def test_needs_human_review_high_risk(self, router):
        """Test that high risk requires human review."""
        signals = RoutingSignals(
            evidence_coverage=0.9,
            precedent_similarity=0.8,
            tool_risk_level="high",
            historical_success_rate=0.9,
            model_self_confidence=0.9
        )
        
        result = router.route(signals)
        
        assert result.decision == RoutingDecision.NEEDS_HUMAN_REVIEW
        assert "high-risk" in result.reasoning.lower()

    def test_needs_more_evidence_low_coverage(self, router):
        """Test that very low evidence coverage needs more evidence."""
        signals = RoutingSignals(
            evidence_coverage=0.3,
            precedent_similarity=0.5,
            tool_risk_level="low",
            historical_success_rate=0.7,
            model_self_confidence=0.6
        )
        
        result = router.route(signals)
        
        assert result.decision == RoutingDecision.NEEDS_MORE_EVIDENCE
        assert "insufficient evidence" in result.reasoning.lower()

    def test_needs_human_review_low_combined_confidence(self, router):
        """Test that low combined confidence requires human review."""
        signals = RoutingSignals(
            evidence_coverage=0.5,
            precedent_similarity=0.4,
            tool_risk_level="medium",
            historical_success_rate=0.6,
            model_self_confidence=0.5
        )
        
        result = router.route(signals)
        
        assert result.decision == RoutingDecision.NEEDS_HUMAN_REVIEW
        assert "below auto-execute threshold" in result.reasoning.lower()

    def test_router_with_custom_config(self):
        """Test router with custom configuration."""
        custom_config = RouterConfig(
            min_combined_confidence=0.5,
            min_evidence_for_auto=0.5
        )
        router = UncertaintyRouter(config=custom_config)
        
        signals = RoutingSignals(
            evidence_coverage=0.6,
            precedent_similarity=0.6,
            tool_risk_level="low",
            historical_success_rate=0.7,
            model_self_confidence=0.7
        )
        
        result = router.route(signals)
        assert result.decision == RoutingDecision.AUTO_EXECUTE

    def test_routing_result_to_dict(self, router):
        """Test converting routing result to dict."""
        signals = RoutingSignals(
            evidence_coverage=0.8,
            precedent_similarity=0.7,
            tool_risk_level="low",
            historical_success_rate=0.9,
            model_self_confidence=0.85
        )
        
        result = router.route(signals)
        result_dict = result.to_dict()
        
        assert result_dict["decision"] in ["auto_execute", "needs_human_review", "needs_more_evidence"]
        assert "confidence" in result_dict
        assert "signals" in result_dict
        assert "thresholds_used" in result_dict

    def test_medium_risk_marginal_signals(self, router):
        """Test medium risk with marginal signals."""
        signals = RoutingSignals(
            evidence_coverage=0.6,
            precedent_similarity=0.5,
            tool_risk_level="medium",
            historical_success_rate=0.7,
            model_self_confidence=0.7
        )
        
        result = router.route(signals)
        assert result.decision in [RoutingDecision.NEEDS_HUMAN_REVIEW, RoutingDecision.AUTO_EXECUTE]

    def test_boundary_auto_execute(self, router):
        """Test at the boundary of auto-execute."""
        signals = RoutingSignals(
            evidence_coverage=0.7,
            precedent_similarity=0.6,
            tool_risk_level="low",
            historical_success_rate=0.8,
            model_self_confidence=0.8
        )
        
        result = router.route(signals)
        assert result.confidence > 0

    def test_all_signals_minimum_for_auto(self, router):
        """Test all signals at minimum for auto-execute."""
        signals = RoutingSignals(
            evidence_coverage=0.7,
            precedent_similarity=0.6,
            tool_risk_level="low",
            historical_success_rate=0.8,
            model_self_confidence=0.8
        )
        
        result = router.route(signals)
        assert result.decision in [RoutingDecision.AUTO_EXECUTE, RoutingDecision.NEEDS_HUMAN_REVIEW]
