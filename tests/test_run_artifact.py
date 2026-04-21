import pytest

from cee_core import (
    DomainPluginPack,
    RUN_ARTIFACT_SCHEMA_VERSION,
    RunArtifact,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
    run_result_to_artifact,
)
from cee_core.world_state import WorldState


def test_run_artifact_from_run_result_captures_counts_and_state():
    result = execute_task("update the project belief summary")

    artifact = run_result_to_artifact(result)

    assert artifact.task == result.task
    assert artifact.plan == result.plan
    assert artifact.narration_lines[0] == "Received task: update the project belief summary"
    assert artifact.allowed_count == 4
    assert artifact.blocked_count == 0
    assert artifact.approval_required_count == 1
    assert artifact.denied_count == 0
    assert artifact.world_state_snapshot is not None


def test_run_artifact_dict_round_trip():
    result = execute_task("analyze project risk")
    artifact = run_result_to_artifact(result)

    payload = artifact.to_dict()
    restored = RunArtifact.from_dict(payload)

    assert payload["schema_version"] == RUN_ARTIFACT_SCHEMA_VERSION
    assert restored == artifact


def test_run_artifact_json_round_trip():
    result = execute_task("analyze project risk")
    artifact = run_result_to_artifact(result)

    restored = RunArtifact.loads(artifact.dumps())

    assert restored == artifact


def test_run_artifact_includes_narration_lines():
    result = execute_task("analyze project risk")

    artifact = run_result_to_artifact(result)

    assert artifact.narration_lines[0] == "Received task: analyze project risk"
    assert artifact.narration_lines[1] == "Selected next action: propose_plan"
    assert len(artifact.narration_lines) >= 2


def test_run_artifact_replay_reconstructs_world_state():
    result = execute_task("update the project belief summary")
    artifact = run_result_to_artifact(result)

    assert artifact.world_state_snapshot is not None
    ws = WorldState.from_dict(artifact.world_state_snapshot)
    assert result.world_state is not None
    assert ws == result.world_state


def test_run_artifact_json_round_trip_preserves_world_state():
    result = execute_task("analyze project risk")
    artifact = run_result_to_artifact(result)

    restored = RunArtifact.loads(artifact.dumps())

    if artifact.world_state_snapshot is not None:
        assert restored.world_state_snapshot is not None
        ws_original = WorldState.from_dict(artifact.world_state_snapshot)
        ws_restored = WorldState.from_dict(restored.world_state_snapshot)
        assert ws_original == ws_restored


def test_run_artifact_rejects_missing_schema_version():
    result = execute_task("analyze project risk")
    payload = run_result_to_artifact(result).to_dict()
    payload.pop("schema_version")

    with pytest.raises(ValueError):
        RunArtifact.from_dict(payload)


def test_run_artifact_rejects_non_object_json():
    with pytest.raises(ValueError):
        RunArtifact.loads("[]")


def test_run_artifact_captures_domain_tightened_decisions():
    """Artifact faithfully records domain-overlay policy decisions."""
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )
    result = execute_task_in_domain("update the project belief summary", domain_ctx)

    artifact = run_result_to_artifact(result)

    assert artifact.allowed_count == 3
    assert artifact.denied_count == 1
    assert artifact.approval_required_count == 1
    assert artifact.blocked_count == 1
    assert artifact.task.domain_name == "construction-site"
    restored = RunArtifact.loads(artifact.dumps())
    assert restored.denied_count == artifact.denied_count
    assert restored.task.domain_name == artifact.task.domain_name
