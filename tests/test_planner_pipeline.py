from cee_core import EventLog, PlanSpec, StatePatch, execute_plan


def test_execute_plan_records_allowed_blocked_and_approval_required_events():
    log = EventLog()
    plan = PlanSpec.from_patches(
        objective="compile bounded state updates",
        candidate_patches=[
            StatePatch(section="beliefs", key="source_count", op="set", value=3),
            StatePatch(section="self_model", key="capabilities", op="set", value={}),
            StatePatch(section="policy", key="allowed_tools", op="set", value=["x"]),
        ],
        actor="deterministic-planner",
    )

    result = execute_plan(plan, event_log=log)

    assert len(result.events) == 3
    assert len(result.allowed) == 1
    assert len(result.requires_approval) == 1
    assert len(result.denied) == 1
    assert len(log.all()) == 3


def test_plan_replay_applies_only_allowed_events():
    log = EventLog()
    plan = PlanSpec.from_patches(
        objective="apply safe belief and block sensitive updates",
        candidate_patches=[
            StatePatch(section="beliefs", key="source_count", op="set", value=3),
            StatePatch(section="self_model", key="identity", op="set", value="agent"),
            StatePatch(section="policy", key="allowed_tools", op="set", value=["x"]),
        ],
    )

    execute_plan(plan, event_log=log)
    state = log.replay_state()

    assert state.beliefs["source_count"] == 3
    assert "identity" not in state.self_model
    assert "allowed_tools" not in state.policy
    assert state.meta["version"] == 1


def test_plan_result_preserves_plan_identity_in_event_reason():
    plan = PlanSpec.from_patches(
        objective="record traceable plan reason",
        candidate_patches=[
            StatePatch(section="goals", key="active", op="set", value=["g1"]),
        ],
    )

    result = execute_plan(plan)

    assert result.events[0].reason.startswith(f"plan:{plan.plan_id}:")
    assert "record traceable plan reason" in result.events[0].reason

