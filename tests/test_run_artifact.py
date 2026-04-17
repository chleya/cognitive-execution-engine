import pytest

from cee_core import (
    DomainPluginPack,
    RUN_ARTIFACT_SCHEMA_VERSION,
    RunArtifact,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
    replay_run_artifact_json,
    run_result_to_artifact,
)


def test_run_artifact_from_run_result_captures_counts_and_state():
    result = execute_task("update the project belief summary")

    artifact = run_result_to_artifact(result)

    assert artifact.task == result.task
    assert artifact.plan == result.plan
    assert artifact.narration_lines[0] == "Received task: update the project belief summary"
    assert artifact.allowed_count == 4
    assert artifact.blocked_count == 1
    assert artifact.approval_required_count == 1
    assert artifact.denied_count == 0
    assert artifact.replayed_state_snapshot == result.replayed_state.snapshot()


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

    assert artifact.narration_lines == (
        "Received task: analyze project risk",
        "Selected next action: propose_plan",
        f"Evaluated state patch: goals.active (allow)",
        f"Evaluated state patch: beliefs.task.{result.task.task_id}.objective (allow)",
        f"Evaluated state patch: beliefs.task.{result.task.task_id}.domain_name (allow)",
        "Evaluated state patch: memory.working (allow)",
    )


def test_run_artifact_replay_reconstructs_state():
    result = execute_task("update the project belief summary")
    artifact = run_result_to_artifact(result)

    replayed = artifact.replay_state()

    assert replayed.snapshot() == result.replayed_state.snapshot()
    assert "last_medium_or_high_risk_task" not in replayed.self_model


def test_replay_run_artifact_json_reconstructs_state():
    result = execute_task("analyze project risk")
    artifact_json = run_result_to_artifact(result).dumps()

    replayed = replay_run_artifact_json(artifact_json)

    assert replayed.snapshot() == result.replayed_state.snapshot()


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

    # Medium-risk: goals(allow), beliefs×2(allow), memory(deny), self_model(requires_approval)
    # allowed=3, denied=1(memory), requires_approval=1(self_model)
    # blocked=2 (both memory and self_model: blocked = verdict in {deny, requires_approval})
    assert artifact.allowed_count == 3
    assert artifact.denied_count == 1
    assert artifact.approval_required_count == 1
    assert artifact.blocked_count == 2
    # TaskSpec carries domain_name into artifact
    assert artifact.task.domain_name == "construction-site"
    # JSON round-trip preserves counts
    restored = RunArtifact.loads(artifact.dumps())
    assert restored.denied_count == artifact.denied_count
    assert restored.task.domain_name == artifact.task.domain_name
