import pytest

from cee_core import (
    Event,
    dumps_event_payloads,
    execute_task,
    loads_event_payloads,
    replay_event_payload_artifact,
)


def test_dump_and_load_event_payloads_round_trip():
    result = execute_task("analyze project risk")

    artifact = dumps_event_payloads(result.event_log.all())
    payloads = loads_event_payloads(artifact)

    assert isinstance(artifact, str)
    assert len(payloads) == len(result.event_log.all())
    assert payloads[0]["event_type"] == "task.received"


def test_replay_event_payload_artifact_reconstructs_state():
    result = execute_task("analyze project risk")
    artifact = dumps_event_payloads(result.event_log.all())

    replayed = replay_event_payload_artifact(artifact)

    assert replayed.snapshot() == result.replayed_state.snapshot()


def test_replay_event_payload_artifact_preserves_blocked_as_audit_only():
    result = execute_task("update the project belief summary")
    artifact = dumps_event_payloads(result.event_log.all())

    replayed = replay_event_payload_artifact(artifact)

    assert replayed.snapshot() == result.replayed_state.snapshot()
    assert "last_medium_or_high_risk_task" not in replayed.self_model


def test_load_event_payloads_rejects_non_array_json():
    with pytest.raises(ValueError):
        loads_event_payloads('{"event_type":"task.received"}')


def test_load_event_payloads_rejects_non_object_entries():
    with pytest.raises(ValueError):
        loads_event_payloads('[1, 2, 3]')


def test_dump_event_payloads_supports_plain_audit_events():
    event = Event(event_type="audit.note", payload={"message": "hello"})

    artifact = dumps_event_payloads([event])
    payloads = loads_event_payloads(artifact)

    assert payloads[0]["event_type"] == "audit.note"
    assert payloads[0]["payload"] == {"message": "hello"}

