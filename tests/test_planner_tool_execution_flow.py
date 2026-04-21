import json
from cee_core.event_log import EventLog
from cee_core.planner import PlanSpec
from cee_core.world_schema import RevisionDelta
from cee_core.tool_observation_flow import execute_plan_with_read_only_tools
from cee_core.tool_runner import InMemoryReadOnlyToolRunner
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec


def test_execute_plan_with_read_only_tools_runs_allowed_calls_once() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_metrics",
            description="Read metrics",
            risk="read",
        )
    )
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_metrics", lambda args: {"count": args["count"]})

    call = ToolCallSpec(
        call_id="toolcall_metrics",
        tool_name="read_metrics",
        arguments={"count": 7},
    )
    plan = PlanSpec(
        objective="Read metrics and track task",
        candidate_deltas=(
            RevisionDelta(delta_id="d1", target_kind="goal_update", target_ref="goals.active", before_summary="no goal", after_summary="g1", justification="set active goal", raw_value=["g1"]),
        ),
        proposed_tool_calls=(call,),
    )
    log = EventLog()

    result = execute_plan_with_read_only_tools(
        plan,
        runner,
        event_log=log,
        promote_to_belief_keys={call.call_id: "metrics.latest"},
    )

    assert len(result.plan_result.tool_call_events) == 1
    assert len(result.tool_flow_results) == 1
    assert result.tool_flow_results[0].tool_result_event.status == "succeeded"
    assert result.tool_flow_results[0].observation is not None
    assert result.tool_flow_results[0].promotion_delta is not None

    proposed_events = [
        event
        for event in log.all()
        if getattr(event, "event_type", "") == "tool.call.proposed"
    ]
    assert len(proposed_events) == 1
    ws = log.replay_world_state()
    entity = ws.find_entity("belief-metrics.latest")
    assert entity is not None
    belief_data = json.loads(entity.summary)
    assert belief_data["content"] == {"count": 7}


def test_execute_plan_with_read_only_tools_skips_blocked_calls() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="write_metrics",
            description="Write metrics",
            risk="write",
        )
    )
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    call = ToolCallSpec(
        call_id="toolcall_write",
        tool_name="write_metrics",
        arguments={"count": 7},
    )
    plan = PlanSpec(
        objective="Attempt write",
        candidate_deltas=(),
        proposed_tool_calls=(call,),
    )
    log = EventLog()

    result = execute_plan_with_read_only_tools(plan, runner, event_log=log)

    assert len(result.plan_result.tool_call_events) == 1
    assert result.plan_result.tool_call_events[0].decision.verdict == "requires_approval"
    assert result.tool_flow_results == ()
    assert not any(
        getattr(event, "event_type", "") == "tool.call.result" for event in log.all()
    )


def test_execute_plan_with_read_only_tools_does_not_promote_without_mapping() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="read_metrics",
            description="Read metrics",
            risk="read",
        )
    )
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_metrics", lambda args: {"count": args["count"]})

    call = ToolCallSpec(
        call_id="toolcall_metrics",
        tool_name="read_metrics",
        arguments={"count": 3},
    )
    plan = PlanSpec(
        objective="Read metrics without promotion",
        candidate_deltas=(),
        proposed_tool_calls=(call,),
    )
    log = EventLog()

    result = execute_plan_with_read_only_tools(plan, runner, event_log=log)

    assert len(result.tool_flow_results) == 1
    assert result.tool_flow_results[0].observation is not None
    assert result.tool_flow_results[0].promotion_delta is None
    ws = log.replay_world_state()
    assert len(ws.hypotheses) == 0
    assert len(ws.anchored_fact_summaries) == 0
