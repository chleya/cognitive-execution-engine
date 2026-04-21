import pytest

from cee_core import (
    DomainPluginPack,
    DomainPluginRegistry,
    EventLog,
    PlanSpec,
    RevisionDelta,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
)
from cee_core.runtime import _execute_plan_in_domain
from cee_core.tool_runner import InMemoryReadOnlyToolRunner
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent


def test_execute_task_runs_full_low_risk_pipeline():
    result = execute_task("analyze project risk")

    assert result.task.objective == "analyze project risk"
    assert result.reasoning_step.chosen_action == "propose_plan"
    assert result.task.kind == "analysis"
    assert result.task.task_level == "L1"
    assert result.task.requested_primitives == (
        "observe",
        "interpret",
        "plan",
        "verify",
    )
    assert result.plan.objective == "analyze project risk"
    assert len(result.allowed_transitions) == 4
    assert len(result.blocked_transitions) == 0
    assert result.world_state is not None
    assert len(result.commitment_events) == 4
    assert len(result.revision_events) == 4


def test_execute_task_records_commitment_and_revision_events():
    result = execute_task("analyze project risk")
    events = result.event_log.all()

    ce_events = [e for e in events if isinstance(e, CommitmentEvent)]
    rev_events = [e for e in events if isinstance(e, ModelRevisionEvent)]

    assert len(ce_events) == 4
    assert len(rev_events) == 4
    assert events[0].event_type == "task.received"
    assert events[1].event_type == "reasoning.step.selected"


def test_execute_task_reports_medium_risk_blocked_transition():
    result = execute_task("update the project belief summary")

    assert result.task.kind == "state_update"
    assert result.task.task_level == "L2"
    assert "escalate" in result.task.requested_primitives
    assert len(result.allowed_transitions) == 4
    assert len(result.approval_required_transitions) == 1
    assert len(result.denied_transitions) == 0
    assert result.world_state is not None


def test_execute_task_can_use_existing_event_log():
    log = EventLog()

    result = execute_task("analyze project risk", event_log=log)

    assert result.event_log is log
    ce_count = len([e for e in log.all() if isinstance(e, CommitmentEvent)])
    rev_count = len([e for e in log.all() if isinstance(e, ModelRevisionEvent)])
    assert ce_count == 4
    assert rev_count == 4


def test_execute_task_rejects_empty_input_before_planning():
    with pytest.raises(ValueError):
        execute_task("   ")


def test_execute_task_in_domain_overlay_tightens_policy():
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )

    result = execute_task_in_domain("update the project belief summary", domain_ctx)

    memory_denied = [
        d for d in result.plan_result.policy_decisions
        if "memory" in _decision_section(d) and not d.allowed and not d.requires_approval
    ]
    assert len(memory_denied) == 1
    assert "domain policy denies" in memory_denied[0].reason
    assert len(result.approval_required_transitions) == 1


def test_domain_registry_provides_context_for_execution():
    registry = DomainPluginRegistry()
    registry.register(
        DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )

    domain_ctx = build_domain_context("construction-site", registry=registry)
    assert domain_ctx.plugin_pack is not None
    assert domain_ctx.plugin_pack.denied_patch_sections == ("memory",)

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    memory_denied = [
        d for d in result.plan_result.policy_decisions
        if "memory" in _decision_section(d) and not d.allowed and not d.requires_approval
    ]
    assert len(memory_denied) == 1


def test_execute_task_in_domain_overlay_requires_approval_tightening():
    domain_ctx = build_domain_context("compliance-review")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="compliance-review",
            approval_required_patch_sections=("beliefs",),
        ),
    )

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    beliefs_approval = [
        d for d in result.plan_result.policy_decisions
        if "beliefs" in _decision_section(d) and d.requires_approval
    ]
    assert len(beliefs_approval) == 2
    assert all("domain policy requires approval" in d.reason for d in beliefs_approval)


def test_execute_task_in_domain_with_no_plugin_pack_equals_core_policy():
    domain_ctx = build_domain_context("nonexistent-domain")

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    assert domain_ctx.plugin_pack is None
    beliefs_allowed = [
        d for d in result.plan_result.policy_decisions
        if "beliefs" in _decision_section(d) and d.allowed and not d.requires_approval
    ]
    memory_allowed = [
        d for d in result.plan_result.policy_decisions
        if "memory" in _decision_section(d) and d.allowed and not d.requires_approval
    ]
    assert len(beliefs_allowed) == 2
    assert len(memory_allowed) == 1


def test_event_log_contains_domain_tightened_commitment_audit_trail():
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            approval_required_patch_sections=("goals",),
        ),
    )

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    log_events = result.event_log.all()
    goals_commitments = [
        e for e in log_events
        if isinstance(e, CommitmentEvent)
        and ("goals" in e.intent_summary or "goals" in e.action_summary)
    ]
    assert len(goals_commitments) >= 1
    assert len(log_events) >= len(result.commitment_events)


def test_execute_plan_in_domain_runs_read_only_tool_flow_when_runner_is_present():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})
    plan = PlanSpec(
        objective="Read docs",
        candidate_deltas=(
            RevisionDelta(delta_id="d1", target_kind="goal_update", target_ref="goals.active", before_summary="no goal", after_summary="g1", justification="set active goal", raw_value=["g1"]),
        ),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "runtime"}),
        ),
    )
    log = EventLog()

    result = _execute_plan_in_domain(
        plan,
        build_domain_context("core"),
        event_log=log,
        tool_runner=runner,
        promote_tool_observations_to_belief_keys={
            plan.proposed_tool_calls[0].call_id: "tool.read_docs.result"
        },
    )

    assert len(result.commitment_events) >= 1
    assert len(result.allowed_tool_calls) == 1
    ws = log.replay_world_state()
    entity = ws.find_entity("belief-tool.read_docs.result")
    assert entity is not None
    import json
    belief_data = json.loads(entity.summary)
    assert belief_data["content"]["hits"] == 2


def test_execute_plan_in_domain_rejects_tool_calls_without_runner():
    plan = PlanSpec(
        objective="Read docs",
        candidate_deltas=(),
        proposed_tool_calls=(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "runtime"}),
        ),
    )

    with pytest.raises(ValueError, match="tool_runner is required"):
        _execute_plan_in_domain(
            plan,
            build_domain_context("core"),
            event_log=EventLog(),
        )


def test_execute_task_in_domain_with_runner_executes_planner_proposed_read_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 3})

    result = execute_task_in_domain(
        "read docs about runtime policy",
        build_domain_context("core"),
        tool_runner=runner,
        promote_tool_observations_to_belief_keys={},
    )

    assert len(result.plan.proposed_tool_calls) == 1
    assert result.reasoning_step.chosen_action == "request_read_tool"
    assert len(result.plan_result.allowed_tool_calls) == 1
    tool_result_events = [
        event for event in result.event_log.all() if getattr(event, "event_type", "") == "tool.call.result"
    ]
    assert len(tool_result_events) == 1
    assert tool_result_events[0].status == "succeeded"


def _decision_section(decision) -> str:
    if "memory" in decision.reason.lower():
        return "memory"
    if "beliefs" in decision.reason.lower() or "belief" in decision.reason.lower():
        return "beliefs"
    if "goals" in decision.reason.lower() or "goal" in decision.reason.lower():
        return "goals"
    if "self_model" in decision.reason.lower() or "self model" in decision.reason.lower():
        return "self_model"
    return "other"
