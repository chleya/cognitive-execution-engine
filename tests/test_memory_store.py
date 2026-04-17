"""Tests for memory_store module."""

import pytest
import json
import os
import tempfile
import shutil
from pathlib import Path
from src.cee_core.memory_store import MemoryStore
from src.cee_core.memory_types import PrecedentMemory
from src.cee_core.retrieval_types import RetrievalQuery


class TestMemoryStore:
    """Tests for MemoryStore class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def sample_memory(self):
        """Create a sample memory for testing."""
        return PrecedentMemory(
            task_signature="test.task",
            state_diff={"key": "value", "count": 42},
            evidence_refs=["ev_001", "ev_002"],
            outcome="success",
            task_summary="Test task that succeeded"
        )

    def test_initialize_store_default_path(self, temp_dir):
        """Test initializing store with default path."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            store = MemoryStore()
            assert store.storage_path == Path(temp_dir) / "memory_store"
            assert store.storage_path.exists()
        finally:
            os.chdir(original_cwd)

    def test_initialize_store_custom_path(self, temp_dir):
        """Test initializing store with custom path."""
        custom_path = Path(temp_dir) / "custom_memory"
        store = MemoryStore(storage_path=str(custom_path))
        
        assert store.storage_path == custom_path
        assert custom_path.exists()

    def test_add_and_get_memory(self, temp_dir, sample_memory):
        """Test adding a memory and retrieving it."""
        store = MemoryStore(storage_path=temp_dir)
        
        mem_id = store.add_memory(sample_memory)
        assert mem_id == sample_memory.memory_id
        
        retrieved = store.get_memory(mem_id)
        assert retrieved is not None
        assert retrieved.memory_id == sample_memory.memory_id
        assert retrieved.task_signature == "test.task"
        assert retrieved.state_diff == {"key": "value", "count": 42}

    def test_get_nonexistent_memory(self, temp_dir):
        """Test getting a memory that doesn't exist."""
        store = MemoryStore(storage_path=temp_dir)
        assert store.get_memory("nonexistent") is None

    def test_delete_memory(self, temp_dir, sample_memory):
        """Test deleting a memory."""
        store = MemoryStore(storage_path=temp_dir)
        mem_id = store.add_memory(sample_memory)
        
        assert store.get_memory(mem_id) is not None
        
        result = store.delete_memory(mem_id)
        assert result is True
        assert store.get_memory(mem_id) is None
        
        mem_file = Path(temp_dir) / f"{mem_id}.json"
        assert not mem_file.exists()

    def test_delete_nonexistent_memory(self, temp_dir):
        """Test deleting a memory that doesn't exist."""
        store = MemoryStore(storage_path=temp_dir)
        result = store.delete_memory("nonexistent")
        assert result is False

    def test_list_memories(self, temp_dir):
        """Test listing memories with filters."""
        store = MemoryStore(storage_path=temp_dir)
        
        mem1 = PrecedentMemory(
            task_signature="task.a",
            state_diff={},
            evidence_refs=[],
            outcome="success",
            domain_label="domain1",
            task_summary="Task A in domain 1"
        )
        mem2 = PrecedentMemory(
            task_signature="task.b",
            state_diff={},
            evidence_refs=[],
            outcome="failure",
            domain_label="domain1",
            task_summary="Task B in domain 1"
        )
        mem3 = PrecedentMemory(
            task_signature="task.a",
            state_diff={},
            evidence_refs=[],
            outcome="success",
            domain_label="domain2",
            task_summary="Task A in domain 2"
        )
        
        store.add_memory(mem1)
        store.add_memory(mem2)
        store.add_memory(mem3)
        
        all_memories = store.list_memories(limit=100)
        assert len(all_memories) == 3
        
        domain1_memories = store.list_memories(domain_label="domain1")
        assert len(domain1_memories) == 2
        
        task_a_memories = store.list_memories(task_signature="task.a")
        assert len(task_a_memories) == 2
        
        success_memories = store.list_memories(outcome="success")
        assert len(success_memories) == 2

    def test_list_memories_pagination(self, temp_dir):
        """Test listing memories with pagination."""
        store = MemoryStore(storage_path=temp_dir)
        
        for i in range(15):
            mem = PrecedentMemory(
                task_signature=f"task.{i}",
                state_diff={},
                evidence_refs=[],
                outcome="success"
            )
            store.add_memory(mem)
        
        page1 = store.list_memories(limit=5, offset=0)
        assert len(page1) == 5
        
        page2 = store.list_memories(limit=5, offset=5)
        assert len(page2) == 5
        
        page3 = store.list_memories(limit=5, offset=10)
        assert len(page3) == 5

    def test_search_memories(self, temp_dir):
        """Test searching memories by keyword."""
        store = MemoryStore(storage_path=temp_dir)
        
        mem1 = PrecedentMemory(
            task_signature="document_analysis",
            state_diff={"result": "analyzed"},
            evidence_refs=[],
            outcome="success",
            task_summary="Analyzed a PDF document with text extraction"
        )
        mem2 = PrecedentMemory(
            task_signature="code_review",
            state_diff={"result": "reviewed"},
            evidence_refs=[],
            outcome="failure",
            task_summary="Reviewed Python code and found bugs"
        )
        
        store.add_memory(mem1)
        store.add_memory(mem2)
        
        query = RetrievalQuery(
            query_text="document",
            limit=10,
            min_relevance=0.0
        )
        
        results = store.search_memories(query)
        assert len(results) >= 1
        assert any(r.memory.memory_id == mem1.memory_id for r in results)

    def test_get_count(self, temp_dir, sample_memory):
        """Test getting memory count."""
        store = MemoryStore(storage_path=temp_dir)
        assert store.get_count() == 0
        
        store.add_memory(sample_memory)
        assert store.get_count() == 1

    def test_persistence_across_instances(self, temp_dir, sample_memory):
        """Test that memories persist across store instances."""
        store1 = MemoryStore(storage_path=temp_dir)
        mem_id = store1.add_memory(sample_memory)
        
        store2 = MemoryStore(storage_path=temp_dir)
        retrieved = store2.get_memory(mem_id)
        
        assert retrieved is not None
        assert retrieved.memory_id == mem_id

    def test_cleanup_old_memories(self, temp_dir):
        """Test cleaning up old memories."""
        store = MemoryStore(storage_path=temp_dir)
        
        from datetime import datetime, timedelta, UTC
        import time
        
        old_time = (datetime.now(UTC) - timedelta(days=400)).timestamp()
        new_time = datetime.now(UTC).timestamp()
        
        old_mem = PrecedentMemory(
            task_signature="old.task",
            state_diff={},
            evidence_refs=[],
            outcome="success",
            memory_id="old_mem",
            created_at=old_time
        )
        new_mem = PrecedentMemory(
            task_signature="new.task",
            state_diff={},
            evidence_refs=[],
            outcome="success",
            memory_id="new_mem",
            created_at=new_time
        )
        
        store.add_memory(old_mem)
        store.add_memory(new_mem)
        
        assert store.get_count() == 2
        
        deleted = store.cleanup_old_memories(days_to_keep=365)
        assert deleted == 1
        
        assert store.get_memory("old_mem") is None
        assert store.get_memory("new_mem") is not None
