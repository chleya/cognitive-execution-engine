from cee_core import (
    Event,
    EventLog,
    CommitmentEvent,
    ModelRevisionEvent,
    RevisionDelta,
)
from cee_core.world_state import WorldState


def test_event_log_appends_and_lists_events():
    log = EventLog()
    event = Event(event_type="task.received", payload={"task_id": "t1"})

    log.append(event)

    assert log.all() == (event,)


def test_event_log_filters_by_trace_id():
    trace_id = "tr_shared"
    first = Event(event_type="task.received", payload={}, trace_id=trace_id)
    second = Event(event_type="task.completed", payload={}, trace_id=trace_id)
    other = Event(event_type="task.received", payload={}, trace_id="tr_other")
    log = EventLog()

    for event in (first, second, other):
        log.append(event)

    assert log.by_trace(trace_id) == (first, second)


def test_event_log_replays_only_revision_events():
    log = EventLog()
    log.append(Event(event_type="task.received", payload={"task_id": "t1"}))

    ce = CommitmentEvent(
        event_id="ce-1",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test",
        action_summary="beliefs source_count",
        success=True,
    )
    rev = ModelRevisionEvent(
        revision_id="rev-1",
        prior_state_id="ws_0",
        caused_by_event_id="ce-1",
        revision_kind="expansion",
        deltas=(RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="2", justification="set source count", raw_value=2),),
        resulting_state_id="ws_1",
        revision_summary="set source count",
    )
    log.append(ce)
    log.append(rev)
    log.append(Event(event_type="task.completed", payload={"task_id": "t1"}))

    ws = log.replay_world_state()

    entity = ws.find_entity("belief-source_count")
    assert entity is not None
    assert ws.state_id == "ws_1"


def test_event_log_replay_world_state_from_commitment_and_revision():
    log = EventLog()
    log.append(Event(event_type="task.received", payload={"task_id": "t1"}))

    ce = CommitmentEvent(
        event_id="ce-1",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test",
        action_summary="beliefs source_count",
        success=True,
    )
    rev = ModelRevisionEvent(
        revision_id="rev-1",
        prior_state_id="ws_0",
        caused_by_event_id="ce-1",
        revision_kind="expansion",
        deltas=(RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="2", justification="test", raw_value=2),),
        resulting_state_id="ws_1",
        revision_summary="set source count",
    )
    log.append(ce)
    log.append(rev)

    ws = log.replay_world_state()

    assert isinstance(ws, WorldState)
    assert ws.state_id == "ws_1"


def test_event_log_replay_world_state_ignores_blocked_transitions():
    blocked_ce = CommitmentEvent(
        event_id="ce-blocked",
        source_state_id="",
        commitment_kind="internal_commit",
        intent_summary="test",
        action_summary="self_model identity",
        success=False,
        requires_approval=True,
    )
    allowed_ce = CommitmentEvent(
        event_id="ce-allowed",
        source_state_id="",
        commitment_kind="observe",
        intent_summary="test",
        action_summary="beliefs source_count",
        success=True,
    )
    rev = ModelRevisionEvent(
        revision_id="rev-1",
        prior_state_id="ws_0",
        caused_by_event_id="ce-allowed",
        revision_kind="expansion",
        deltas=(RevisionDelta(delta_id="d1", target_kind="entity_update", target_ref="beliefs.source_count", before_summary="unknown", after_summary="1", justification="test", raw_value=1),),
        resulting_state_id="ws_1",
        revision_summary="set source count",
    )

    log = EventLog()
    log.append(blocked_ce)
    log.append(allowed_ce)
    log.append(rev)

    ws = log.replay_world_state()

    assert isinstance(ws, WorldState)
    assert len(log.revision_events()) == 1
