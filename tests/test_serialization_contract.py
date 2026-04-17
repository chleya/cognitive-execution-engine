from cee_core import (
    DELIBERATION_EVENT_SCHEMA_VERSION,
    PATCH_SCHEMA_VERSION,
    PLAN_SCHEMA_VERSION,
    POLICY_DECISION_SCHEMA_VERSION,
    REASONING_STEP_SCHEMA_VERSION,
    STATE_TRANSITION_EVENT_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION,
    DeliberationEvent,
    PlanSpec,
    PolicyDecision,
    ReasoningStep,
    StatePatch,
    StateTransitionEvent,
    TaskSpec,
    replay_serialized_transition_events,
)


def test_state_patch_round_trip():
    patch = StatePatch(section="beliefs", key="source_count", op="set", value=3)

    payload = patch.to_dict()
    restored = StatePatch.from_dict(payload)

    assert payload["schema_version"] == PATCH_SCHEMA_VERSION
    assert restored == patch


def test_policy_decision_round_trip():
    decision = PolicyDecision(
        verdict="requires_approval",
        reason="self_model mutation",
        policy_ref="stage0.patch-policy:v1",
    )

    payload = decision.to_dict()
    restored = PolicyDecision.from_dict(payload)

    assert payload["schema_version"] == POLICY_DECISION_SCHEMA_VERSION
    assert restored == decision


def test_task_spec_round_trip():
    task = TaskSpec(
        task_id="task_1",
        objective="analyze risk",
        kind="analysis",
        risk_level="low",
        task_level="L1",
        success_criteria=("structured", "audited"),
        requested_primitives=("observe", "interpret", "plan", "verify"),
        raw_input=" analyze risk ",
    )

    payload = task.to_dict()
    restored = TaskSpec.from_dict(payload)

    assert payload["schema_version"] == TASK_SCHEMA_VERSION
    assert restored == task


def test_plan_spec_round_trip():
    plan = PlanSpec.from_patches(
        objective="analyze risk",
        candidate_patches=[
            StatePatch(section="beliefs", key="risk", op="set", value="low"),
        ],
        actor="deterministic-planner",
    )

    payload = plan.to_dict()
    restored = PlanSpec.from_dict(payload)

    assert payload["schema_version"] == PLAN_SCHEMA_VERSION
    assert restored == plan


def test_reasoning_step_round_trip():
    step = ReasoningStep(
        step_id="rs_1",
        task_id="task_1",
        summary="Select next action",
        hypothesis="Need evidence",
        missing_information=("docs not read",),
        candidate_actions=("propose_plan", "request_read_tool"),
        chosen_action="request_read_tool",
        rationale="Read docs first.",
        stop_condition="Stop after selecting next action.",
    )

    payload = step.to_dict()
    restored = ReasoningStep.from_dict(payload)

    assert payload["schema_version"] == REASONING_STEP_SCHEMA_VERSION
    assert restored == step


def test_state_transition_event_round_trip():
    event = StateTransitionEvent(
        patch=StatePatch(section="beliefs", key="source_count", op="set", value=2),
        policy_decision=PolicyDecision(
            verdict="allow",
            reason="safe",
            policy_ref="stage0.patch-policy:v1",
        ),
        trace_id="tr_1",
        actor="planner",
        reason="test",
        created_at="2026-04-16T00:00:00+00:00",
    )

    payload = event.to_dict()
    restored = StateTransitionEvent.from_dict(payload)

    assert payload["schema_version"] == STATE_TRANSITION_EVENT_SCHEMA_VERSION
    assert restored == event


def test_deliberation_event_round_trip():
    event = DeliberationEvent(
        reasoning_step=ReasoningStep(
            step_id="rs_1",
            task_id="task_1",
            summary="Select next action",
            hypothesis="Need evidence",
            missing_information=("docs not read",),
            candidate_actions=("propose_plan", "request_read_tool"),
            chosen_action="request_read_tool",
            rationale="Read docs first.",
            stop_condition="Stop after selecting next action.",
        ),
        trace_id="tr_1",
        actor="deliberation_engine",
        created_at="2026-04-16T00:00:00+00:00",
    )

    payload = event.to_dict()
    restored = DeliberationEvent.from_dict(payload)

    assert payload["schema_version"] == DELIBERATION_EVENT_SCHEMA_VERSION
    assert restored == event


def test_replay_serialized_transition_events_ignores_non_transition_and_blocked():
    allowed = StateTransitionEvent(
        patch=StatePatch(section="beliefs", key="source_count", op="set", value=2),
        policy_decision=PolicyDecision(
            verdict="allow",
            reason="safe",
            policy_ref="stage0.patch-policy:v1",
        ),
    )
    blocked = StateTransitionEvent(
        patch=StatePatch(section="self_model", key="identity", op="set", value="x"),
        policy_decision=PolicyDecision(
            verdict="requires_approval",
            reason="self model",
            policy_ref="stage0.patch-policy:v1",
        ),
    )
    payloads = [
        {"event_type": "task.received", "payload": {"task_id": "task_1"}},
        blocked.to_dict(),
        allowed.to_dict(),
    ]

    state = replay_serialized_transition_events(payloads)

    assert state.beliefs["source_count"] == 2
    assert "identity" not in state.self_model
    assert state.meta["version"] == 1


def test_missing_schema_version_is_rejected():
    payload = StatePatch(section="beliefs", key="x", op="set", value=1).to_dict()
    payload.pop("schema_version")

    try:
        StatePatch.from_dict(payload)
    except ValueError as exc:
        assert "Missing schema_version" in str(exc)
    else:
        raise AssertionError("missing schema_version should be rejected")


def test_unknown_major_schema_version_is_rejected():
    payload = StatePatch(section="beliefs", key="x", op="set", value=1).to_dict()
    payload["schema_version"] = "cee.patch.v2"

    try:
        StatePatch.from_dict(payload)
    except ValueError as exc:
        assert "Unsupported schema major version" in str(exc)
    else:
        raise AssertionError("unknown major schema version should be rejected")
