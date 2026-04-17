from cee_core import (
    Event,
    EventLog,
    PolicyDecision,
    StatePatch,
    StateTransitionEvent,
    replay_transition_events,
)


def _allow() -> PolicyDecision:
    return PolicyDecision(
        verdict="allow",
        reason="safe transition",
        policy_ref="state-policy:v1",
    )


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


def test_event_log_replays_only_transition_events():
    log = EventLog()
    log.append(Event(event_type="task.received", payload={"task_id": "t1"}))
    log.append(
        StateTransitionEvent(
            patch=StatePatch(section="beliefs", key="source_count", op="set", value=2),
            policy_decision=_allow(),
        )
    )
    log.append(Event(event_type="task.completed", payload={"task_id": "t1"}))

    state = log.replay_state()

    assert state.beliefs["source_count"] == 2
    assert state.meta["version"] == 1


def test_replay_transition_events_accepts_mixed_stream():
    events = [
        Event(event_type="audit.note", payload={"message": "ignored by replay"}),
        StateTransitionEvent(
            patch=StatePatch(section="memory", key="working", op="append", value="step"),
            policy_decision=_allow(),
        ),
    ]

    state = replay_transition_events(events)

    assert state.memory["working"] == ["step"]
    assert state.meta["version"] == 1


def test_replay_transition_events_ignores_blocked_transition_events():
    events = [
        StateTransitionEvent(
            patch=StatePatch(section="self_model", key="identity", op="set", value="x"),
            policy_decision=PolicyDecision(
                verdict="requires_approval",
                reason="self_model requires approval",
                policy_ref="stage0.patch-policy:v1",
            ),
        ),
        StateTransitionEvent(
            patch=StatePatch(section="beliefs", key="source_count", op="set", value=1),
            policy_decision=_allow(),
        ),
    ]

    state = replay_transition_events(events)

    assert "identity" not in state.self_model
    assert state.beliefs["source_count"] == 1
    assert state.meta["version"] == 1
