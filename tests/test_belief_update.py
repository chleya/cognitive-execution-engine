from cee_core import ObservationCandidate, build_belief_payload, promote_observation_to_belief_patch


def test_build_belief_payload_without_prior_uses_observation_confidence():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )

    payload = build_belief_payload(observation)

    assert payload["confidence"] == 0.8
    assert payload["evidence_count"] == 1
    assert payload["evidence_weight"] == 1.0


def test_build_belief_payload_with_prior_updates_confidence_by_weight():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_2",
        content={"hits": 3},
        confidence=0.9,
        evidence_weight=2.0,
        provenance=("tool:read_docs", "call:toolcall_2"),
    )
    prior = {
        "content": {"hits": 2},
        "confidence": 0.6,
        "provenance": ["tool:read_docs", "call:toolcall_1"],
        "source_tool": "read_docs",
        "call_id": "toolcall_1",
        "evidence_weight": 1.0,
        "evidence_count": 1,
        "evidence_history": [
            {
                "call_id": "toolcall_1",
                "source_tool": "read_docs",
                "confidence": 0.6,
                "evidence_weight": 1.0,
            }
        ],
    }

    payload = build_belief_payload(observation, prior_belief=prior)

    assert payload["confidence"] == 0.8
    assert payload["evidence_count"] == 3
    assert len(payload["evidence_history"]) == 2


def test_promote_observation_to_belief_patch_rejects_empty_key():
    observation = ObservationCandidate(
        source_tool="read_docs",
        call_id="toolcall_1",
        content={"hits": 2},
        confidence=0.8,
        evidence_weight=1.0,
        provenance=("tool:read_docs", "call:toolcall_1"),
    )

    try:
        promote_observation_to_belief_patch(observation, belief_key=" ")
    except ValueError as exc:
        assert "belief_key cannot be empty" in str(exc)
    else:
        raise AssertionError("expected empty belief key to be rejected")
