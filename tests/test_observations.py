import pytest

from cee_core import (
    EventLog,
    ObservationCandidate,
    ToolResultEvent,
    build_observation_event,
    observation_from_tool_result,
    promote_observation_to_patch,
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

    assert payload == {
        "source_tool": "read_docs",
        "call_id": "toolcall_1",
        "content": {"hits": 2},
        "confidence": 0.8,
        "evidence_weight": 1.0,
        "provenance": ["tool:read_docs", "call:toolcall_1"],
    }


def test_observation_from_successful_tool_result():
    event = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="succeeded",
        result={"hits": 2},
    )

    observation = observation_from_tool_result(event)

    assert observation.source_tool == "read_docs"
    assert observation.call_id == "toolcall_1"
    assert observation.content == {"hits": 2}
    assert observation.confidence == 0.8
    assert observation.evidence_weight == 1.0
    assert observation.provenance == ("tool:read_docs", "call:toolcall_1")


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
    assert payload["actor"] == "observer"
    assert payload["observation"]["source_tool"] == "read_docs"


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
    state = log.replay_state()

    assert state.meta["version"] == 0
    assert state.beliefs == {}


def test_promote_observation_to_patch_creates_belief_patch_with_provenance():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )

    patch = promote_observation_to_patch(
        observation,
        belief_key="tool.read_docs.hits",
    )

    assert patch.section == "beliefs"
    assert patch.key == "tool.read_docs.hits"
    assert patch.op == "set"
    assert patch.value == {
        "content": {"hits": 2},
        "confidence": 0.8,
        "provenance": ["tool:read_docs", "call:toolcall_1"],
        "source_tool": "read_docs",
        "call_id": "toolcall_1",
        "evidence_weight": 1.0,
        "evidence_count": 1,
        "evidence_history": [
            {
                "call_id": "toolcall_1",
                "source_tool": "read_docs",
                "confidence": 0.8,
                "evidence_weight": 1.0,
            }
        ],
    }


def test_promote_observation_to_patch_rejects_empty_belief_key():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )

    with pytest.raises(ValueError, match="belief_key cannot be empty"):
        promote_observation_to_patch(observation, belief_key=" ")


def test_promoted_observation_patch_still_requires_policy_and_replay():
    from cee_core import EventLog, build_transition_for_patch

    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )
    patch = promote_observation_to_patch(
        observation,
        belief_key="tool.read_docs.hits",
    )
    event = build_transition_for_patch(patch, actor="observation_promoter")
    log = EventLog()

    log.append(event)
    state = log.replay_state()

    assert event.policy_decision.verdict == "allow"
    assert state.beliefs["tool.read_docs.hits"]["content"] == {"hits": 2}
    assert state.beliefs["tool.read_docs.hits"]["confidence"] == 0.8
    assert state.meta["version"] == 1
