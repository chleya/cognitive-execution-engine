from cee_core import (
    EventLog,
    PlanSpec,
    ReasoningStep,
    TaskSpec,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    execute_plan,
    plan_from_task,
)


def _registry():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    registry.register(ToolSpec(name="write_doc", description="Write doc", risk="write"))
    return registry


def test_execute_plan_records_proposed_tool_calls_as_audit_events():
    log = EventLog()
    plan = PlanSpec(
        objective="plan with read tool call",
        candidate_deltas=(),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        ),
        actor="deterministic-planner",
    )

    result = execute_plan(plan, event_log=log, tool_registry=_registry())

    assert len(result.tool_call_events) == 1
    assert len(result.allowed_tool_calls) == 1
    assert result.tool_call_events[0].event_type == "tool.call.proposed"
    assert log.all() == (result.tool_call_events[0],)


def test_execute_plan_blocks_write_tool_call_but_does_not_execute():
    log = EventLog()
    plan = PlanSpec(
        objective="plan with write tool call",
        candidate_deltas=(),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="write_doc", arguments={"content": "x"}),
        ),
        actor="deterministic-planner",
    )

    result = execute_plan(plan, event_log=log, tool_registry=_registry())

    assert len(result.tool_call_events) == 1
    assert len(result.allowed_tool_calls) == 0
    assert len(result.blocked_tool_calls) == 1
    assert result.tool_call_events[0].decision.verdict == "requires_approval"
    assert log.replay_world_state().state_id == "ws_0"


def test_execute_plan_requires_tool_registry_when_plan_proposes_tool_calls():
    plan = PlanSpec(
        objective="plan with read tool call",
        candidate_deltas=(),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        ),
        actor="deterministic-planner",
    )

    try:
        execute_plan(plan)
    except ValueError as exc:
        assert "tool_registry is required" in str(exc)
    else:
        raise AssertionError("expected execute_plan to reject missing tool_registry")


def test_plan_spec_round_trip_preserves_proposed_tool_calls():
    plan = PlanSpec(
        objective="plan with tool call",
        candidate_deltas=(),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        ),
        actor="deterministic-planner",
    )

    restored = PlanSpec.from_dict(plan.to_dict())

    assert restored == plan


def test_plan_from_task_proposes_read_docs_when_registry_supports_it():
    task = TaskSpec(
        objective="read docs about runtime policy",
        kind="analysis",
        risk_level="low",
        success_criteria=("find docs",),
        requested_primitives=("observe", "interpret", "plan", "verify"),
    )

    plan = plan_from_task(task, tool_registry=_registry())

    assert len(plan.proposed_tool_calls) == 1
    assert plan.proposed_tool_calls[0].tool_name == "read_docs"
    assert plan.proposed_tool_calls[0].arguments == {"query": "about runtime policy"}


def test_plan_from_task_does_not_propose_read_docs_without_registry():
    task = TaskSpec(
        objective="read docs about runtime policy",
        kind="analysis",
        risk_level="low",
        success_criteria=("find docs",),
        requested_primitives=("observe", "interpret", "plan", "verify"),
    )

    plan = plan_from_task(task)

    assert plan.proposed_tool_calls == ()


def test_plan_from_task_respects_reasoning_step_choice():
    task = TaskSpec(
        objective="read docs about runtime policy",
        kind="analysis",
        risk_level="low",
        success_criteria=("find docs",),
        requested_primitives=("observe", "interpret", "plan", "verify"),
    )
    step = ReasoningStep(
        task_id=task.task_id,
        summary="Proceed directly",
        hypothesis="Enough local context",
        missing_information=(),
        candidate_actions=("propose_plan", "request_read_tool"),
        chosen_action="propose_plan",
        rationale="Tool lookup is optional.",
        stop_condition="Stop after selecting next action.",
    )

    plan = plan_from_task(task, tool_registry=_registry(), reasoning_step=step)

    assert plan.proposed_tool_calls == ()
