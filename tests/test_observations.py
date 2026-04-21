import json
import pytest

from cee_core import (
    EventLog,
    ObservationCandidate,
    ToolResultEvent,
    build_observation_event,
    observation_from_tool_result,
    promote_observation_to_delta,
    PlanSpec,
    execute_plan,
)


def test_observation_candidate_serializes():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    payload = observation.to_dict()
    assert payload["source_tool"] == "read_docs"
    assert payload["confidence"] == 0.8


def test_observation_from_successful_tool_result():
    event = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="succeeded",
        result={"hits": 2},
    )
    observation = observation_from_tool_result(event)
    assert observation.source_tool == "read_docs"
    assert observation.content == {"hits": 2}


def test_observation_from_failed_tool_result_is_rejected():
    event = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="failed",
        error_message="not found",
    )
    with pytest.raises(ValueError, match="Only succeeded tool results"):
        observation_from_tool_result(event)


def test_build_observation_event_serializes_observation():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    event = build_observation_event(observation, actor="observer")
    payload = event.to_dict()
    assert payload["event_type"] == "observation.candidate.recorded"
    assert payload["trace_id"] == "toolcall_1"


def test_observation_event_is_audit_only_for_replay():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    log = EventLog()
    log.append(build_observation_event(observation))
    ws = log.replay_world_state()
    assert ws.state_id == "ws_0"
    assert len(ws.entities) == 0


def test_promote_observation_to_delta_creates_belief_delta():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    delta = promote_observation_to_delta(observation, belief_key="tool.read_docs.hits")
    assert delta.target_kind == "entity_update"
    assert delta.target_ref == "beliefs.tool.read_docs.hits"
    assert delta.raw_value["content"] == {"hits": 2}
    assert delta.raw_value["confidence"] == 0.8
    assert delta.raw_value["evidence_count"] == 1


def test_promote_observation_to_delta_rejects_empty_belief_key():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    with pytest.raises(ValueError, match="belief_key cannot be empty"):
        promote_observation_to_delta(observation, belief_key=" ")


def test_promoted_observation_delta_through_execute_plan():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    delta = promote_observation_to_delta(observation, belief_key="tool.read_docs.hits")

    log = EventLog()
    plan = PlanSpec(objective="promote observation", candidate_deltas=(delta,))
    result = execute_plan(plan, event_log=log)

    assert result.allowed_count == 1
    ws = log.replay_world_state()
    entity = ws.find_entity("belief-tool.read_docs.hits")
    assert entity is not None
    belief_data = json.loads(entity.summary)
    assert belief_data["content"] == {"hits": 2}
    assert belief_data["confidence"] == 0.8
