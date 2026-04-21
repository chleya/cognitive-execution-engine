import json
from cee_core import EventLog, PlanSpec, RevisionDelta, execute_plan
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent


def test_execute_plan_records_allowed_blocked_and_approval_required_events():
    log = EventLog()
    plan = PlanSpec.from_deltas(
        objective="compile bounded state updates",
        candidate_deltas=[
            RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="3", justification="set source count", raw_value=3),
            RevisionDelta(delta_id="d2", target_kind="self_update", target_ref="self_model.capabilities", before_summary="unknown", after_summary="{}", justification="set capabilities", raw_value={}),
            RevisionDelta(delta_id="d3", target_kind="entity_update", target_ref="policy.allowed_tools", before_summary="unknown", after_summary="x", justification="set policy", raw_value=["x"]),
        ],
        actor="deterministic-planner",
    )

    result = execute_plan(plan, event_log=log)

    assert len(result.policy_decisions) == 3
    assert result.allowed_count == 1
    assert result.requires_approval_count == 1
    assert result.blocked_count == 1
    assert len(result.commitment_events) == 3
    assert len(result.revision_events) == 1
    commitment_count = sum(1 for e in log.all() if isinstance(e, CommitmentEvent))
    revision_count = sum(1 for e in log.all() if isinstance(e, ModelRevisionEvent))
    assert commitment_count == 3
    assert revision_count == 1


def test_plan_replay_applies_only_allowed_events():
    log = EventLog()
    plan = PlanSpec.from_deltas(
        objective="apply safe belief and block sensitive updates",
        candidate_deltas=[
            RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="3", justification="set source count", raw_value=3),
            RevisionDelta(delta_id="d2", target_kind="self_update", target_ref="self_model.identity", before_summary="unknown", after_summary="agent", justification="set identity", raw_value="agent"),
            RevisionDelta(delta_id="d3", target_kind="entity_update", target_ref="policy.allowed_tools", before_summary="unknown", after_summary="x", justification="set policy", raw_value=["x"]),
        ],
    )

    execute_plan(plan, event_log=log)
    ws = log.replay_world_state()

    entity = ws.find_entity("belief-source_count")
    assert entity is not None
    assert entity.summary == "3"
    assert ws.state_id != "ws_0"


def test_plan_result_preserves_plan_identity_in_event_reason():
    plan = PlanSpec.from_deltas(
        objective="record traceable plan reason",
        candidate_deltas=[
            RevisionDelta(delta_id="d1", target_kind="goal_update", target_ref="goals.active", before_summary="no goal", after_summary="g1", justification="set active goal", raw_value=["g1"]),
        ],
    )

    result = execute_plan(plan)

    assert result.commitment_events[0].intent_summary.startswith(f"plan:{plan.plan_id}:")
    assert "record traceable plan reason" in result.commitment_events[0].intent_summary
