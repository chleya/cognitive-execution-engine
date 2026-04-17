from cee_core import EventLog, ToolResultEvent


def test_tool_result_event_serializes_success_result():
    event = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="succeeded",
        result={"documents": 2},
    )

    payload = event.to_dict()

    assert payload["event_type"] == "tool.call.result"
    assert payload["trace_id"] == "toolcall_1"
    assert payload["tool_name"] == "read_docs"
    assert payload["status"] == "succeeded"
    assert payload["result"] == {"documents": 2}
    assert payload["error_message"] == ""


def test_tool_result_event_serializes_failure_result():
    event = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="failed",
        error_message="not found",
    )

    payload = event.to_dict()

    assert payload["status"] == "failed"
    assert payload["result"] is None
    assert payload["error_message"] == "not found"


def test_tool_result_events_are_audit_only_for_state_replay():
    log = EventLog()
    log.append(
        ToolResultEvent(
            call_id="toolcall_1",
            tool_name="read_docs",
            status="succeeded",
            result={"documents": 2},
        )
    )

    state = log.replay_state()

    assert state.snapshot() == {
        "memory": {},
        "goals": {},
        "beliefs": {},
        "self_model": {},
        "policy": {},
        "domain_data": {},
        "tool_affordances": {},
        "meta": {"version": 0},
    }
