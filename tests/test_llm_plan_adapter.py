"""Tests for LLM-driven plan generation adapter."""

import json

import pytest

from cee_core.llm_plan_adapter import (
    ProviderBackedPlanCompiler,
    StaticLLMPlanCompiler,
    plan_with_llm,
    parse_llm_plan_response,
)
from cee_core.tasks import TaskSpec
from cee_core.event_log import EventLog
from cee_core.tools import ToolRegistry, ToolSpec


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


class TestParseLLMPlanResponse:
    def test_parse_valid_plan_response(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["task_1"]},
                {"section": "memory", "key": "working", "op": "append", "value": {"data": "test"}},
            ],
            "tool_calls": [
                {"tool_name": "read_docs", "arguments": {"query": "test"}},
            ],
            "rationale": "test plan",
        })
        task = _make_task()

        plan = parse_llm_plan_response(response, task)

        assert len(plan.candidate_patches) == 2
        assert len(plan.proposed_tool_calls) == 1
        assert plan.proposed_tool_calls[0].tool_name == "read_docs"

    def test_parse_rejects_invalid_patch_op(self):
        response = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "execute", "value": "test"},
            ],
        })
        task = _make_task()

        with pytest.raises(ValueError, match="Invalid patch op"):
            parse_llm_plan_response(response, task)

    def test_parse_handles_empty_tool_calls(self):
        response = json.dumps({
            "patches": [
                {"section": "beliefs", "key": "test", "op": "set", "value": "val"},
            ],
        })
        task = _make_task()

        plan = parse_llm_plan_response(response, task)

        assert len(plan.proposed_tool_calls) == 0

    def test_parse_rejects_non_object_json(self):
        response = json.dumps(["test"])
        task = _make_task()

        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_llm_plan_response(response, task)

    def test_parse_rejects_invalid_json(self):
        response = "not json"
        task = _make_task()

        with pytest.raises(ValueError, match="invalid JSON"):
            parse_llm_plan_response(response, task)


class TestStaticLLMPlanCompiler:
    def test_static_compiler_returns_fixed_response(self):
        response_json = json.dumps({
            "patches": [{"section": "goals", "key": "active", "op": "set", "value": []}],
        })
        compiler = StaticLLMPlanCompiler(response_json=response_json)
        task = _make_task()

        result = compiler.compile_plan(task, context="")

        assert result == response_json


class TestPlanWithLLM:
    def test_plan_generation_with_static_compiler(self):
        response_json = json.dumps({
            "patches": [
                {"section": "goals", "key": "active", "op": "set", "value": ["task_1"]},
            ],
            "rationale": "minimal plan",
        })
        compiler = StaticLLMPlanCompiler(response_json=response_json)
        task = _make_task()

        plan = plan_with_llm(task, compiler)

        assert len(plan.candidate_patches) == 1
        assert plan.candidate_patches[0].section == "goals"

    def test_plan_fallback_on_failure(self):
        class FailingCompiler:
            def compile_plan(self, task, context):
                raise RuntimeError("LLM failed")

        compiler = FailingCompiler()
        task = _make_task()

        plan = plan_with_llm(task, compiler, fallback_to_deterministic=True)

        assert plan is not None
        assert len(plan.candidate_patches) > 0

    def test_plan_raises_on_failure_without_fallback(self):
        class FailingCompiler:
            def compile_plan(self, task, context):
                raise RuntimeError("LLM failed")

        compiler = FailingCompiler()
        task = _make_task()

        with pytest.raises(RuntimeError, match="LLM failed"):
            plan_with_llm(task, compiler, fallback_to_deterministic=False)

    def test_plan_with_reasoning_step(self):
        from cee_core.deliberation import ReasoningStep

        response_json = json.dumps({
            "patches": [
                {"section": "beliefs", "key": "test", "op": "set", "value": "data"},
            ],
        })
        compiler = StaticLLMPlanCompiler(response_json=response_json)
        task = _make_task()
        step = ReasoningStep(
            task_id=task.task_id,
            summary="test step",
            hypothesis="test",
            missing_information=(),
            candidate_actions=("propose_plan",),
            chosen_action="propose_plan",
            rationale="test rationale",
            stop_condition="done",
        )

        plan = plan_with_llm(task, compiler, reasoning_step=step)

        assert len(plan.candidate_patches) == 1


class TestProviderBackedPlanCompiler:
    def test_provider_backed_compiler_records_events(self):
        from cee_core.llm_provider import StaticLLMProvider

        provider = StaticLLMProvider(
            response_text=json.dumps({
                "patches": [
                    {"section": "goals", "key": "active", "op": "set", "value": ["task_1"]},
                ],
            })
        )
        log = EventLog()
        compiler = ProviderBackedPlanCompiler(provider=provider, event_log=log)
        task = _make_task()

        response = compiler.compile_plan(task, context="")

        plan = parse_llm_plan_response(response, task)
        assert len(plan.candidate_patches) == 1

        events = log.all()
        assert any(e.event_type == "llm.plan_compiler.requested" for e in events)
        assert any(e.event_type == "llm.plan_compiler.succeeded" for e in events)

    def test_provider_backed_compiler_records_failure_events(self):
        from cee_core.llm_provider import FailingLLMProvider

        provider = FailingLLMProvider(kind="provider_error", message="test failure")
        log = EventLog()
        compiler = ProviderBackedPlanCompiler(provider=provider, event_log=log)
        task = _make_task()

        with pytest.raises(RuntimeError):
            compiler.compile_plan(task, context="")

        events = log.all()
        assert any(e.event_type == "llm.plan_compiler.requested" for e in events)
        assert any(e.event_type == "llm.plan_compiler.failed" for e in events)
