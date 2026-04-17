"""Tests for memory_types module."""

import pytest
import time
from dataclasses import FrozenInstanceError
from src.cee_core.memory_types import PrecedentMemory, MemoryRetrievalResult


class TestPrecedentMemory:
    """Tests for PrecedentMemory dataclass."""

    def test_create_memory_with_defaults(self):
        """Test creating a memory with default values."""
        memory = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1", "ev2"],
            outcome="success"
        )
        
        assert memory.memory_id.startswith("mem_")
        assert memory.task_signature == "test.task"
        assert memory.state_diff == {"key": "value"}
        assert memory.evidence_refs == ["ev1", "ev2"]
        assert memory.outcome == "success"
        assert memory.failure_mode is None
        assert memory.approval_result is None
        assert memory.semantic_vector is None
        assert memory.domain_label == "default"
        assert memory.task_summary == ""
        assert isinstance(memory.created_at, float)

    def test_create_memory_with_all_fields(self):
        """Test creating a memory with all fields specified."""
        memory = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1"],
            outcome="failure",
            memory_id="custom_mem_123",
            failure_mode="invalid_input",
            approval_result="rejected",
            semantic_vector=[0.1, 0.2, 0.3],
            domain_label="test_domain",
            task_summary="Test task summary",
            created_at=1234567890.0
        )
        
        assert memory.memory_id == "custom_mem_123"
        assert memory.outcome == "failure"
        assert memory.failure_mode == "invalid_input"
        assert memory.approval_result == "rejected"
        assert memory.semantic_vector == [0.1, 0.2, 0.3]
        assert memory.domain_label == "test_domain"
        assert memory.task_summary == "Test task summary"
        assert memory.created_at == 1234567890.0

    def test_memory_immutability(self):
        """Test that PrecedentMemory is immutable (frozen dataclass)."""
        memory = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1"],
            outcome="success"
        )
        
        with pytest.raises(FrozenInstanceError):
            memory.task_signature = "modified"

    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value", "number": 42},
            evidence_refs=["ev1", "ev2", "ev3"],
            outcome="partial_success",
            memory_id="test_mem_001",
            failure_mode=None,
            approval_result="auto_approved",
            semantic_vector=[0.5, 0.6, 0.7],
            domain_label="test",
            task_summary="Test summary",
            created_at=987654321.0
        )
        
        # Convert to dict
        mem_dict = original.to_dict()
        
        assert mem_dict["memory_id"] == "test_mem_001"
        assert mem_dict["task_signature"] == "test.task"
        assert mem_dict["state_diff"] == {"key": "value", "number": 42}
        assert mem_dict["evidence_refs"] == ["ev1", "ev2", "ev3"]
        assert mem_dict["outcome"] == "partial_success"
        
        # Convert back from dict
        restored = PrecedentMemory.from_dict(mem_dict)
        
        assert restored.memory_id == original.memory_id
        assert restored.task_signature == original.task_signature
        assert restored.state_diff == original.state_diff
        assert restored.evidence_refs == original.evidence_refs
        assert restored.outcome == original.outcome
        assert restored.failure_mode == original.failure_mode
        assert restored.approval_result == original.approval_result
        assert restored.semantic_vector == original.semantic_vector
        assert restored.domain_label == original.domain_label
        assert restored.task_summary == original.task_summary
        assert restored.created_at == original.created_at

    def test_from_dict_with_missing_fields(self):
        """Test from_dict with minimal required fields."""
        minimal_dict = {
            "task_signature": "minimal.task",
            "state_diff": {},
            "evidence_refs": [],
            "outcome": "success"
        }
        
        memory = PrecedentMemory.from_dict(minimal_dict)
        
        assert memory.task_signature == "minimal.task"
        assert memory.state_diff == {}
        assert memory.evidence_refs == []
        assert memory.outcome == "success"
        assert memory.memory_id.startswith("mem_")
        assert memory.domain_label == "default"
        assert memory.task_summary == ""


class TestMemoryRetrievalResult:
    """Tests for MemoryRetrievalResult dataclass."""

    def test_create_retrieval_result(self):
        """Test creating a retrieval result."""
        memory = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1"],
            outcome="success"
        )
        
        result = MemoryRetrievalResult(
            memory=memory,
            relevance_score=0.85,
            match_reason="Matched task signature"
        )
        
        assert result.memory == memory
        assert result.relevance_score == 0.85
        assert result.match_reason == "Matched task signature"

    def test_retrieval_result_immutability(self):
        """Test that MemoryRetrievalResult is immutable."""
        memory = PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1"],
            outcome="success"
        )
        result = MemoryRetrievalResult(
            memory=memory,
            relevance_score=0.85
        )
        
        with pytest.raises(FrozenInstanceError):
            result.relevance_score = 0.9

    def test_to_dict(self):
        """Test converting retrieval result to dict."""
        memory = PrecedentMemory(
            memory_id="test_mem_002",
            task_signature="test.task",
            state_diff={"key": "value"},
            evidence_refs=["ev1"],
            outcome="success",
            created_at=1234567890.0
        )
        
        result = MemoryRetrievalResult(
            memory=memory,
            relevance_score=0.92,
            match_reason="Perfect match"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["memory"]["memory_id"] == "test_mem_002"
        assert result_dict["relevance_score"] == 0.92
        assert result_dict["match_reason"] == "Perfect match"
