"""Tests for LLM-driven deliberation adapter."""

import json

import pytest

from cee_core.llm_deliberation import (
    ProviderBackedDeliberationCompiler,
    StaticLLMDeliberationCompiler,
    deliberate_chain_with_llm,
    deliberate_with_llm,
    parse_llm_deliberation_response,
)
from cee_core.tasks import TaskSpec
from cee_core.event_log import EventLog
from cee_core.tools import ToolRegistry


def _make_task(**overrides):
    defaults = dict(
        objective="analyze the codebase for potential issues",
        kind="analysis",
        risk_level="low",
        task_level="L1",
        success_criteria=("identified issues",),
        requested_primitives=("observe", "interpret"),
    )
    defaults.update(overrides)
    return TaskSpec(**defaults)


class TestParseLLMDeliberationResponse:
    def test_parse_valid_deliberation_response(self):
        response = json.dumps({
            "summary": "Task needs planning",
            "hypothesis": "Low risk analysis task",
            "missing_information": ["external docs"],
            "candidate_actions": ["propose_plan", "request_read_tool"],
            "chosen_action": "propose_plan",
            "rationale": "Task is structured enough to plan directly",
            "stop_condition": "Terminal: plan proposed",
        })
        task = _make_task()

        step = parse_llm_deliberation_response(response, task)

        assert step.chosen_action == "propose_plan"
        assert step.task_id == task.task_id
        assert "external docs" in step.missing_information

    def test_parse_rejects_invalid_action(self):
        response = json.dumps({
            "summary": "test",
            "hypothesis": "test",
            "missing_information": [],
            "candidate_actions": ["execute_tool"],
            "chosen_action": "execute_tool",
            "rationale": "test",
            "stop_condition": "test",
        })
        task = _make_task()

        with pytest.raises(ValueError, match="chosen_action must be one of"):
            parse_llm_deliberation_response(response, task)

    def test_parse_handles_missing_fields(self):
        response = json.dumps({"chosen_action": "propose_plan"})
        task = _make_task()

        step = parse_llm_deliberation_response(response, task)

        assert step.chosen_action == "propose_plan"
        assert step.summary == ""
        assert step.missing_information == ()

    def test_parse_rejects_non_object_json(self):
        response = json.dumps(["propose_plan"])
        task = _make_task()

        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_llm_deliberation_response(response, task)

    def test_parse_rejects_invalid_json(self):
        response = "not json"
        task = _make_task()

        with pytest.raises(ValueError, match="invalid JSON"):
            parse_llm_deliberation_response(response, task)


class TestStaticLLMDeliberationCompiler:
    def test_static_compiler_returns_fixed_response(self):
        response_json = json.dumps({
            "chosen_action": "request_approval",
            "summary": "needs approval",
            "hypothesis": "test",
            "missing_information": [],
            "candidate_actions": ["request_approval"],
            "rationale": "test",
            "stop_condition": "test",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response_json)
        task = _make_task()

        result = compiler.deliberate(task, context="")

        assert result == response_json


class TestDeliberateWithLLM:
    def test_llm_deliberation_with_static_compiler(self):
        response_json = json.dumps({
            "chosen_action": "propose_plan",
            "summary": "proceed to plan",
            "hypothesis": "task is structured",
            "missing_information": [],
            "candidate_actions": ["propose_plan"],
            "rationale": "task has enough structure",
            "stop_condition": "plan proposed",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response_json)
        task = _make_task()

        step = deliberate_with_llm(task, compiler)

        assert step.chosen_action == "propose_plan"

    def test_llm_deliberation_fallback_on_failure(self):
        class FailingCompiler:
            def deliberate(self, task, context):
                raise RuntimeError("LLM failed")

        compiler = FailingCompiler()
        task = _make_task()

        step = deliberate_with_llm(task, compiler, fallback_to_deterministic=True)

        assert step is not None
        assert step.chosen_action is not None

    def test_llm_deliberation_raises_on_failure_without_fallback(self):
        class FailingCompiler:
            def deliberate(self, task, context):
                raise RuntimeError("LLM failed")

        compiler = FailingCompiler()
        task = _make_task()

        with pytest.raises(RuntimeError, match="LLM failed"):
            deliberate_with_llm(task, compiler, fallback_to_deterministic=False)


class TestDeliberateChainWithLLM:
    def test_chain_terminates_on_terminal_action(self):
        response_json = json.dumps({
            "chosen_action": "propose_plan",
            "summary": "final step",
            "hypothesis": "test",
            "missing_information": [],
            "candidate_actions": ["propose_plan"],
            "rationale": "test",
            "stop_condition": "terminal",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response_json)
        task = _make_task()

        chain = deliberate_chain_with_llm(task, compiler, max_steps=5)

        assert chain.step_count == 1
        assert chain.is_terminal
        assert chain.final_action == "propose_plan"

    def test_chain_respects_max_steps(self):
        response_json = json.dumps({
            "chosen_action": "request_read_tool",
            "summary": "needs docs",
            "hypothesis": "test",
            "missing_information": [],
            "candidate_actions": ["request_read_tool"],
            "rationale": "test",
            "stop_condition": "not terminal",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response_json)
        task = _make_task()

        chain = deliberate_chain_with_llm(task, compiler, max_steps=3)

        assert chain.step_count == 4
        assert chain.steps[-1].chosen_action == "propose_plan"

    def test_chain_with_tool_registry(self):
        response_json = json.dumps({
            "chosen_action": "request_read_tool",
            "summary": "requesting docs",
            "hypothesis": "needs external docs",
            "missing_information": [],
            "candidate_actions": ["request_read_tool"],
            "rationale": "task needs documentation",
            "stop_condition": "read tool requested",
        })
        compiler = StaticLLMDeliberationCompiler(response_json=response_json)
        task = _make_task()
        registry = ToolRegistry()
        from cee_core.tools import ToolSpec
        registry._tools["read_docs"] = ToolSpec(
            name="read_docs",
            description="Read documentation",
            risk="read",
        )

        chain = deliberate_chain_with_llm(task, compiler, tool_registry=registry, max_steps=2)

        assert chain.step_count >= 1


class TestProviderBackedDeliberationCompiler:
    def test_provider_backed_compiler_records_events(self):
        from cee_core.llm_provider import StaticLLMProvider

        provider = StaticLLMProvider(
            response_text=json.dumps({
                "chosen_action": "propose_plan",
                "summary": "plan needed",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "rationale": "test",
                "stop_condition": "done",
            })
        )
        log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=log)
        task = _make_task()

        response = compiler.deliberate(task, context="")

        step = parse_llm_deliberation_response(response, task)
        assert step.chosen_action == "propose_plan"

        events = log.all()
        assert any(e.event_type == "llm.deliberation.requested" for e in events)
        assert any(e.event_type == "llm.deliberation.succeeded" for e in events)

    def test_provider_backed_compiler_records_failure_events(self):
        from cee_core.llm_provider import FailingLLMProvider

        provider = FailingLLMProvider(kind="provider_error", message="test failure")
        log = EventLog()
        compiler = ProviderBackedDeliberationCompiler(provider=provider, event_log=log)
        task = _make_task()

        with pytest.raises(RuntimeError):
            compiler.deliberate(task, context="")

        events = log.all()
        assert any(e.event_type == "llm.deliberation.requested" for e in events)
        assert any(e.event_type == "llm.deliberation.failed" for e in events)
