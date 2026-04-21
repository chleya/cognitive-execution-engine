"""Tests for Memory Promotion pipeline.

Tests cover:
- MemoryPromotionRequest construction and serialization
- DefaultMemoryPromotionPolicy evaluation rules
- promote_to_memory() full pipeline (policy, audit, storage)
- promote_from_observation() convenience function
- promote_from_revision() convenience function
- Audit trail completeness
- Deterministic replayability
"""

import json
import os
import tempfile

import pytest

from cee_core.event_log import EventLog
from cee_core.memory_promotion import (
    DefaultMemoryPromotionPolicy,
    MemoryPromotionPolicyDecision,
    MemoryPromotionRequest,
    MemoryPromotionResult,
    promote_from_observation,
    promote_from_revision,
    promote_to_memory,
    MIN_CONFIDENCE,
    MIN_EVIDENCE_WEIGHT,
    MAX_STATE_DIFF_SIZE,
)
from cee_core.memory_store import MemoryStore
from cee_core.memory_types import PrecedentMemory
from cee_core.observations import ObservationCandidate
from cee_core.revision import ModelRevisionEvent
from cee_core.world_schema import RevisionDelta


@pytest.fixture
def memory_store(tmp_path):
    return MemoryStore(storage_path=str(tmp_path / "mem_store"))


@pytest.fixture
def event_log():
    return EventLog()


def _make_observation(
    confidence: float = 0.8,
    evidence_weight: float = 1.0,
) -> ObservationCandidate:
    return ObservationCandidate(
        source_tool="read_docs",
        call_id="call_001",
        content="test observation content",
        confidence=confidence,
        evidence_weight=evidence_weight,
        provenance=("tool:read_docs", "call:call_001"),
    )


def _make_revision(
    justification: str = "test justification",
) -> ModelRevisionEvent:
    delta = RevisionDelta(
        delta_id="delta-1",
        target_kind="entity_update",
        target_ref="beliefs.test",
        before_summary="unknown",
        after_summary="updated",
        justification=justification,
    )
    return ModelRevisionEvent(
        revision_id="rev_001",
        prior_state_id="ws_0",
        caused_by_event_id="ce_001",
        revision_kind="expansion",
        deltas=(delta,),
        resulting_state_id="ws_1",
        revision_summary="test revision",
    )


class TestMemoryPromotionRequest:
    def test_default_values(self):
        req = MemoryPromotionRequest()
        assert req.source == "observation"
        assert req.outcome == "success"
        assert req.domain_label == "default"
        assert req.request_id.startswith("mpr_")

    def test_unique_request_ids(self):
        r1 = MemoryPromotionRequest()
        r2 = MemoryPromotionRequest()
        assert r1.request_id != r2.request_id

    def test_to_dict_basic(self):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
        )
        d = req.to_dict()
        assert d["source"] == "observation"
        assert d["task_signature"] == "test.task"
        assert d["outcome"] == "success"

    def test_to_dict_with_observation(self):
        obs = _make_observation()
        req = MemoryPromotionRequest(observation=obs)
        d = req.to_dict()
        assert d["observation_call_id"] == "call_001"
        assert d["observation_tool"] == "read_docs"

    def test_to_dict_with_revision(self):
        rev = _make_revision()
        req = MemoryPromotionRequest(revision_event=rev)
        d = req.to_dict()
        assert d["revision_id"] == "rev_001"


class TestDefaultMemoryPromotionPolicy:
    def test_allows_valid_request(self):
        req = MemoryPromotionRequest(
            source="observation",
            task_signature="test.task",
            outcome="success",
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert decision.allowed
        assert not decision.violated_rules

    def test_rejects_empty_task_signature(self):
        req = MemoryPromotionRequest(
            task_signature="",
            outcome="success",
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert "empty_task_signature" in decision.violated_rules

    def test_rejects_invalid_outcome(self):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="unknown",
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("invalid_outcome" in r for r in decision.violated_rules)

    def test_accepts_valid_outcomes(self):
        for outcome in ("success", "failure", "partial_success"):
            req = MemoryPromotionRequest(
                task_signature="test.task",
                outcome=outcome,
            )
            policy = DefaultMemoryPromotionPolicy()
            decision = policy.evaluate(req)
            assert decision.allowed, f"outcome '{outcome}' should be allowed"

    def test_rejects_invalid_source(self):
        req = MemoryPromotionRequest(
            source="invalid_source",
            task_signature="test.task",
            outcome="success",
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("invalid_source" in r for r in decision.violated_rules)

    def test_accepts_valid_sources(self):
        for source in ("observation", "revision", "belief", "llm_proposal"):
            req = MemoryPromotionRequest(
                source=source,
                task_signature="test.task",
                outcome="success",
            )
            policy = DefaultMemoryPromotionPolicy()
            decision = policy.evaluate(req)
            assert decision.allowed, f"source '{source}' should be allowed"

    def test_rejects_oversized_state_diff(self):
        large_diff = {"key": "x" * (MAX_STATE_DIFF_SIZE + 100)}
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
            state_diff=large_diff,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("state_diff_too_large" in r for r in decision.violated_rules)

    def test_allows_normal_sized_state_diff(self):
        normal_diff = {"key": "value", "count": 42}
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
            state_diff=normal_diff,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert decision.allowed

    def test_rejects_low_confidence_observation(self):
        obs = _make_observation(confidence=0.01)
        req = MemoryPromotionRequest(
            source="observation",
            task_signature="test.task",
            outcome="success",
            observation=obs,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("insufficient_confidence" in r for r in decision.violated_rules)

    def test_rejects_low_evidence_weight_observation(self):
        obs = _make_observation(evidence_weight=0.01)
        req = MemoryPromotionRequest(
            source="observation",
            task_signature="test.task",
            outcome="success",
            observation=obs,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("insufficient_evidence_weight" in r for r in decision.violated_rules)

    def test_accepts_sufficient_confidence_observation(self):
        obs = _make_observation(confidence=0.5, evidence_weight=0.5)
        req = MemoryPromotionRequest(
            source="observation",
            task_signature="test.task",
            outcome="success",
            observation=obs,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert decision.allowed

    def test_rejects_revision_with_empty_justification(self):
        rev = _make_revision(justification="")
        req = MemoryPromotionRequest(
            source="revision",
            task_signature="test.task",
            outcome="success",
            revision_event=rev,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert any("delta_without_justification" in r for r in decision.violated_rules)

    def test_accepts_revision_with_justification(self):
        rev = _make_revision(justification="well justified")
        req = MemoryPromotionRequest(
            source="revision",
            task_signature="test.task",
            outcome="success",
            revision_event=rev,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert decision.allowed

    def test_multiple_violations_all_reported(self):
        obs = _make_observation(confidence=0.01)
        req = MemoryPromotionRequest(
            source="invalid_source",
            task_signature="",
            outcome="unknown",
            observation=obs,
        )
        policy = DefaultMemoryPromotionPolicy()
        decision = policy.evaluate(req)

        assert not decision.allowed
        assert len(decision.violated_rules) >= 3

    def test_custom_min_confidence(self):
        obs = _make_observation(confidence=0.3)
        req = MemoryPromotionRequest(
            source="observation",
            task_signature="test.task",
            outcome="success",
            observation=obs,
        )
        strict_policy = DefaultMemoryPromotionPolicy(min_confidence=0.5)
        lenient_policy = DefaultMemoryPromotionPolicy(min_confidence=0.1)

        assert not strict_policy.evaluate(req).allowed
        assert lenient_policy.evaluate(req).allowed

    def test_custom_max_state_diff_size(self):
        small_diff = {"key": "a" * 100}
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
            state_diff=small_diff,
        )
        strict_policy = DefaultMemoryPromotionPolicy(max_state_diff_size=50)
        lenient_policy = DefaultMemoryPromotionPolicy(max_state_diff_size=500)

        assert not strict_policy.evaluate(req).allowed
        assert lenient_policy.evaluate(req).allowed


class TestMemoryPromotionPolicyDecision:
    def test_to_dict(self):
        decision = MemoryPromotionPolicyDecision(
            allowed=True,
            reason="satisfied",
            violated_rules=(),
        )
        d = decision.to_dict()
        assert d["allowed"] is True
        assert d["reason"] == "satisfied"
        assert d["violated_rules"] == []

    def test_rejected_decision_to_dict(self):
        decision = MemoryPromotionPolicyDecision(
            allowed=False,
            reason="violated",
            violated_rules=("rule1", "rule2"),
        )
        d = decision.to_dict()
        assert d["allowed"] is False
        assert len(d["violated_rules"]) == 2


class TestPromoteToMemory:
    def test_promotion_requested_event(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
        )
        promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        events = event_log.all()
        assert any(e.event_type == "memory.promotion.requested" for e in events)

    def test_approved_promotion_stores_memory(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            task_summary="test summary",
            outcome="success",
            domain_label="test_domain",
        )
        result = promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        assert result.promoted
        assert result.memory is not None
        assert result.memory_id is not None
        assert result.memory.task_signature == "test.task"
        assert result.memory.domain_label == "test_domain"

    def test_approved_promotion_event(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
        )
        promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        events = event_log.all()
        assert any(e.event_type == "memory.promotion.approved" for e in events)

    def test_rejected_promotion_no_storage(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="",
            outcome="success",
        )
        result = promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        assert result.blocked
        assert result.memory is None
        assert result.memory_id is None
        assert memory_store.get_count() == 0

    def test_rejected_promotion_event(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="",
            outcome="success",
        )
        promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        events = event_log.all()
        assert any(e.event_type == "memory.promotion.rejected" for e in events)

    def test_custom_policy(self, event_log, memory_store):
        class AlwaysRejectPolicy:
            def evaluate(self, request):
                return MemoryPromotionPolicyDecision(
                    allowed=False,
                    reason="always rejected",
                    violated_rules=("always_reject",),
                )

        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
        )
        result = promote_to_memory(
            req,
            event_log=event_log,
            memory_store=memory_store,
            policy=AlwaysRejectPolicy(),
        )

        assert result.blocked
        assert result.memory is None

    def test_stored_memory_retrievable(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            task_summary="test summary",
            outcome="success",
            state_diff={"key": "value"},
            evidence_refs=["ev1", "ev2"],
        )
        result = promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        assert result.memory_id is not None
        stored = memory_store.get_memory(result.memory_id)
        assert stored is not None
        assert stored.task_signature == "test.task"
        assert stored.outcome == "success"

    def test_promotion_with_failure_outcome(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="failure",
            failure_mode="timeout",
        )
        result = promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        assert result.promoted
        assert result.memory.failure_mode == "timeout"

    def test_promotion_with_approval_result(self, event_log, memory_store):
        req = MemoryPromotionRequest(
            task_signature="test.task",
            outcome="success",
            approval_result="approved",
        )
        result = promote_to_memory(req, event_log=event_log, memory_store=memory_store)

        assert result.promoted
        assert result.memory.approval_result == "approved"


class TestPromoteFromObservation:
    def test_promote_valid_observation(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            task_summary="observed test data",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory is not None
        assert result.memory.task_signature == "analysis.observe"

    def test_reject_low_confidence_observation(self, event_log, memory_store):
        obs = _make_observation(confidence=0.01)
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.blocked

    def test_observation_summary_used_as_task_summary(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.task_summary == "test observation content"

    def test_explicit_summary_overrides_observation(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            task_summary="explicit summary",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.task_summary == "explicit summary"

    def test_state_diff_passed_through(self, event_log, memory_store):
        obs = _make_observation()
        state_diff = {"entities_added": 3, "confidence_delta": 0.2}
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            state_diff=state_diff,
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.state_diff == state_diff

    def test_evidence_refs_passed_through(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            evidence_refs=("ev1", "ev2"),
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert "ev1" in result.memory.evidence_refs
        assert "ev2" in result.memory.evidence_refs

    def test_domain_label_passed_through(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="analysis.observe",
            domain_label="code_review",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.domain_label == "code_review"


class TestPromoteFromRevision:
    def test_promote_valid_revision(self, event_log, memory_store):
        rev = _make_revision()
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            task_summary="revised beliefs",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory is not None
        assert result.memory.task_signature == "analysis.revise"

    def test_reject_revision_without_justification(self, event_log, memory_store):
        rev = _make_revision(justification="")
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.blocked

    def test_state_diff_extracted_from_revision(self, event_log, memory_store):
        rev = _make_revision()
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert "revision_id" in result.memory.state_diff
        assert "deltas" in result.memory.state_diff

    def test_custom_state_diff_overrides_extraction(self, event_log, memory_store):
        rev = _make_revision()
        custom_diff = {"custom_key": "custom_value"}
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            state_diff=custom_diff,
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.state_diff == custom_diff

    def test_revision_summary_used_as_task_summary(self, event_log, memory_store):
        rev = _make_revision()
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.task_summary == "test revision"

    def test_explicit_summary_overrides_revision(self, event_log, memory_store):
        rev = _make_revision()
        result = promote_from_revision(
            rev,
            task_signature="analysis.revise",
            task_summary="explicit summary",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory.task_summary == "explicit summary"


class TestMemoryPromotionResult:
    def test_promoted_property(self):
        req = MemoryPromotionRequest(task_signature="test", outcome="success")
        decision = MemoryPromotionPolicyDecision(allowed=True, reason="ok")
        memory = PrecedentMemory(
            task_signature="test",
            state_diff={},
            evidence_refs=[],
            outcome="success",
        )
        result = MemoryPromotionResult(
            request=req,
            policy_decision=decision,
            memory=memory,
            memory_id="mem_123",
        )

        assert result.promoted
        assert not result.blocked

    def test_blocked_property(self):
        req = MemoryPromotionRequest(task_signature="", outcome="success")
        decision = MemoryPromotionPolicyDecision(
            allowed=False,
            reason="violated",
            violated_rules=("empty_task_signature",),
        )
        result = MemoryPromotionResult(
            request=req,
            policy_decision=decision,
        )

        assert result.blocked
        assert not result.promoted
        assert result.memory is None


class TestAuditTrail:
    def test_full_audit_trail_on_approval(self, event_log, memory_store):
        obs = _make_observation()
        promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=event_log,
            memory_store=memory_store,
        )

        events = event_log.all()
        event_types = [e.event_type for e in events]
        assert "memory.promotion.requested" in event_types
        assert "memory.promotion.approved" in event_types

    def test_full_audit_trail_on_rejection(self, event_log, memory_store):
        obs = _make_observation(confidence=0.01)
        promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=event_log,
            memory_store=memory_store,
        )

        events = event_log.all()
        event_types = [e.event_type for e in events]
        assert "memory.promotion.requested" in event_types
        assert "memory.promotion.rejected" in event_types
        assert "memory.promotion.approved" not in event_types

    def test_approved_event_contains_memory_id(self, event_log, memory_store):
        obs = _make_observation()
        promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=event_log,
            memory_store=memory_store,
        )

        approved_events = [
            e for e in event_log.all()
            if e.event_type == "memory.promotion.approved"
        ]
        assert len(approved_events) == 1
        assert "memory_id" in approved_events[0].payload

    def test_rejected_event_contains_violated_rules(self, event_log, memory_store):
        obs = _make_observation(confidence=0.01)
        promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=event_log,
            memory_store=memory_store,
        )

        rejected_events = [
            e for e in event_log.all()
            if e.event_type == "memory.promotion.rejected"
        ]
        assert len(rejected_events) == 1
        assert "violated_rules" in rejected_events[0].payload


class TestDeterminism:
    def test_same_request_same_result(self, memory_store, tmp_path):
        obs = _make_observation()

        log1 = EventLog()
        store1 = MemoryStore(storage_path=str(tmp_path / "mem1"))
        result1 = promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=log1,
            memory_store=store1,
        )

        log2 = EventLog()
        store2 = MemoryStore(storage_path=str(tmp_path / "mem2"))
        result2 = promote_from_observation(
            obs,
            task_signature="test.task",
            event_log=log2,
            memory_store=store2,
        )

        assert result1.promoted == result2.promoted
        assert result1.blocked == result2.blocked
        assert result1.policy_decision.allowed == result2.policy_decision.allowed


class TestEndToEnd:
    def test_observation_to_memory_to_retrieval(self, event_log, memory_store):
        obs = _make_observation()
        result = promote_from_observation(
            obs,
            task_signature="document_analysis.extract_info",
            task_summary="Extracted key information from document",
            domain_label="document_analysis",
            evidence_refs=("ev_doc_1",),
            state_diff={"entities_found": 3},
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        assert result.memory_id is not None

        stored = memory_store.get_memory(result.memory_id)
        assert stored is not None
        assert stored.task_signature == "document_analysis.extract_info"
        assert stored.domain_label == "document_analysis"
        assert stored.outcome == "success"

    def test_revision_to_memory_to_retrieval(self, event_log, memory_store):
        rev = _make_revision(justification="evidence supports update")
        result = promote_from_revision(
            rev,
            task_signature="belief_update.correction",
            task_summary="Corrected belief based on new evidence",
            domain_label="core",
            evidence_refs=("ev_obs_1",),
            event_log=event_log,
            memory_store=memory_store,
        )

        assert result.promoted
        stored = memory_store.get_memory(result.memory_id)
        assert stored is not None
        assert stored.task_signature == "belief_update.correction"

    def test_multiple_promotions_all_stored(self, event_log, memory_store):
        for i in range(5):
            obs = _make_observation()
            promote_from_observation(
                obs,
                task_signature=f"test.task_{i}",
                event_log=event_log,
                memory_store=memory_store,
            )

        assert memory_store.get_count() == 5

    def test_mixed_approved_and_rejected(self, event_log, memory_store):
        good_obs = _make_observation(confidence=0.8)
        bad_obs = _make_observation(confidence=0.01)

        r1 = promote_from_observation(
            good_obs,
            task_signature="good.task",
            event_log=event_log,
            memory_store=memory_store,
        )
        r2 = promote_from_observation(
            bad_obs,
            task_signature="bad.task",
            event_log=event_log,
            memory_store=memory_store,
        )

        assert r1.promoted
        assert r2.blocked
        assert memory_store.get_count() == 1
