from cee_core import (
    DELIBERATION_EVENT_SCHEMA_VERSION,
    PLAN_SCHEMA_VERSION,
    REASONING_STEP_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION,
    DeliberationEvent,
    PlanSpec,
    ReasoningStep,
    RevisionDelta,
    TaskSpec,
    CommitmentEvent,
    ModelRevisionEvent,
)
from cee_core.event_log import EventLog


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
    plan = PlanSpec.from_deltas(
        objective="analyze risk",
        candidate_deltas=[
            RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.risk", before_summary="unknown", after_summary="low", justification="set risk", raw_value="low"),
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


def test_commitment_event_round_trip():
    ce = CommitmentEvent(
        event_id="ce-test-1",
        source_state_id="ws_0",
        commitment_kind="observe",
        intent_summary="test plan",
        action_summary="beliefs source_count",
        success=True,
        reversibility="reversible",
    )

    payload = ce.to_dict()
    restored = CommitmentEvent.from_dict(payload)

    assert restored == ce


def test_revision_event_round_trip():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="beliefs.source_count",
        before_summary="unknown",
        after_summary="2",
        justification="set source count",
        raw_value=2,
    )
    rev = ModelRevisionEvent(
        revision_id="rev-1",
        prior_state_id="ws_0",
        caused_by_event_id="ce-1",
        revision_kind="expansion",
        deltas=(delta,),
        resulting_state_id="ws_1",
        revision_summary="set source count",
    )

    payload = rev.to_dict()
    restored = ModelRevisionEvent.from_dict(payload)

    assert restored == rev


def test_replay_world_state_ignores_blocked_transitions():
    log = EventLog()

    allowed_ce = CommitmentEvent(
        event_id="ce-1",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test",
        action_summary="beliefs source_count",
        success=True,
        reversibility="reversible",
    )
    blocked_ce = CommitmentEvent(
        event_id="ce-2",
        source_state_id="",
        commitment_kind="internal_commit",
        intent_summary="test",
        action_summary="self_model identity",
        success=False,
        reversibility="reversible",
        requires_approval=True,
    )

    log.append(allowed_ce)
    log.append(ModelRevisionEvent(
        revision_id="rev-1",
        prior_state_id="ws_0",
        caused_by_event_id="ce-1",
        revision_kind="expansion",
        deltas=(RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="2", justification="test", raw_value=2),),
        resulting_state_id="ws_1",
        revision_summary="set source count",
    ))
    log.append(blocked_ce)

    ws = log.replay_world_state()

    assert len(log.revision_events()) == 1
    assert ws.state_id == "ws_1"
