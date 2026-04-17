import pytest

from cee_core import (
    DomainPluginPack,
    DomainPluginRegistry,
    EventLog,
    PlanSpec,
    StateTransitionEvent,
    StatePatch,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
)
from cee_core.runtime import _execute_plan_in_domain
from cee_core.tool_runner import InMemoryReadOnlyToolRunner


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
    assert result.replayed_state.goals["active"] == [result.task.task_id]
    assert result.replayed_state.meta["version"] == 4


def test_execute_task_records_task_event_and_transition_attempts():
    result = execute_task("analyze project risk")
    events = result.event_log.all()

    assert len(events) == 6
    assert events[0].event_type == "task.received"
    assert events[1].event_type == "reasoning.step.selected"
    assert events[2].event_type == "state.patch.requested"


def test_execute_task_reports_medium_risk_blocked_transition():
    result = execute_task("update the project belief summary")

    assert result.task.kind == "state_update"
    assert result.task.task_level == "L2"
    assert "escalate" in result.task.requested_primitives
    assert len(result.allowed_transitions) == 4
    assert len(result.approval_required_transitions) == 1
    assert len(result.denied_transitions) == 0
    assert "last_medium_or_high_risk_task" not in result.replayed_state.self_model
    assert result.replayed_state.meta["version"] == 4


def test_execute_task_can_use_existing_event_log():
    log = EventLog()

    result = execute_task("analyze project risk", event_log=log)

    assert result.event_log is log
    assert len(log.all()) == 6


def test_execute_task_rejects_empty_input_before_planning():
    with pytest.raises(ValueError):
        execute_task("   ")


def test_execute_task_in_domain_overlay_tightens_policy():
    """Domain overlay must participate in actual execution trace, not just type-check."""
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )

    # "update the project belief summary" is medium-risk: generates memory + self_model patches
    result = execute_task_in_domain("update the project belief summary", domain_ctx)

    # Core policy: memory=allow, self_model=requires_approval
    # Domain overlay: memory=deny (tightened), self_model=unchanged
    memory_denied = [
        e for e in result.plan_result.events
        if e.patch.section == "memory" and e.policy_decision.verdict == "deny"
    ]
    assert len(memory_denied) == 1
    assert "domain policy denies" in memory_denied[0].policy_decision.reason
    # self_model still requires_approval (domain cannot loosen core requires_approval)
    assert len(result.approval_required_transitions) == 1


def test_domain_registry_provides_context_for_execution():
    """Migration test: second domain introduced via plugin registration, not core changes."""
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
        e for e in result.plan_result.events
        if e.patch.section == "memory" and e.policy_decision.verdict == "deny"
    ]
    assert len(memory_denied) == 1


def test_execute_task_in_domain_overlay_requires_approval_tightening():
    """Domain overlay can tighten allow → requires_approval, not just allow → deny."""
    domain_ctx = build_domain_context("compliance-review")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="compliance-review",
            approval_required_patch_sections=("beliefs",),
        ),
    )

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    # Core policy: beliefs=allow; Domain overlay: beliefs=requires_approval
    beliefs_approval = [
        e for e in result.plan_result.events
        if e.patch.section == "beliefs" and e.policy_decision.verdict == "requires_approval"
    ]
    assert len(beliefs_approval) == 2  # objective + domain_name
    assert all("domain policy requires approval" in e.policy_decision.reason for e in beliefs_approval)


def test_execute_task_in_domain_with_no_plugin_pack_equals_core_policy():
    """Domain context with no plugin pack does not change core policy decisions."""
    domain_ctx = build_domain_context("nonexistent-domain")

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    assert domain_ctx.plugin_pack is None
    # beliefs and memory are core-allow; no domain tightening applies
    beliefs_allowed = [
        e for e in result.plan_result.events
        if e.patch.section == "beliefs" and e.policy_decision.verdict == "allow"
    ]
    memory_allowed = [
        e for e in result.plan_result.events
        if e.patch.section == "memory" and e.policy_decision.verdict == "allow"
    ]
    assert len(beliefs_allowed) == 2
    assert len(memory_allowed) == 1


def test_event_log_contains_domain_tightened_transition_audit_trail():
    """Full event log audit trail includes domain overlay policy decisions."""
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            approval_required_patch_sections=("goals",),
        ),
    )

    result = execute_task_in_domain("analyze site hazards", domain_ctx)

    # Verify domain-tightened decisions appear in the full event log
    log_events = result.event_log.all()
    domain_approval_events = [
        e for e in log_events
        if isinstance(e, StateTransitionEvent)
        and e.patch.section == "goals"
        and e.policy_decision.verdict == "requires_approval"
        and "domain policy requires approval" in e.policy_decision.reason
    ]
    assert len(domain_approval_events) == 1
    # Non-transition events are also present (task events, etc.)
    assert len(log_events) >= len(result.plan_result.events)


def test_execute_plan_in_domain_runs_read_only_tool_flow_when_runner_is_present():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})
    plan = PlanSpec(
        objective="Read docs",
        candidate_patches=(
            StatePatch(section="goals", key="active", op="set", value=["g1"]),
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

    assert len(result.events) == 1
    assert len(result.allowed_tool_calls) == 1
    assert log.replay_state().beliefs["tool.read_docs.result"]["content"]["hits"] == 2


def test_execute_plan_in_domain_rejects_tool_calls_without_runner():
    plan = PlanSpec(
        objective="Read docs",
        candidate_patches=(),
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
