from cee_core import (
    EventLog,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    build_tool_call_event,
)


def test_build_tool_call_event_records_allowed_read_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    call = ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"})

    event = build_tool_call_event(call, registry, actor="planner")

    assert event.event_type == "tool.call.proposed"
    assert event.trace_id == call.call_id
    assert event.actor == "planner"
    assert event.decision.verdict == "allow"


def test_build_tool_call_event_records_approval_required_write_tool():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="write_doc", description="Write doc", risk="write"))
    call = ToolCallSpec(tool_name="write_doc", arguments={"content": "x"})

    event = build_tool_call_event(call, registry)

    assert event.decision.verdict == "requires_approval"
    assert event.decision.blocked is True


def test_build_tool_call_event_records_denied_unknown_tool():
    registry = ToolRegistry()
    call = ToolCallSpec(tool_name="unknown", arguments={})

    event = build_tool_call_event(call, registry)

    assert event.decision.verdict == "deny"
    assert event.decision.blocked is True


def test_tool_call_event_serializes_call_and_decision():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    call = ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"})

    payload = build_tool_call_event(call, registry).to_dict()

    assert payload["event_type"] == "tool.call.proposed"
    assert payload["call"]["tool_name"] == "read_docs"
    assert payload["decision"]["verdict"] == "allow"


def test_tool_call_events_are_audit_only_for_state_replay():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    log = EventLog()

    log.append(
        build_tool_call_event(
            ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
            registry,
        )
    )
    ws = log.replay_world_state()

    assert ws.state_id == "ws_0"
    assert ws.dominant_goals == ()
    assert ws.entities == ()
