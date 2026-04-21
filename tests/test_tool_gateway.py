"""Tests for the Tool Gateway: bounded execution boundary."""

import pytest

from cee_core import (
    EventLog,
    RevisionDelta,
    ToolCallSpec,
    ToolGateway,
    ToolGatewayResult,
    ToolRegistry,
    ToolResultEvent,
    ToolSpec,
    build_tool_gateway,
)
from cee_core.tool_gateway import (
    ApprovalProvider,
    StaticApprovalProvider,
)


def _make_registry_with_read_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="read_docs",
        description="Read documents",
        risk="read",
    ))
    return registry


def _make_registry_with_write_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="write_file",
        description="Write a file",
        risk="write",
    ))
    return registry


def _make_registry_with_external_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="send_email",
        description="Send an email",
        risk="external_side_effect",
    ))
    return registry


class TestToolGatewayReadTool:
    def test_read_tool_allowed_by_policy(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert result.succeeded
        assert not result.blocked_by_policy
        assert result.commitment_event is not None
        assert result.tool_result is not None
        assert result.tool_result.status == "succeeded"

    def test_read_tool_records_commitment_event(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert result.commitment_event is not None
        assert result.commitment_event.commitment_kind == "tool_contact"
        assert result.commitment_event.action_summary == "read_docs"

    def test_read_tool_records_tool_result(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert result.tool_result is not None
        assert result.tool_result.status == "succeeded"
        assert result.tool_result.result == {"hits": 3}

    def test_read_tool_creates_observation(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert result.observation is not None
        assert result.observation.source_tool == "read_docs"

    def test_read_tool_promotes_observation_to_delta(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(
            call,
            event_log=log,
            promote_to_belief_key="tool.read_docs.result",
        )

        assert result.promotion_delta is not None
        assert result.promotion_delta.target_ref == "beliefs.tool.read_docs.result"
        assert result.revision_event is not None

    def test_read_tool_records_revision_event_on_promotion(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(
            call,
            event_log=log,
            promote_to_belief_key="tool.read_docs.result",
        )

        assert result.revision_event is not None
        assert result.revision_event.revision_kind == "expansion"
        assert len(result.revision_event.deltas) == 1


class TestToolGatewayWriteTool:
    def test_write_tool_requires_approval(self):
        registry = _make_registry_with_write_tool()
        gateway = build_tool_gateway(registry)
        log = EventLog()

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_approval
        assert not result.succeeded

    def test_write_tool_approved_with_provider(self):
        registry = _make_registry_with_write_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"write_file": lambda args: "ok"},
            approval_provider=StaticApprovalProvider(verdict=True),
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.succeeded
        assert result.commitment_event is not None

    def test_write_tool_denied_by_provider(self):
        registry = _make_registry_with_write_tool()
        gateway = build_tool_gateway(
            registry,
            approval_provider=StaticApprovalProvider(verdict=False),
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="write_file", arguments={"path": "/tmp/test"})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_approval
        assert not result.succeeded


class TestToolGatewayExternalTool:
    def test_external_tool_requires_approval(self):
        registry = _make_registry_with_external_tool()
        gateway = build_tool_gateway(registry)
        log = EventLog()

        call = ToolCallSpec(tool_name="send_email", arguments={"to": "test@test.com"})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_approval
        assert not result.succeeded

    def test_external_tool_approved_with_provider(self):
        registry = _make_registry_with_external_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"send_email": lambda args: "sent"},
            approval_provider=StaticApprovalProvider(verdict=True),
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="send_email", arguments={"to": "test@test.com"})
        result = gateway.execute(call, event_log=log)

        assert result.succeeded


class TestToolGatewayUnknownTool:
    def test_unknown_tool_denied_by_policy(self):
        registry = ToolRegistry()
        gateway = build_tool_gateway(registry)
        log = EventLog()

        call = ToolCallSpec(tool_name="nonexistent", arguments={})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_policy
        assert not result.succeeded
        assert "unknown tool" in result.tool_result.error_message


class TestToolGatewayHandlerErrors:
    def test_handler_exception_returns_failed_result(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: (_ for _ in ()).throw(RuntimeError("handler error"))},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert not result.succeeded
        assert result.tool_result.status == "failed"
        assert "handler error" in result.tool_result.error_message

    def test_no_handler_returns_failed_result(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(registry)
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        result = gateway.execute(call, event_log=log)

        assert not result.succeeded
        assert "no handler registered" in result.tool_result.error_message


class TestToolGatewayBatch:
    def test_execute_batch_multiple_calls(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="read_a", description="A", risk="read"))
        registry.register(ToolSpec(name="read_b", description="B", risk="read"))

        gateway = build_tool_gateway(
            registry,
            handlers={
                "read_a": lambda args: {"result": "a"},
                "read_b": lambda args: {"result": "b"},
            },
        )
        log = EventLog()

        calls = (
            ToolCallSpec(tool_name="read_a", arguments={}),
            ToolCallSpec(tool_name="read_b", arguments={}),
        )
        results = gateway.execute_batch(calls, event_log=log)

        assert len(results) == 2
        assert all(r.succeeded for r in results)

    def test_execute_batch_state_id_chaining(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 1}},
        )
        log = EventLog()

        calls = (
            ToolCallSpec(tool_name="read_docs", arguments={"q": "1"}, call_id="c1"),
            ToolCallSpec(tool_name="read_docs", arguments={"q": "2"}, call_id="c2"),
        )
        results = gateway.execute_batch(
            calls,
            event_log=log,
            promote_to_belief_keys={"c1": "tool.docs.q1", "c2": "tool.docs.q2"},
        )

        assert len(results) == 2
        assert results[0].revision_event is not None
        assert results[0].revision_event.resulting_state_id == "ws_1"
        assert results[1].revision_event is not None
        assert results[1].revision_event.prior_state_id == "ws_1"
        assert results[1].revision_event.resulting_state_id == "ws_2"


class TestToolGatewayAuditTrail:
    def test_complete_audit_trail_for_read_tool(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: {"hits": 3}},
        )
        log = EventLog()

        call = ToolCallSpec(tool_name="read_docs", arguments={"query": "test"})
        gateway.execute(
            call,
            event_log=log,
            promote_to_belief_key="tool.read_docs.result",
        )

        events = list(log.all())
        commitment_events = log.commitment_events()
        revision_events = log.revision_events()

        assert len(commitment_events) == 1
        assert commitment_events[0].commitment_kind == "tool_contact"
        assert len(revision_events) == 1
        assert revision_events[0].revision_kind == "expansion"

    def test_denied_tool_still_records_result_event(self):
        registry = ToolRegistry()
        gateway = build_tool_gateway(registry)
        log = EventLog()

        call = ToolCallSpec(tool_name="nonexistent", arguments={})
        result = gateway.execute(call, event_log=log)

        assert result.blocked_by_policy
        assert result.tool_result is not None
        assert any(
            hasattr(e, "call_id") and getattr(e, "call_id", None) == call.call_id
            for e in log.all()
        )


class TestToolGatewayResult:
    def test_succeeded_property(self):
        result = ToolGatewayResult(
            call=ToolCallSpec(tool_name="t", arguments={}),
            policy_decision=None,
            commitment_event=None,
            tool_result=ToolResultEvent(
                call_id="c1", tool_name="t", status="succeeded", result="ok"
            ),
            observation=None,
            promotion_delta=None,
            revision_event=None,
        )
        assert result.succeeded

    def test_succeeded_property_failed(self):
        result = ToolGatewayResult(
            call=ToolCallSpec(tool_name="t", arguments={}),
            policy_decision=None,
            commitment_event=None,
            tool_result=ToolResultEvent(
                call_id="c1", tool_name="t", status="failed", error_message="err"
            ),
            observation=None,
            promotion_delta=None,
            revision_event=None,
        )
        assert not result.succeeded


class TestBuildToolGateway:
    def test_build_with_handlers(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(
            registry,
            handlers={"read_docs": lambda args: "ok"},
        )
        assert "read_docs" in gateway.handlers

    def test_build_with_approval_provider(self):
        registry = _make_registry_with_write_tool()
        gateway = build_tool_gateway(
            registry,
            approval_provider=StaticApprovalProvider(verdict=True),
        )
        assert gateway.approval_provider is not None

    def test_register_handler_for_unknown_tool_raises(self):
        registry = ToolRegistry()
        gateway = build_tool_gateway(registry)

        with pytest.raises(ValueError, match="unknown tool"):
            gateway.register_handler("nonexistent", lambda args: "ok")

    def test_register_duplicate_handler_raises(self):
        registry = _make_registry_with_read_tool()
        gateway = build_tool_gateway(registry)
        gateway.register_handler("read_docs", lambda args: "ok")

        with pytest.raises(ValueError, match="already registered"):
            gateway.register_handler("read_docs", lambda args: "ok2")
