from cee_core import ReasoningStep, TaskSpec, ToolRegistry, ToolSpec, deliberate_next_action


def test_reasoning_step_round_trip():
    step = ReasoningStep(
        step_id="rs_1",
        task_id="task_1",
        summary="Select next action",
        hypothesis="Need more evidence",
        missing_information=("docs not read",),
        candidate_actions=("propose_plan", "request_read_tool"),
        chosen_action="request_read_tool",
        rationale="Docs lookup is required first.",
        stop_condition="Stop after selecting next action.",
    )

    restored = ReasoningStep.from_dict(step.to_dict())

    assert restored == step


def test_deliberate_next_action_requests_read_tool_when_available():
    task = TaskSpec(
        task_id="task_1",
        objective="read docs about runtime policy",
        kind="analysis",
        risk_level="low",
        success_criteria=("find docs",),
        requested_primitives=("observe", "interpret", "plan", "verify"),
    )
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))

    step = deliberate_next_action(task, tool_registry=registry)

    assert step.chosen_action == "request_read_tool"
    assert "request_read_tool" in step.candidate_actions
    assert step.missing_information == ("External documentation evidence has not been observed yet.",)


def test_deliberate_next_action_stays_on_plan_when_read_tool_is_unavailable():
    task = TaskSpec(
        task_id="task_1",
        objective="read docs about runtime policy",
        kind="analysis",
        risk_level="low",
        success_criteria=("find docs",),
        requested_primitives=("observe", "interpret", "plan", "verify"),
    )

    step = deliberate_next_action(task)

    assert step.chosen_action == "propose_plan"
    assert "request_read_tool" in step.candidate_actions
