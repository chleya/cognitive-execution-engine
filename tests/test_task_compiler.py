import pytest

from cee_core import EventLog, compile_task, execute_plan, plan_from_task


def test_compile_task_normalizes_raw_input_into_task_spec():
    task = compile_task("  analyze   project   risk  ")

    assert task.objective == "analyze project risk"
    assert task.kind == "analysis"
    assert task.risk_level == "low"
    assert task.task_level == "L1"
    assert task.requested_primitives == ("observe", "interpret", "plan", "verify")
    assert task.raw_input == "  analyze   project   risk  "


def test_compile_task_rejects_empty_input():
    with pytest.raises(ValueError):
        compile_task("   ")


def test_compile_task_records_task_received_event():
    log = EventLog()
    task = compile_task("analyze project risk", event_log=log)

    events = log.all()

    assert len(events) == 1
    assert events[0].event_type == "task.received"
    assert events[0].payload["task_id"] == task.task_id


def test_compile_task_marks_write_like_input_as_state_update():
    task = compile_task("update the project belief summary")

    assert task.kind == "state_update"
    assert task.risk_level == "medium"
    assert task.task_level == "L2"
    assert task.requested_primitives == (
        "observe",
        "interpret",
        "plan",
        "act",
        "verify",
        "escalate",
    )


def test_compile_task_marks_chinese_update_input_as_state_update():
    task = compile_task("更新项目状态摘要")

    assert task.kind == "state_update"
    assert task.risk_level == "medium"
    assert task.task_level == "L2"


def test_compile_task_marks_simple_lookup_as_l0():
    task = compile_task("read docs about runtime policy")

    assert task.kind == "analysis"
    assert task.task_level == "L0"


def test_compile_task_marks_migration_heavy_input_as_l3():
    task = compile_task("migrate cross-domain workflow state")

    assert task.task_level == "L3"


def test_plan_from_task_does_not_use_raw_input_directly():
    task = compile_task("  analyze   project   risk  ")
    plan = plan_from_task(task)

    assert plan.objective == "analyze project risk"
    assert all(task.raw_input not in str(patch.value) for patch in plan.candidate_patches)


def test_task_to_plan_to_replay_pipeline_applies_allowed_updates():
    log = EventLog()
    task = compile_task("analyze project risk", event_log=log)
    plan = plan_from_task(task)
    result = execute_plan(plan, event_log=log)
    state = log.replay_state()

    assert len(result.allowed) == 4
    assert state.goals["active"] == [task.task_id]
    assert state.beliefs[f"task.{task.task_id}.objective"] == "analyze project risk"
    assert state.beliefs[f"task.{task.task_id}.domain_name"] == "core"
    assert state.memory["working"][0]["task_id"] == task.task_id
    assert state.memory["working"][0]["requested_primitives"] == [
        "observe",
        "interpret",
        "plan",
        "verify",
    ]
    assert state.memory["working"][0]["task_level"] == "L1"


def test_medium_risk_task_generates_approval_required_self_model_patch():
    log = EventLog()
    task = compile_task("update the project belief summary", event_log=log)
    plan = plan_from_task(task)
    result = execute_plan(plan, event_log=log)
    state = log.replay_state()

    assert len(result.requires_approval) == 1
    assert "last_medium_or_high_risk_task" not in state.self_model
    assert state.goals["active"] == [task.task_id]
    assert state.beliefs[f"task.{task.task_id}.domain_name"] == "core"
