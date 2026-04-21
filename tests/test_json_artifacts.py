import pytest

from cee_core import (
    Event,
    dumps_event_payloads,
    execute_task,
    loads_event_payloads,
)
from cee_core.run_artifact import run_result_to_artifact
from cee_core.world_state import WorldState


def test_dump_and_load_event_payloads_round_trip():
    result = execute_task("analyze project risk")

    artifact = dumps_event_payloads(result.event_log.all())
    payloads = loads_event_payloads(artifact)

    assert isinstance(artifact, str)
    assert len(payloads) == len(result.event_log.all())
    assert payloads[0]["event_type"] == "task.received"


def test_artifact_world_state_snapshot_matches_result():
    result = execute_task("analyze project risk")

    artifact = run_result_to_artifact(result)

    assert artifact.world_state_snapshot is not None
    artifact_ws = WorldState.from_dict(artifact.world_state_snapshot)
    assert result.world_state is not None
    assert artifact_ws == result.world_state


def test_artifact_world_state_preserves_blocked_as_audit_only():
    result = execute_task("update the project belief summary")

    artifact = run_result_to_artifact(result)

    assert artifact.world_state_snapshot is not None
    artifact_ws = WorldState.from_dict(artifact.world_state_snapshot)
    assert result.world_state is not None
    assert artifact_ws == result.world_state


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
