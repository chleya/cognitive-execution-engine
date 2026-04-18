"""End-to-end integration test for tool execution with LLM deliberation.

Demonstrates the full flow:
1. LLM deliberation decides which tool to use
2. Sandboxed tool executor runs the actual tool
3. Results are promoted to beliefs and audited
"""

import json
import pytest

from cee_core import (
    StaticLLMDeliberationCompiler,
    deliberate_with_llm,
    SandboxedToolExecutor,
    ToolExecutionContext,
    ToolExecutionResult,
)
from cee_core.event_log import EventLog
from cee_core.tasks import TaskSpec
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec
from cee_core.tool_observation_flow import (
    run_read_only_tool_observation_flow,
    ToolObservationFlowResult,
)
from cee_core.domain_context import DomainContext


def _make_task(**overrides):
    defaults = dict(
        objective="analyze this document for key insights",
        kind="analysis",
        risk_level="low",
        task_level="L1",
        success_criteria=("analysis complete",),
        requested_primitives=("observe", "interpret"),
    )
    defaults.update(overrides)
    return TaskSpec(**defaults)


class TestEndToEndToolExecution:
    """End-to-end tests demonstrating LLM + tool execution integration."""

    def test_llm_deliberation_to_tool_execution_flow(self):
        """Test LLM deliberation decides to use a tool, then execute it."""
        response = json.dumps({
            "summary": "Task needs document analysis",
            "hypothesis": "Document analysis required",
            "missing_information": ["document content"],
            "candidate_actions": ["request_read_tool"],
            "chosen_action": "request_read_tool",
            "rationale": "Task asks for document analysis",
            "stop_condition": "Tool execution needed",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response)
        task = _make_task()

        step = deliberate_with_llm(task, compiler)

        assert step.chosen_action == "request_read_tool"
        assert "document" in step.hypothesis.lower()

    def test_full_tool_execution_with_audit_trail(self):
        """Test complete tool execution with full audit trail."""
        registry = ToolRegistry()
        registry._tools["analyze_document"] = ToolSpec(
            name="analyze_document",
            description="Analyze document content",
            risk="read",
        )

        from cee_core.domains.document_tools import handle_analyze_document
        from cee_core.tool_runner import InMemoryReadOnlyToolRunner

        runner = InMemoryReadOnlyToolRunner(registry=registry)
        runner.register_handler("analyze_document", lambda args: {
            "keywords": ["test", "document"],
            "analysis": "simple test",
        })

        log = EventLog()
        call = ToolCallSpec(
            tool_name="analyze_document",
            arguments={"content": "This is a test document with important keywords."},
        )

        result = run_read_only_tool_observation_flow(
            call,
            runner,
            event_log=log,
            promote_to_belief_key="document.analysis_result",
            domain_context=DomainContext(domain_name="document_analysis"),
        )

        assert result.tool_result_event.status == "succeeded"
        assert "keywords" in result.tool_result_event.result

        events = log.all()
        event_types = [e.event_type for e in events]
        assert "tool.call.proposed" in event_types
        assert "tool.call.result" in event_types

    def test_sandboxed_executor_with_real_document_tool(self):
        """Test sandboxed executor with real document analysis tool."""
        registry = ToolRegistry()
        registry._tools["analyze_document"] = ToolSpec(
            name="analyze_document",
            description="Analyze document",
            risk="read",
        )

        executor = SandboxedToolExecutor(registry=registry)

        from cee_core.domains.document_tools import handle_analyze_document
        executor.register_handler("analyze_document", handle_analyze_document)

        call = ToolCallSpec(
            tool_name="analyze_document",
            arguments={
                "content": "Python is a programming language. It supports multiple paradigms.",
                "top_k": 5,
            },
        )

        event = executor.execute(call)

        assert event.status == "succeeded"
        assert "keywords" in event.result
        assert "python" in event.result["keywords"]

    def test_sandboxed_executor_with_real_code_tool(self):
        """Test sandboxed executor with real code analysis tool."""
        registry = ToolRegistry()
        registry._tools["analyze_code"] = ToolSpec(
            name="analyze_code",
            description="Analyze code",
            risk="read",
        )

        executor = SandboxedToolExecutor(registry=registry)

        from cee_core.domains.code_tools import handle_analyze_code
        executor.register_handler("analyze_code", handle_analyze_code)

        call = ToolCallSpec(
            tool_name="analyze_code",
            arguments={
                "code": """
def calculate_sum(numbers):
    \"\"\"Calculate the sum of numbers.\"\"\"
    total = 0
    for n in numbers:
        total += n
    return total
""",
            },
        )

        event = executor.execute(call)

        assert event.status == "succeeded"
        assert "complexity_metrics" in event.result
        assert event.result["complexity_metrics"]["function_count"] == 1

    def test_tool_execution_timeout_simulation(self):
        """Test that slow tools are handled correctly."""
        import time
        registry = ToolRegistry()
        registry._tools["slow_tool"] = ToolSpec(
            name="slow_tool",
            description="A slow tool",
            risk="read",
        )

        def slow_handler(ctx):
            time.sleep(0.1)
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result="done",
            )

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_handler("slow_tool", slow_handler)

        call = ToolCallSpec(
            tool_name="slow_tool",
            arguments={},
        )

        event = executor.execute(call)

        assert event.status == "succeeded"
        assert event.result == "done"

    def test_tool_execution_with_error_propagation(self):
        """Test that tool errors are properly captured and audited."""
        registry = ToolRegistry()
        registry._tools["failing_tool"] = ToolSpec(
            name="failing_tool",
            description="A tool that always fails",
            risk="read",
        )

        def failing_handler(ctx):
            raise ValueError("This tool intentionally fails")

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_handler("failing_tool", failing_handler)

        call = ToolCallSpec(
            tool_name="failing_tool",
            arguments={},
        )

        event = executor.execute(call)

        assert event.status == "failed"
        assert "intentionally fails" in event.error_message


class TestToolExecutionOrchestration:
    """Test orchestration of multiple tools in sequence."""

    def test_chain_document_analysis_then_code_review(self):
        """Test running document analysis followed by code review."""
        registry = ToolRegistry()
        registry._tools["analyze_document"] = ToolSpec(
            name="analyze_document",
            description="Analyze document",
            risk="read",
        )
        registry._tools["analyze_code"] = ToolSpec(
            name="analyze_code",
            description="Analyze code",
            risk="read",
        )

        executor = SandboxedToolExecutor(registry=registry)

        from cee_core.domains.document_tools import handle_analyze_document
        from cee_core.domains.code_tools import handle_analyze_code
        executor.register_handler("analyze_document", handle_analyze_document)
        executor.register_handler("analyze_code", handle_analyze_code)

        doc_call = ToolCallSpec(
            tool_name="analyze_document",
            arguments={"content": "This is a requirements document."},
        )
        code_call = ToolCallSpec(
            tool_name="analyze_code",
            arguments={"code": "def foo(): pass"},
        )

        doc_result = executor.execute(doc_call)
        code_result = executor.execute(code_call)

        assert doc_result.status == "succeeded"
        assert code_result.status == "succeeded"
        assert "keywords" in doc_result.result
        assert "complexity_metrics" in code_result.result
