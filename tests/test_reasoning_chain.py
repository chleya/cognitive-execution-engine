import pytest

from cee_core import (
    ReasoningChain,
    ReasoningStep,
    deliberate_chain,
    deliberate_next_action,
)
from cee_core.tasks import TaskSpec


def _analysis_task() -> TaskSpec:
    return TaskSpec(
        task_id="t_chain_1",
        domain_name="core",
        kind="analysis",
        risk_level="medium",
        objective="read docs and analyze risk factors",
        success_criteria="analysis complete",
        task_level="atomic",
        requested_primitives=("observe", "interpret", "plan"),
    )


def _simple_task() -> TaskSpec:
    return TaskSpec(
        task_id="t_chain_2",
        domain_name="core",
        kind="execution",
        risk_level="low",
        objective="count to three",
        success_criteria="counted",
        task_level="atomic",
        requested_primitives=("plan",),
    )


def test_reasoning_step_is_terminal():
    step = ReasoningStep(
        task_id="t1",
        summary="test",
        hypothesis="test",
        missing_information=(),
        candidate_actions=("propose_plan",),
        chosen_action="propose_plan",
        rationale="test",
        stop_condition="test",
    )
    assert step.is_terminal is True


def test_reasoning_step_non_terminal():
    step = ReasoningStep(
        task_id="t1",
        summary="test",
        hypothesis="test",
        missing_information=(),
        candidate_actions=("request_read_tool",),
        chosen_action="request_read_tool",
        rationale="test",
        stop_condition="test",
    )
    assert step.is_terminal is False


def test_reasoning_chain_empty():
    chain = ReasoningChain(steps=())
    assert chain.final_action == "propose_plan"
    assert chain.is_terminal is False
    assert chain.step_count == 0


def test_reasoning_chain_single_terminal_step():
    step = ReasoningStep(
        task_id="t1",
        summary="test",
        hypothesis="test",
        missing_information=(),
        candidate_actions=("propose_plan",),
        chosen_action="propose_plan",
        rationale="test",
        stop_condition="test",
    )
    chain = ReasoningChain(steps=(step,))
    assert chain.final_action == "propose_plan"
    assert chain.is_terminal is True
    assert chain.step_count == 1


def test_deliberate_chain_simple_task():
    task = _simple_task()
    chain = deliberate_chain(task)

    assert chain.step_count >= 1
    assert chain.is_terminal is True
    assert chain.final_action == "propose_plan"


def test_deliberate_chain_analysis_task():
    task = _analysis_task()
    chain = deliberate_chain(task)

    assert chain.step_count >= 1
    assert chain.is_terminal is True


def test_deliberate_chain_respects_max_steps():
    task = _analysis_task()
    chain = deliberate_chain(task, max_steps=1)

    assert chain.step_count == 1


def test_reasoning_chain_to_dict():
    step = ReasoningStep(
        task_id="t1",
        summary="test",
        hypothesis="test",
        missing_information=(),
        candidate_actions=("propose_plan",),
        chosen_action="propose_plan",
        rationale="test",
        stop_condition="test",
    )
    chain = ReasoningChain(steps=(step,))

    d = chain.to_dict()
    assert d["step_count"] == 1
    assert d["final_action"] == "propose_plan"
    assert d["is_terminal"] is True
    assert len(d["steps"]) == 1


def test_chain_does_not_repeat_read_tool_request():
    from cee_core.tools import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="read_docs",
        description="Read docs",
        risk="read",
    ))

    task = TaskSpec(
        task_id="t_chain_3",
        domain_name="core",
        kind="analysis",
        risk_level="medium",
        objective="read docs about compliance",
        success_criteria="analysis complete",
        task_level="atomic",
        requested_primitives=("observe", "interpret"),
    )

    chain = deliberate_chain(task, tool_registry=registry)

    read_tool_steps = [
        s for s in chain.steps if s.chosen_action == "request_read_tool"
    ]
    assert len(read_tool_steps) <= 1

    assert chain.is_terminal is True
