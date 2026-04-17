"""Stage-gate readiness checks for machine-readable handoff state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffStageResult:
    """One stage-gate readiness result."""

    stage: str
    status: str
    reasons: tuple[str, ...]


def assess_handoff_stage_gates(
    payload: dict[str, object],
) -> tuple[HandoffStageResult, ...]:
    """Assess whether each declared stage gate is ready from the handoff state."""

    stage_gates = payload.get("stage_gates")
    if not isinstance(stage_gates, list):
        return ()

    results: list[HandoffStageResult] = []
    for stage in stage_gates:
        if not isinstance(stage, str) or not stage.strip():
            continue
        reasons = _reasons_for_stage(stage, payload)
        results.append(
            HandoffStageResult(
                stage=stage,
                status="ready" if not reasons else "blocked",
                reasons=tuple(reasons),
            )
        )
    return tuple(results)


def _reasons_for_stage(stage: str, payload: dict[str, object]) -> list[str]:
    current_task = payload.get("current_task")
    control_philosophy = payload.get("control_philosophy")
    primary_files = payload.get("primary_files")
    allowed_files = payload.get("allowed_files")
    required_checks = payload.get("required_checks")
    success_predicates = payload.get("success_predicates")
    failure_predicates = payload.get("failure_predicates")
    global_acceptance_gates = payload.get("global_acceptance_gates")
    red_line_rules = payload.get("red_line_rules")
    task_packet = payload.get("task_packet")
    claim_metadata = payload.get("claim_metadata")
    execution_mode = payload.get("execution_mode")
    fallback_mode = payload.get("fallback_mode")
    expansion_rule = payload.get("expansion_rule")

    reasons: list[str] = []

    if stage == "read_state":
        if not isinstance(payload.get("repo_path"), str):
            reasons.append("repo_path is missing")
        if not isinstance(current_task, dict) or not isinstance(
            current_task.get("goal"), str
        ):
            reasons.append("current_task.goal is missing")
        if not _is_string_list(control_philosophy):
            reasons.append("control_philosophy is missing")
        if not isinstance(task_packet, dict):
            reasons.append("task_packet is missing")
        if not isinstance(claim_metadata, dict):
            reasons.append("claim_metadata is missing")
    elif stage == "restate_scope":
        if not isinstance(execution_mode, str):
            reasons.append("execution_mode is missing")
        if not _is_string_list(primary_files):
            reasons.append("primary_files is missing")
        if not _is_string_list(payload.get("forbidden_scope")):
            reasons.append("forbidden_scope is missing")
        if not _is_string_list(required_checks):
            reasons.append("required_checks is missing")
        if not _is_string_list(red_line_rules):
            reasons.append("red_line_rules is missing")
    elif stage == "inspect_minimum_context":
        if not _is_string_list(primary_files):
            reasons.append("primary_files is missing")
        effective_allowed = allowed_files if _is_string_list(allowed_files) else primary_files
        if _is_string_list(primary_files) and _is_string_list(effective_allowed):
            missing = [item for item in primary_files if item not in effective_allowed]
            if missing:
                reasons.append("primary_files fall outside allowed_files")
        if isinstance(task_packet, dict):
            artifact_paths = task_packet.get("artifact_paths")
            if not _is_string_list(artifact_paths):
                reasons.append("task_packet.artifact_paths is missing")
    elif stage == "edit_if_needed":
        if not isinstance(execution_mode, str):
            reasons.append("execution_mode is missing")
        if not isinstance(expansion_rule, str) or not expansion_rule.strip():
            reasons.append("expansion_rule is missing")
        if execution_mode in ("diagnose_only", "explore"):
            reasons.append(f"execution_mode {execution_mode} does not allow edits")
    elif stage == "focused_verify":
        if not _contains_check(required_checks, "tests\\test_handoff_validator.py"):
            reasons.append("focused verification command is missing")
    elif stage == "full_verify":
        if not _contains_check(required_checks, "python -m pytest -q"):
            reasons.append("full verification command is missing")
    elif stage == "emit_handoff_report":
        if not _contains_entry(success_predicates, "handoff report shows Ready: yes"):
            reasons.append("success_predicates does not require a ready handoff report")
        if not _contains_entry(success_predicates, "handoff report warning count == 0"):
            reasons.append("success_predicates does not require a clean warning count")
        if not isinstance(fallback_mode, str):
            reasons.append("fallback_mode is missing")
        if not _contains_entry(failure_predicates, "fails twice"):
            reasons.append("failure_predicates does not encode repeated-failure recovery")
        if not _contains_entry(
            global_acceptance_gates, "stage_gates all report ready"
        ):
            reasons.append("global_acceptance_gates does not require stage-gate readiness")
        if isinstance(claim_metadata, dict):
            scope = claim_metadata.get("validation_scope")
            if not isinstance(scope, str) or not scope.strip():
                reasons.append("claim_metadata.validation_scope is missing")
    else:
        reasons.append(f"unknown stage gate: {stage}")

    return reasons


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _contains_check(checks: object, expected: str) -> bool:
    return _contains_entry(checks, expected)


def _contains_entry(values: object, expected_fragment: str) -> bool:
    if not isinstance(values, list):
        return False
    return any(
        isinstance(item, str) and expected_fragment in item for item in values
    )
