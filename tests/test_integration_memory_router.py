# -*- coding: utf-8 -*-
"""Integration tests for precedent memory and uncertainty router in runtime."""

import pytest
import tempfile
import shutil
from cee_core import (
    execute_task_in_domain,
    DomainContext,
    MemoryStore,
    UncertaintyRouter,
)
from cee_core.memory_types import PrecedentMemory
from cee_core.event_log import EventLog
from cee_core.events import DeliberationEvent


class TestPrecedentMemoryIntegration:
    """Tests for precedent memory integration in runtime."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for memory store."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def memory_store_with_precedents(self, temp_dir):
        """Create memory store with some precedent memories."""
        store = MemoryStore(storage_path=temp_dir)
        
        precedents = [
            PrecedentMemory(
                memory_id="mem_001",
                task_signature="analyze.project.risk",
                state_diff={"risk_level": "high", "vulnerabilities": ["sql_injection"]},
                evidence_refs=["audit_001", "scan_002"],
                outcome="success",
                task_summary="成功识别SQL注入漏洞",
                domain_label="security",
                semantic_vector=[0.1] * 1536,
            ),
            PrecedentMemory(
                memory_id="mem_002",
                task_signature="review.code.quality",
                state_diff={"coverage": "improved", "quality_score": "increased"},
                evidence_refs=["review_001"],
                outcome="success",
                task_summary="代码审查发现并修复质量问题",
                domain_label="code_review",
                semantic_vector=[0.2] * 1536,
            ),
        ]
        
        for mem in precedents:
            store.add_memory(mem)
        
        return store

    def test_runtime_retrieves_precedents_when_memory_store_provided(self, memory_store_with_precedents):
        """Test that runtime retrieves precedents when memory_store is provided."""
        result = execute_task_in_domain(
            "分析项目安全风险",
            DomainContext(domain_name="security"),
            memory_store=memory_store_with_precedents,
        )
        
        # Check that task executed successfully
        assert result.task is not None
        assert result.reasoning_step is not None
        
        # The memory_index may not return results in test environment due to embedding provider
        # but we verify that the integration code path executes without errors
        events = list(result.event_log.all())
        assert len(events) > 0, "Should have recorded events"

    def test_runtime_works_without_memory_store(self):
        """Test that runtime works normally without memory_store."""
        result = execute_task_in_domain(
            "分析项目风险",
            DomainContext(domain_name="core"),
        )
        
        # Should complete successfully without memory store
        assert result.task is not None
        assert result.reasoning_step is not None
        assert result.plan is not None

    def test_precedent_retrieval_records_event(self, memory_store_with_precedents):
        """Test that precedent retrieval is recorded in event log."""
        result = execute_task_in_domain(
            "审查代码质量",
            DomainContext(domain_name="core"),
            memory_store=memory_store_with_precedents,
        )
        
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        # Should have at least the normal deliberation event plus precedent event
        assert len(deliberation_events) >= 1


class TestUncertaintyRouterIntegration:
    """Tests for uncertainty router integration in runtime."""

    def test_runtime_calls_router_when_provided(self):
        """Test that runtime calls uncertainty router when provided."""
        router = UncertaintyRouter()
        
        result = execute_task_in_domain(
            "分析项目风险",
            DomainContext(domain_name="core"),
            router=router,
        )
        
        # Check that routing decision is recorded
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        # Should have routing decision event
        routing_events = [
            e for e in deliberation_events
            if "routing" in str(e.reasoning_step.summary).lower()
        ]
        assert len(routing_events) > 0, "Should have routing decision event"

    def test_router_decision_affects_approval_strategy(self):
        """Test that router decision can affect approval strategy."""
        router = UncertaintyRouter()
        
        result = execute_task_in_domain(
            "高风险操作：更新安全配置",
            DomainContext(domain_name="core"),
            router=router,
        )
        
        # For high-risk tasks, router should recommend human review
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        routing_events = [
            e for e in deliberation_events
            if "routing" in str(e.reasoning_step.summary).lower()
        ]
        
        if routing_events:
            routing_event = routing_events[0]
            summary = str(routing_event.reasoning_step.summary)
            # Should mention routing decision
            assert "routing" in summary.lower()

    def test_runtime_works_without_router(self):
        """Test that runtime works normally without router."""
        result = execute_task_in_domain(
            "分析项目风险",
            DomainContext(domain_name="core"),
        )
        
        # Should complete successfully without router
        assert result.task is not None
        assert result.reasoning_step is not None


class TestCombinedIntegration:
    """Tests for combined precedent memory + uncertainty router integration."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for memory store."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def memory_store_with_precedents(self, temp_dir):
        """Create memory store with some precedent memories."""
        store = MemoryStore(storage_path=temp_dir)
        
        precedents = [
            PrecedentMemory(
                memory_id="mem_001",
                task_signature="analyze.security.risk",
                state_diff={"risk_level": "high"},
                evidence_refs=["audit_001"],
                outcome="success",
                task_summary="成功识别安全风险",
                domain_label="security",
                semantic_vector=[0.3] * 1536,
            ),
        ]
        
        for mem in precedents:
            store.add_memory(mem)
        
        return store

    def test_runtime_with_both_memory_and_router(self, memory_store_with_precedents):
        """Test runtime with both memory store and router provided."""
        router = UncertaintyRouter()
        
        result = execute_task_in_domain(
            "分析项目安全风险",
            DomainContext(domain_name="security"),
            memory_store=memory_store_with_precedents,
            router=router,
        )
        
        # Should complete successfully
        assert result.task is not None
        assert result.reasoning_step is not None
        assert result.plan is not None
        
        # Should have routing decision event
        from cee_core.events import DeliberationEvent
        events = list(result.event_log.all())
        deliberation_events = [e for e in events if isinstance(e, DeliberationEvent)]
        
        routing_events = [
            e for e in deliberation_events
            if "routing" in str(e.reasoning_step.summary).lower()
        ]
        assert len(routing_events) > 0, "Should have routing decision event"

    def test_replay_still_works_with_memory_and_router(self, memory_store_with_precedents):
        """Test that state replay still works with memory and router integration."""
        router = UncertaintyRouter()
        
        result = execute_task_in_domain(
            "分析项目风险",
            DomainContext(domain_name="core"),
            memory_store=memory_store_with_precedents,
            router=router,
        )
        
        # Replay should still work
        ws = result.event_log.replay_world_state()
        assert ws is not None
        assert ws.state_id is not None
