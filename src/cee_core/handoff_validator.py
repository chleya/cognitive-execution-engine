"""Validation helpers for machine-readable handoff state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HandoffValidationResult:
    """Result of validating a handoff state document."""

    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def load_handoff_state(path: str | Path) -> dict[str, object]:
    """Load a handoff state JSON document."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("handoff_state must be a JSON object")
    return payload


def validate_handoff_state(payload: dict[str, object]) -> HandoffValidationResult:
    """Validate required handoff fields and simple consistency rules."""

    errors: list[str] = []
    warnings: list[str] = []

    _require_non_empty_string(payload, "repo_path", errors)
    validation = _require_object(payload, "validation", errors)
    if validation is not None:
        _require_non_empty_string(validation, "command", errors, prefix="validation.")
        _require_non_empty_string(validation, "result", errors, prefix="validation.")

    current_task = _require_object(payload, "current_task", errors)
    if current_task is not None:
        _require_non_empty_string(current_task, "goal", errors, prefix="current_task.")
        if not isinstance(current_task.get("do_not_expand_scope"), bool):
            errors.append("current_task.do_not_expand_scope must be a boolean")

    control_philosophy = _require_string_list(payload, "control_philosophy", errors)
    task_packet = _require_object(payload, "task_packet", errors)
    if task_packet is not None:
        _require_non_empty_string(task_packet, "task_id", errors, prefix="task_packet.")
        _require_non_empty_string(task_packet, "owner", errors, prefix="task_packet.")
        _require_string_list(task_packet, "commands", errors, prefix="task_packet.")
        _require_string_list(task_packet, "artifact_paths", errors, prefix="task_packet.")
        _require_string_list(task_packet, "acceptance_gates", errors, prefix="task_packet.")
        _require_string_list(task_packet, "hold_conditions", errors, prefix="task_packet.")
        _require_non_empty_string(task_packet, "fallback_plan", errors, prefix="task_packet.")
        _require_string_list(task_packet, "required_update_format", errors, prefix="task_packet.")

    claim_metadata = _require_object(payload, "claim_metadata", errors)
    if claim_metadata is not None:
        _require_non_empty_string(
            claim_metadata, "validation_source", errors, prefix="claim_metadata."
        )
        _require_non_empty_string(
            claim_metadata, "validation_scope", errors, prefix="claim_metadata."
        )
        _require_non_empty_string(
            claim_metadata, "cost_model", errors, prefix="claim_metadata."
        )
        if not isinstance(claim_metadata.get("oracle_assumption"), bool):
            errors.append("claim_metadata.oracle_assumption must be a boolean")
        _require_string_list(claim_metadata, "notes", errors, prefix="claim_metadata.")

    red_line_rules = _require_string_list(payload, "red_line_rules", errors)
    _require_choice(
        payload,
        "execution_mode",
        {"validate_only", "handoff_sync", "focused_fix", "diagnose_only", "explore"},
        errors,
    )
    primary_files = _require_string_list(payload, "primary_files", errors)
    allowed_files = payload.get("allowed_files")
    if allowed_files is None:
        allowed_files = primary_files
    elif not isinstance(allowed_files, list) or not all(
        isinstance(item, str) and item.strip() for item in allowed_files
    ):
        errors.append("allowed_files must be a non-empty list of strings")
        allowed_files = None
    forbidden_scope = _require_string_list(payload, "forbidden_scope", errors)
    required_checks = _require_string_list(payload, "required_checks", errors)
    success_predicates = _require_string_list(payload, "success_predicates", errors)
    failure_predicates = _require_string_list(payload, "failure_predicates", errors)
    stage_gates = _require_string_list(payload, "stage_gates", errors)
    _require_non_empty_string(payload, "expansion_rule", errors)
    _require_choice(
        payload,
        "fallback_mode",
        {"diagnose_only", "handoff_sync", "validate_only"},
        errors,
    )
    global_acceptance_gates = _require_string_list(
        payload, "global_acceptance_gates", errors
    )
    stop_conditions = _require_string_list(payload, "stop_conditions", errors)
    _require_string_list(payload, "source_of_truth", errors)
    _require_string_list(payload, "current_architecture", errors)
    _require_string_list(payload, "already_completed", errors)
    _require_string_list(payload, "first_command_sequence", errors)

    next_task_candidates = payload.get("next_task_candidates")
    if not isinstance(next_task_candidates, list):
        errors.append("next_task_candidates must be a list")
    elif next_task_candidates:
        for idx, candidate in enumerate(next_task_candidates):
            if not isinstance(candidate, dict):
                errors.append(f"next_task_candidates[{idx}] must be an object")
            else:
                _require_non_empty_string(
                    candidate, "task_id", errors, prefix=f"next_task_candidates[{idx}]."
                )
                _require_non_empty_string(
                    candidate, "goal", errors, prefix=f"next_task_candidates[{idx}]."
                )

    module_map = payload.get("module_map")
    if not isinstance(module_map, dict):
        errors.append("module_map must be an object")
    elif not module_map:
        errors.append("module_map must be a non-empty object")
    elif not all(
        isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
        for k, v in module_map.items()
    ):
        errors.append("module_map keys and values must be non-empty strings")

    dependency_map = payload.get("dependency_map")
    if dependency_map is not None:
        if not isinstance(dependency_map, dict):
            errors.append("dependency_map must be an object")
        elif not all(
            isinstance(k, str) and k.strip() and isinstance(v, list)
            for k, v in dependency_map.items()
        ):
            errors.append("dependency_map keys must be strings and values must be lists")
        elif isinstance(module_map, dict) and module_map:
            missing_from_module_map = [
                k for k in dependency_map if k not in module_map
            ]
            if missing_from_module_map:
                warnings.append(
                    f"dependency_map has entries not in module_map: "
                    f"{', '.join(missing_from_module_map[:3])}"
                )

    if primary_files is not None and allowed_files is not None:
        missing_primary = [item for item in primary_files if item not in allowed_files]
        if missing_primary:
            errors.append(
                "primary_files must be included in allowed_files: "
                + ", ".join(missing_primary)
            )

    if task_packet is not None and primary_files is not None:
        artifact_paths = task_packet.get("artifact_paths")
        if isinstance(artifact_paths, list):
            missing_artifacts = [
                item for item in artifact_paths if item not in primary_files
            ]
            if missing_artifacts:
                errors.append(
                    "task_packet.artifact_paths must be included in primary_files: "
                    + ", ".join(missing_artifacts)
                )

    if allowed_files is not None and forbidden_scope is not None:
        forbidden_file_entries = {
            _normalize_path_like(item) for item in forbidden_scope if _looks_like_file_path(item)
        }
        overlap = sorted(
            original
            for original in allowed_files
            if _normalize_path_like(original) in forbidden_file_entries
        )
        if overlap:
            errors.append(
                "allowed_files and forbidden_scope overlap: " + ", ".join(overlap)
            )

    if stage_gates is not None:
        _validate_stage_gates(stage_gates, errors)

    if control_philosophy is not None and len(control_philosophy) < 4:
        warnings.append("control_philosophy is thin; weaker models may lack decision rationale")

    if success_predicates is not None and not any("Ready: yes" in item for item in success_predicates):
        warnings.append("success_predicates does not explicitly require a ready handoff report")

    if failure_predicates is not None and not any("fails twice" in item for item in failure_predicates):
        warnings.append("failure_predicates does not explicitly encode a repeated-failure fallback")

    if red_line_rules is not None and not any(
        "runtime authority boundaries" in item for item in red_line_rules
    ):
        warnings.append("red_line_rules does not explicitly protect runtime authority boundaries")

    if global_acceptance_gates is not None and not any(
        "stage_gates all report ready" in item for item in global_acceptance_gates
    ):
        warnings.append("global_acceptance_gates does not explicitly require stage-gate readiness")

    repo_path = payload.get("repo_path")
    if isinstance(repo_path, str) and repo_path.strip():
        _validate_human_mirror(
            Path(repo_path) / "NEXT_AGENT_START_HERE.md",
            payload,
            errors,
            warnings,
        )

    if required_checks is not None and not any("pytest" in check for check in required_checks):
        warnings.append("required_checks does not include a pytest command")

    if allowed_files is not None and len(allowed_files) > 10:
        warnings.append("allowed_files is broad; weaker models may drift")

    if isinstance(repo_path, str) and repo_path.strip():
        mirror_path = Path(repo_path) / "NEXT_AGENT_START_HERE.md"
        if mirror_path.exists():
            mirror_text = mirror_path.read_text(encoding="utf-8")
            _check_mirror_duplicates(mirror_text, warnings)

    return HandoffValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_handoff_state_file(path: str | Path) -> HandoffValidationResult:
    """Load and validate one handoff state file."""

    return validate_handoff_state(load_handoff_state(path))


def _require_object(
    payload: dict[str, object],
    key: str,
    errors: list[str],
) -> dict[str, object] | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return None
    return value  # type: ignore[return-value]


def _require_non_empty_string(
    payload: dict[str, object],
    key: str,
    errors: list[str],
    *,
    prefix: str = "",
) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}{key} must be a non-empty string")


def _require_choice(
    payload: dict[str, object],
    key: str,
    choices: set[str],
    errors: list[str],
) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(sorted(choices))
        errors.append(f"{key} must be one of: {allowed}")


def _require_string_list(
    payload: dict[str, object],
    key: str,
    errors: list[str],
    *,
    prefix: str = "",
) -> list[str] | None:
    value = payload.get(key)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"{prefix}{key} must be a non-empty list of strings")
        return None
    return value  # type: ignore[return-value]


def _validate_human_mirror(
    mirror_path: Path,
    payload: dict[str, object],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not mirror_path.exists():
        warnings.append(f"human mirror file is missing: {mirror_path.name}")
        return

    text = mirror_path.read_text(encoding="utf-8")
    normalized_text = _normalize_text(text)
    validation = payload.get("validation")
    current_task = payload.get("current_task")

    if isinstance(validation, dict):
        result = validation.get("result")
        if isinstance(result, str) and result.strip() and _normalize_text(result) not in normalized_text:
            errors.append(
                f"{mirror_path.name} does not mirror validation.result from handoff_state.json"
            )

    if isinstance(current_task, dict):
        goal = current_task.get("goal")
        if isinstance(goal, str) and goal.strip() and _normalize_text(goal) not in normalized_text:
            errors.append(
                f"{mirror_path.name} does not mirror current_task.goal from handoff_state.json"
            )

    scalar_fields = ("execution_mode", "expansion_rule", "fallback_mode")
    for key in scalar_fields:
        value = payload.get(key)
        if isinstance(value, str) and value.strip() and _normalize_text(value) not in normalized_text:
            errors.append(f"{mirror_path.name} does not mirror {key} from handoff_state.json")

    task_packet = payload.get("task_packet")
    if isinstance(task_packet, dict):
        for key in ("task_id", "owner", "fallback_plan"):
            value = task_packet.get(key)
            if isinstance(value, str) and value.strip() and _normalize_text(value) not in normalized_text:
                errors.append(
                    f"{mirror_path.name} does not mirror task_packet.{key} from handoff_state.json"
                )

    claim_metadata = payload.get("claim_metadata")
    if isinstance(claim_metadata, dict):
        for key in ("validation_source", "validation_scope", "cost_model"):
            value = claim_metadata.get(key)
            if isinstance(value, str) and value.strip() and _normalize_text(value) not in normalized_text:
                errors.append(
                    f"{mirror_path.name} does not mirror claim_metadata.{key} from handoff_state.json"
                )

    for key in (
        "control_philosophy",
        "primary_files",
        "allowed_files",
        "required_checks",
        "success_predicates",
        "failure_predicates",
        "stage_gates",
        "red_line_rules",
        "global_acceptance_gates",
    ):
        values = payload.get(key)
        if isinstance(values, list):
            missing = [
                value
                for value in values
                if isinstance(value, str)
                and value.strip()
                and _normalize_text(value) not in normalized_text
            ]
            if missing:
                errors.append(
                    f"{mirror_path.name} is missing {key}: " + ", ".join(missing)
                )

    if isinstance(task_packet, dict):
        for key in (
            "commands",
            "artifact_paths",
            "acceptance_gates",
            "hold_conditions",
            "required_update_format",
        ):
            values = task_packet.get(key)
            if isinstance(values, list):
                missing = [
                    value
                    for value in values
                    if isinstance(value, str)
                    and value.strip()
                    and _normalize_text(value) not in normalized_text
                ]
                if missing:
                    errors.append(
                        f"{mirror_path.name} is missing task_packet.{key}: "
                        + ", ".join(missing)
                    )

    if isinstance(claim_metadata, dict):
        values = claim_metadata.get("notes")
        if isinstance(values, list):
            missing = [
                value
                for value in values
                if isinstance(value, str)
                and value.strip()
                and _normalize_text(value) not in normalized_text
            ]
            if missing:
                errors.append(
                    f"{mirror_path.name} is missing claim_metadata.notes: "
                    + ", ".join(missing)
                )

    next_task_candidates = payload.get("next_task_candidates")
    if isinstance(next_task_candidates, list) and next_task_candidates:
        for candidate in next_task_candidates:
            if isinstance(candidate, dict):
                goal = candidate.get("goal")
                if isinstance(goal, str) and goal.strip() and _normalize_text(goal) not in normalized_text:
                    errors.append(
                        f"{mirror_path.name} is missing next_task_candidates goal: {goal}"
                    )
    elif isinstance(next_task_candidates, list) and not next_task_candidates:
        if "None" not in normalized_text and "next task candidates" not in normalized_text.lower():
            warnings.append(
                f"{mirror_path.name} does not mention that next_task_candidates is empty"
            )

    module_map = payload.get("module_map")
    if isinstance(module_map, dict) and module_map:
        module_names = list(module_map.keys())
        missing_modules = [
            name for name in module_names
            if _normalize_text(name) not in normalized_text
        ]
        if len(missing_modules) > len(module_names) // 2:
            warnings.append(
                f"{mirror_path.name} is missing most module_map entries; "
                f"weaker models may lack code navigation"
            )


def _looks_like_file_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith((".py", ".md", ".json", ".toml"))


def _normalize_path_like(value: str) -> str:
    return value.replace("\\", "/").lower()


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("`", "").split())


def _validate_stage_gates(stage_gates: list[str], errors: list[str]) -> None:
    expected_order = (
        "read_state",
        "restate_scope",
        "inspect_minimum_context",
        "edit_if_needed",
        "focused_verify",
        "full_verify",
        "emit_handoff_report",
    )
    if stage_gates != list(expected_order):
        errors.append(
            "stage_gates must exactly match the expected gated execution order: "
            + ", ".join(expected_order)
        )


def _check_mirror_duplicates(mirror_text: str, warnings: list[str]) -> None:
    in_code_block = False
    content_lines: list[str] = []
    for line in mirror_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("- "):
            continue
        if stripped:
            content_lines.append(stripped)
    seen: dict[str, int] = {}
    for line in content_lines:
        normalized = _normalize_text(line)
        if normalized in seen:
            seen[normalized] += 1
        else:
            seen[normalized] = 1
    duplicates = {line: count for line, count in seen.items() if count > 1 and len(line) > 30}
    if duplicates:
        preview = next(iter(duplicates))
        warnings.append(
            f"NEXT_AGENT_START_HERE.md has {len(duplicates)} duplicate line(s); "
            f"weaker models may be confused by repeated content, e.g.: {preview[:80]}"
        )
