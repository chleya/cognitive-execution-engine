"""Tests for real tool execution framework."""

import pytest

from cee_core.tool_executor import (
    DefaultToolSandbox,
    SandboxedToolExecutor,
    ToolExecutionContext,
    ToolExecutionResult,
)
from cee_core.tools import ToolRegistry, ToolSpec
from cee_core.event_log import EventLog
from cee_core.tool_runner import ReadToolHandler


class TestToolExecutionContext:
    def test_context_creation(self):
        ctx = ToolExecutionContext(
            tool_name="test_tool",
            arguments={"key": "value"},
            call_id="call_123",
        )

        assert ctx.tool_name == "test_tool"
        assert ctx.arguments == {"key": "value"}
        assert ctx.call_id == "call_123"
        assert ctx.request_id == "exec_call_123"

    def test_default_timeout(self):
        ctx = ToolExecutionContext(
            tool_name="test",
            arguments={},
            call_id="call_1",
        )

        assert ctx.timeout_seconds == 30.0
        assert ctx.max_output_size == 100000


class TestToolExecutionResult:
    def test_result_to_event(self):
        result = ToolExecutionResult(
            tool_name="test_tool",
            call_id="call_123",
            status="succeeded",
            result={"data": "test"},
        )

        event = result.to_event()

        assert event.call_id == "call_123"
        assert event.tool_name == "test_tool"
        assert event.status == "succeeded"
        assert event.result == {"data": "test"}

    def test_failed_result(self):
        result = ToolExecutionResult(
            tool_name="test_tool",
            call_id="call_123",
            status="failed",
            error_message="something went wrong",
        )

        event = result.to_event()

        assert event.status == "failed"
        assert event.error_message == "something went wrong"


class TestDefaultToolSandbox:
    def test_successful_execution(self):
        sandbox = DefaultToolSandbox()

        def handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result="test output",
            )

        ctx = ToolExecutionContext(
            tool_name="test_tool",
            arguments={},
            call_id="call_1",
        )

        result = sandbox.execute(handler, ctx)

        assert result.status == "succeeded"
        assert result.result == "test output"
        assert result.execution_time_ms >= 0

    def test_exception_handling(self):
        sandbox = DefaultToolSandbox()

        def handler(ctx):
            raise RuntimeError("test error")

        ctx = ToolExecutionContext(
            tool_name="test_tool",
            arguments={},
            call_id="call_1",
        )

        result = sandbox.execute(handler, ctx)

        assert result.status == "failed"
        assert "test error" in result.error_message
        assert result.execution_time_ms >= 0

    def test_output_truncation(self):
        sandbox = DefaultToolSandbox(max_output_size=10)

        def handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result="a" * 100,
            )

        ctx = ToolExecutionContext(
            tool_name="test_tool",
            arguments={},
            call_id="call_1",
            max_output_size=10,
        )

        result = sandbox.execute(handler, ctx)

        assert result.status == "succeeded"
        assert result.result.endswith("...[truncated]")
        assert result.metadata.get("truncated") is True


class TestSandboxedToolExecutor:
    def test_register_and_execute_read_handler(self):
        registry = ToolRegistry()
        registry._tools["read_data"] = ToolSpec(
            name="read_data",
            description="Read data",
            risk="read",
        )

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_read_handler("read_data", lambda args: {"data": "test"})

        from cee_core.tools import ToolCallSpec
        call = ToolCallSpec(
            tool_name="read_data",
            arguments={},
        )

        event = executor.execute(call)

        assert event.status == "succeeded"
        assert event.result == {"data": "test"}

    def test_register_handler_for_unknown_tool_raises(self):
        registry = ToolRegistry()
        executor = SandboxedToolExecutor(registry=registry)

        def handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result="test",
            )

        with pytest.raises(ValueError, match="unknown tool"):
            executor.register_handler("nonexistent", handler)

    def test_execute_unknown_tool_fails(self):
        registry = ToolRegistry()
        executor = SandboxedToolExecutor(registry=registry)

        from cee_core.tools import ToolCallSpec
        call = ToolCallSpec(
            tool_name="nonexistent",
            arguments={},
        )

        event = executor.execute(call)

        assert event.status == "failed"
        assert "policy blocked" in event.error_message or "no handler" in event.error_message

    def test_execute_records_events(self):
        registry = ToolRegistry()
        registry._tools["test_tool"] = ToolSpec(
            name="test_tool",
            description="Test",
            risk="read",
        )

        log = EventLog()
        executor = SandboxedToolExecutor(registry=registry, event_log=log)
        executor.register_read_handler("test_tool", lambda args: "success")

        from cee_core.tools import ToolCallSpec
        call = ToolCallSpec(
            tool_name="test_tool",
            arguments={},
        )

        executor.execute(call)

        events = log.all()
        assert any(e.event_type == "tool.execution.policy_evaluated" for e in events)
        assert any(e.event_type == "tool.execution.started" for e in events)
        assert any(e.event_type == "tool.execution.completed" for e in events)

    def test_policy_blocked_execution(self):
        registry = ToolRegistry()
        registry._tools["write_tool"] = ToolSpec(
            name="write_tool",
            description="Write",
            risk="write",
        )

        executor = SandboxedToolExecutor(registry=registry)

        from cee_core.tools import ToolCallSpec
        call = ToolCallSpec(
            tool_name="write_tool",
            arguments={},
        )

        event = executor.execute(call)

        assert event.status == "failed"
        assert "policy blocked" in event.error_message


class TestDocumentAnalysisTools:
    def test_analyze_document_success(self):
        from cee_core.domains.document_tools import handle_analyze_document

        ctx = ToolExecutionContext(
            tool_name="analyze_document",
            arguments={
                "content": "This is a test document. It has multiple sentences. Some keywords are important.",
                "top_k": 5,
            },
            call_id="call_1",
        )

        result = handle_analyze_document(ctx)

        assert result.status == "succeeded"
        assert "keywords" in result.result
        assert "readability" in result.result
        assert result.result["char_count"] > 0

    def test_analyze_document_empty_content(self):
        from cee_core.domains.document_tools import handle_analyze_document

        ctx = ToolExecutionContext(
            tool_name="analyze_document",
            arguments={"content": ""},
            call_id="call_1",
        )

        result = handle_analyze_document(ctx)

        assert result.status == "failed"
        assert "required" in result.error_message.lower()

    def test_search_document_success(self):
        from cee_core.domains.document_tools import handle_search_document

        ctx = ToolExecutionContext(
            tool_name="search_document",
            arguments={
                "content": "The quick brown fox jumps over the lazy dog.",
                "query": "fox",
            },
            call_id="call_1",
        )

        result = handle_search_document(ctx)

        assert result.status == "succeeded"
        assert result.result["match_count"] == 1

    def test_summarize_document_success(self):
        from cee_core.domains.document_tools import handle_summarize_document

        content = "First sentence here. Second sentence there. Third sentence everywhere. Fourth is boring. Fifth is cool."
        ctx = ToolExecutionContext(
            tool_name="summarize_document",
            arguments={
                "content": content,
                "max_sentences": 2,
            },
            call_id="call_1",
        )

        result = handle_summarize_document(ctx)

        assert result.status == "succeeded"
        assert "summary" in result.result
        assert "compression_ratio" in result.result


class TestCodeAnalysisTools:
    def test_analyze_code_success(self):
        from cee_core.domains.code_tools import handle_analyze_code

        code = """
def add(a, b):
    return a + b

def multiply(a, b):
    result = a * b
    if result > 100:
        print("large result")
    return result
"""
        ctx = ToolExecutionContext(
            tool_name="analyze_code",
            arguments={"code": code},
            call_id="call_1",
        )

        result = handle_analyze_code(ctx)

        assert result.status == "succeeded"
        assert "complexity_metrics" in result.result
        assert "issues" in result.result
        assert "issue_summary" in result.result

    def test_analyze_code_empty(self):
        from cee_core.domains.code_tools import handle_analyze_code

        ctx = ToolExecutionContext(
            tool_name="analyze_code",
            arguments={"code": ""},
            call_id="call_1",
        )

        result = handle_analyze_code(ctx)

        assert result.status == "failed"

    def test_check_code_style_success(self):
        from cee_core.domains.code_tools import handle_check_code_style

        code = "def good_code():\n    return True\n"
        ctx = ToolExecutionContext(
            tool_name="check_code_style",
            arguments={"code": code},
            call_id="call_1",
        )

        result = handle_check_code_style(ctx)

        assert result.status == "succeeded"
        assert "style_issues" in result.result

    def test_find_code_patterns_success(self):
        from cee_core.domains.code_tools import handle_find_code_patterns

        code = "import os\nimport sys\nfrom pathlib import Path"
        ctx = ToolExecutionContext(
            tool_name="find_code_patterns",
            arguments={
                "code": code,
                "pattern": r"import\s+\w+",
            },
            call_id="call_1",
        )

        result = handle_find_code_patterns(ctx)

        assert result.status == "succeeded"
        assert result.result["match_count"] >= 2

    def test_find_code_patterns_invalid_regex(self):
        from cee_core.domains.code_tools import handle_find_code_patterns

        ctx = ToolExecutionContext(
            tool_name="find_code_patterns",
            arguments={
                "code": "test",
                "pattern": "[invalid",
            },
            call_id="call_1",
        )

        result = handle_find_code_patterns(ctx)

        assert result.status == "failed"
        assert "Invalid regex" in result.error_message
