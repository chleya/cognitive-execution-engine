"""Tests for approval_packet module."""

import pytest
import time
from cee_core.approval_packet import ApprovalPacket, ApprovalVerdict
from cee_core.world_schema import RevisionDelta
from cee_core.retriever import RetrievalResult


class TestApprovalVerdict:
    """Tests for ApprovalVerdict enum."""

    def test_verdict_values(self):
        """Test all verdict values exist."""
        assert ApprovalVerdict.APPROVED.value == "approved"
        assert ApprovalVerdict.REJECTED.value == "rejected"
        assert ApprovalVerdict.NEEDS_MORE_INFO.value == "needs_more_info"
        assert ApprovalVerdict.AUTO_APPROVED.value == "auto_approved"


class TestApprovalPacket:
    """Tests for ApprovalPacket dataclass."""

    @pytest.fixture
    def sample_packet(self):
        """Create a sample approval packet for testing."""
        return ApprovalPacket(
            original_task="Analyze document and extract key points",
            proposed_actions="Read file, parse content, extract summary",
            state_diff={"file_read": "document.txt", "summary_generated": True},
            deltas=[],
            evidence_used=[],
            precedent_summary=[],
            router_result=None,
            evidence_graph=None,
            risk_level="medium",
            reversible=True,
            rollback_instructions="Delete generated summary file"
        )

    def test_create_packet_with_defaults(self):
        """Test creating a packet with default values."""
        packet = ApprovalPacket(
            original_task="Test task",
            proposed_actions="Test actions",
            state_diff={},
            deltas=[],
            evidence_used=[],
            precedent_summary=[],
            router_result=None,
            evidence_graph=None,
            risk_level="low",
            reversible=False
        )

        assert packet.packet_id.startswith("approval_")
        assert packet.original_task == "Test task"
        assert packet.verdict is None
        assert packet.reviewer is None
        assert packet.reviewed_at is None
        assert isinstance(packet.created_at, float)

    def test_create_packet_with_all_fields(self):
        """Test creating a packet with all fields specified."""
        deltas = [RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="memory.test", before_summary="unknown", after_summary="value", justification="test", raw_value="value")]

        packet = ApprovalPacket(
            original_task="Custom task",
            proposed_actions="Custom actions",
            state_diff={"key": "value"},
            deltas=deltas,
            evidence_used=[],
            precedent_summary=[{"task": "prev_task", "outcome": "success"}],
            router_result=None,
            evidence_graph=None,
            risk_level="high",
            reversible=True,
            packet_id="custom_approval_001",
            created_at=1234567890.0,
            rollback_instructions="Undo everything",
            reviewer_notes="Looks okay",
            verdict=ApprovalVerdict.APPROVED,
            reviewed_at=987654321.0,
            reviewer="test_user"
        )

        assert packet.packet_id == "custom_approval_001"
        assert packet.created_at == 1234567890.0
        assert packet.verdict == ApprovalVerdict.APPROVED
        assert packet.reviewer == "test_user"
        assert packet.reviewed_at == 987654321.0

    def test_record_verdict(self, sample_packet):
        """Test recording a reviewer's verdict."""
        assert sample_packet.verdict is None
        assert not sample_packet.is_resolved

        sample_packet.record_verdict(
            verdict=ApprovalVerdict.APPROVED,
            reviewer="user_123",
            notes="Looks good!"
        )

        assert sample_packet.verdict == ApprovalVerdict.APPROVED
        assert sample_packet.reviewer == "user_123"
        assert sample_packet.reviewer_notes == "Looks good!"
        assert sample_packet.reviewed_at is not None
        assert sample_packet.is_resolved

    def test_is_approved_property(self, sample_packet):
        """Test is_approved property."""
        assert not sample_packet.is_approved

        sample_packet.record_verdict(ApprovalVerdict.APPROVED, "user")
        assert sample_packet.is_approved

        sample_packet.verdict = ApprovalVerdict.AUTO_APPROVED
        assert sample_packet.is_approved

        sample_packet.verdict = ApprovalVerdict.REJECTED
        assert not sample_packet.is_approved

    def test_is_resolved_property(self, sample_packet):
        """Test is_resolved property."""
        assert not sample_packet.is_resolved

        sample_packet.record_verdict(ApprovalVerdict.NEEDS_MORE_INFO, "user")
        assert sample_packet.is_resolved

    def test_to_dict(self, sample_packet):
        """Test converting packet to dictionary."""
        sample_packet.record_verdict(ApprovalVerdict.APPROVED, "user", "notes")

        packet_dict = sample_packet.to_dict()

        assert packet_dict["packet_id"] == sample_packet.packet_id
        assert packet_dict["original_task"] == sample_packet.original_task
        assert packet_dict["verdict"] == "approved"
        assert packet_dict["reviewer"] == "user"
        assert "deltas" in packet_dict

    def test_format_for_human_review(self, sample_packet):
        """Test formatting for human review."""
        formatted = sample_packet.format_for_human_review()

        assert "APPROVAL REQUEST" in formatted
        assert "Analyze document" in formatted
        assert "Risk Level" in formatted
        assert "Reversible" in formatted

    def test_format_for_human_review_with_verdict(self, sample_packet):
        """Test formatting with a recorded verdict."""
        sample_packet.record_verdict(ApprovalVerdict.REJECTED, "user", "Not safe")

        formatted = sample_packet.format_for_human_review()

        assert "Verdict: REJECTED" in formatted
        assert "Reviewed by: user" in formatted

    def test_format_for_human_review_truncated(self, sample_packet):
        """Test formatting with truncation."""
        sample_packet.original_task = "x" * 10000
        formatted = sample_packet.format_for_human_review(max_length=1000)

        assert len(formatted) <= 1500

    def test_format_with_evidence(self, sample_packet):
        """Test formatting with evidence."""
        from cee_core.retriever import RetrievalResult

        mock_evidence = RetrievalResult(
            content="Test evidence content",
            relevance_score=0.9,
            result_type="document_chunk",
            source_id="doc_001",
            metadata={}
        )
        sample_packet.evidence_used = [mock_evidence]

        formatted = sample_packet.format_for_human_review()

        assert "EVIDENCE USED" in formatted

    def test_format_with_precedents(self, sample_packet):
        """Test formatting with precedents."""
        sample_packet.precedent_summary = [
            {"task": "Task 1", "outcome": "success"},
            {"task": "Task 2", "outcome": "failure"}
        ]

        formatted = sample_packet.format_for_human_review()

        assert "PRECEDENTS" in formatted

    def test_format_with_rollback(self, sample_packet):
        """Test formatting with rollback instructions."""
        sample_packet.rollback_instructions = "Delete file X and restore from backup"

        formatted = sample_packet.format_for_human_review()

        assert "ROLLBACK INSTRUCTIONS" in formatted
        assert "Delete file X" in formatted

    def test_multiple_verdicts(self, sample_packet):
        """Test recording multiple verdicts (overwrites)."""
        sample_packet.record_verdict(ApprovalVerdict.NEEDS_MORE_INFO, "user1")
        assert sample_packet.verdict == ApprovalVerdict.NEEDS_MORE_INFO

        sample_packet.record_verdict(ApprovalVerdict.APPROVED, "user2")
        assert sample_packet.verdict == ApprovalVerdict.APPROVED
        assert sample_packet.reviewer == "user2"
