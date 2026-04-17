import json
import shutil
from pathlib import Path
from uuid import uuid4

from cee_core import (
    build_handoff_report,
    load_handoff_state,
    validate_handoff_state,
    validate_handoff_state_file,
)


def test_validate_handoff_state_file_accepts_current_repo_file():
    result = validate_handoff_state_file("F:\\cognitive-execution-engine\\handoff_state.json")

    assert result.is_valid is True
    assert result.errors == ()


def test_validate_handoff_state_rejects_missing_goal():
    payload = {
        "repo_path": "F:\\cognitive-execution-engine",
        "validation": {"command": "python -m pytest -q", "result": "204 passed, 2 skipped"},
        "current_architecture": ["TaskSpec -> ReasoningStep -> PlanSpec"],
        "already_completed": ["narration persisted into RunArtifact"],
        "current_task": {"goal": " ", "do_not_expand_scope": True},
        "execution_mode": "validate_only",
        "primary_files": ["src/cee_core/run_artifact.py"],
        "allowed_files": ["src/cee_core/run_artifact.py"],
        "expansion_rule": "Only expand scope if a focused failure proves it is needed.",
        "forbidden_scope": ["do not change policy semantics"],
        "required_checks": ["python -m pytest -q"],
        "success_predicates": ["handoff report shows Ready: yes"],
        "failure_predicates": ["focused validation fails twice on the same issue"],
        "stage_gates": [
            "read_state",
            "restate_scope",
            "inspect_minimum_context",
            "edit_if_needed",
            "focused_verify",
            "full_verify",
            "emit_handoff_report",
        ],
        "fallback_mode": "diagnose_only",
        "stop_conditions": ["tests fail for unrelated reasons"],
        "source_of_truth": ["README.md"],
        "first_command_sequence": ["cd F:\\cognitive-execution-engine"],
    }

    result = validate_handoff_state(payload)

    assert result.is_valid is False
    assert "current_task.goal must be a non-empty string" in result.errors


def test_validate_handoff_state_rejects_overlap_between_allowed_and_forbidden():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["forbidden_scope"] = list(payload["forbidden_scope"]) + [  # type: ignore[index]
        "handoff_state.json"
    ]

    result = validate_handoff_state(payload)

    assert result.is_valid is False
    assert any("allowed_files and forbidden_scope overlap" in error for error in result.errors)


def test_build_handoff_report_mentions_ready_status():
    report = build_handoff_report("F:\\cognitive-execution-engine\\handoff_state.json")

    assert "Handoff Report" in report
    assert "Ready                        : yes" in report
    assert "Execution mode               : validate_only" in report
    assert "Task packet ID               : HANDOFF-VALIDATE-001" in report
    assert "Validation source            : local_pytest" in report
    assert "Control Philosophy" in report
    assert "Global gate count            :" in report
    assert "Stage Gates" in report
    assert "- focused_verify: ready" in report


def test_validate_handoff_state_rejects_stale_human_mirror():
    temp_dir = Path("F:\\cognitive-execution-engine\\tests") / f"_tmp_handoff_{uuid4().hex}"
    temp_dir.mkdir()
    try:
        mirror = temp_dir / "NEXT_AGENT_START_HERE.md"
        mirror.write_text(
            "# Next Agent Start Here\n\nValidation: 199 passed, 2 skipped\n",
            encoding="utf-8",
        )
        payload = {
            "repo_path": str(temp_dir),
            "validation": {"command": "python -m pytest -q", "result": "211 passed, 2 skipped"},
            "current_architecture": ["TaskSpec -> ReasoningStep -> PlanSpec"],
            "already_completed": ["handoff readiness report"],
            "current_task": {
                "goal": "No active implementation task is assigned. Validate current state and wait for the next explicit instruction.",
                "do_not_expand_scope": True,
            },
            "execution_mode": "validate_only",
            "primary_files": ["handoff_state.json", "NEXT_AGENT_START_HERE.md"],
            "allowed_files": ["handoff_state.json", "NEXT_AGENT_START_HERE.md"],
            "expansion_rule": "Only expand scope if a focused failure proves it is needed.",
            "forbidden_scope": ["do not change policy semantics"],
            "required_checks": ["python -m pytest -q tests\\test_handoff_validator.py"],
            "success_predicates": ["handoff report shows Ready: yes"],
            "failure_predicates": ["focused validation fails twice on the same issue"],
            "stage_gates": [
                "read_state",
                "restate_scope",
                "inspect_minimum_context",
                "edit_if_needed",
                "focused_verify",
                "full_verify",
                "emit_handoff_report",
            ],
            "fallback_mode": "diagnose_only",
            "stop_conditions": ["tests fail for reasons unrelated to the current task"],
            "source_of_truth": ["README.md"],
            "first_command_sequence": ["python -m pytest -q tests\\test_handoff_validator.py"],
        }

        result = validate_handoff_state(payload)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    assert result.is_valid is False
    assert any("NEXT_AGENT_START_HERE.md does not mirror validation.result" in error for error in result.errors)


def test_validate_handoff_state_rejects_incomplete_stage_gate_order():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["stage_gates"] = [  # type: ignore[index]
        "read_state",
        "focused_verify",
        "emit_handoff_report",
    ]

    result = validate_handoff_state(payload)

    assert result.is_valid is False
    assert any("stage_gates must exactly match the expected gated execution order" in error for error in result.errors)


def test_validate_handoff_state_rejects_missing_task_packet_owner():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    task_packet = dict(payload["task_packet"])  # type: ignore[index]
    task_packet["owner"] = " "
    payload["task_packet"] = task_packet

    result = validate_handoff_state(payload)

    assert result.is_valid is False
    assert "task_packet.owner must be a non-empty string" in result.errors


def test_validate_handoff_state_rejects_missing_claim_metadata_scope():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    claim_metadata = dict(payload["claim_metadata"])  # type: ignore[index]
    claim_metadata["validation_scope"] = " "
    payload["claim_metadata"] = claim_metadata

    result = validate_handoff_state(payload)

    assert result.is_valid is False
    assert "claim_metadata.validation_scope must be a non-empty string" in result.errors
