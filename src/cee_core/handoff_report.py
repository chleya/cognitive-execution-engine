"""Reporting helpers for handoff readiness."""

from __future__ import annotations

from pathlib import Path

from .handoff_stage_checker import assess_handoff_stage_gates
from .handoff_validator import (
    HandoffValidationResult,
    load_handoff_state,
    validate_handoff_state_file,
)


def build_handoff_report(path: str | Path) -> str:
    """Build a compact handoff readiness report for one state file."""

    state = load_handoff_state(path)
    result = validate_handoff_state_file(path)
    return render_handoff_report(result, path=path, state=state)


def render_handoff_report(
    result: HandoffValidationResult,
    *,
    path: str | Path,
    state: dict[str, object] | None = None,
) -> str:
    """Render a human-readable handoff validation report."""

    lines = [
        "Handoff Report",
        f"Path                         : {Path(path)}",
        f"Ready                        : {'yes' if result.is_valid else 'no'}",
        f"Error count                  : {len(result.errors)}",
        f"Warning count                : {len(result.warnings)}",
    ]
    if state is not None:
        execution_mode = state.get("execution_mode")
        fallback_mode = state.get("fallback_mode")
        primary_files = state.get("primary_files")
        stage_gates = state.get("stage_gates")
        success_predicates = state.get("success_predicates")
        failure_predicates = state.get("failure_predicates")
        control_philosophy = state.get("control_philosophy")
        red_line_rules = state.get("red_line_rules")
        global_acceptance_gates = state.get("global_acceptance_gates")
        task_packet = state.get("task_packet")
        claim_metadata = state.get("claim_metadata")
        lines.extend(
            [
                f"Execution mode               : {execution_mode}",
                f"Fallback mode                : {fallback_mode}",
                f"Primary file count           : {len(primary_files) if isinstance(primary_files, list) else 0}",
                f"Stage gate count             : {len(stage_gates) if isinstance(stage_gates, list) else 0}",
                f"Success predicate count      : {len(success_predicates) if isinstance(success_predicates, list) else 0}",
                f"Failure predicate count      : {len(failure_predicates) if isinstance(failure_predicates, list) else 0}",
                f"Control philosophy count     : {len(control_philosophy) if isinstance(control_philosophy, list) else 0}",
                f"Red-line rule count          : {len(red_line_rules) if isinstance(red_line_rules, list) else 0}",
                f"Global gate count            : {len(global_acceptance_gates) if isinstance(global_acceptance_gates, list) else 0}",
            ]
        )
        if isinstance(control_philosophy, list):
            lines.append("Control Philosophy")
            lines.extend(
                f"- {item}" for item in control_philosophy if isinstance(item, str)
            )
        if isinstance(task_packet, dict):
            lines.extend(
                [
                    f"Task packet ID               : {task_packet.get('task_id')}",
                    f"Task packet owner            : {task_packet.get('owner')}",
                ]
            )
        if isinstance(claim_metadata, dict):
            lines.extend(
                [
                    f"Validation source            : {claim_metadata.get('validation_source')}",
                    f"Validation scope             : {claim_metadata.get('validation_scope')}",
                    f"Oracle assumption            : {claim_metadata.get('oracle_assumption')}",
                ]
            )
        stage_results = assess_handoff_stage_gates(state)
        if stage_results:
            lines.append("Stage Gates")
            lines.extend(
                f"- {item.stage}: {item.status}"
                + (f" ({'; '.join(item.reasons)})" if item.reasons else "")
                for item in stage_results
            )
        if isinstance(task_packet, dict):
            lines.append("Task Packet")
            for key in (
                "commands",
                "artifact_paths",
                "acceptance_gates",
                "hold_conditions",
                "required_update_format",
            ):
                values = task_packet.get(key)
                if isinstance(values, list):
                    lines.extend(f"- {key}: {value}" for value in values)
            fallback_plan = task_packet.get("fallback_plan")
            if isinstance(fallback_plan, str):
                lines.append(f"Task packet fallback plan    : {fallback_plan}")
        if isinstance(claim_metadata, dict):
            notes = claim_metadata.get("notes")
            if isinstance(notes, list):
                lines.append("Claim Metadata Notes")
                lines.extend(f"- {note}" for note in notes if isinstance(note, str))
        next_task_candidates = state.get("next_task_candidates")
        if isinstance(next_task_candidates, list):
            lines.append(f"Next task candidate count    : {len(next_task_candidates)}")
            for candidate in next_task_candidates:
                if isinstance(candidate, dict):
                    lines.append(f"- {candidate.get('task_id')}: {candidate.get('goal')}")
        module_map = state.get("module_map")
        if isinstance(module_map, dict):
            lines.append(f"Module map entry count       : {len(module_map)}")
        dependency_map = state.get("dependency_map")
        if isinstance(dependency_map, dict):
            lines.append(f"Dependency map entry count   : {len(dependency_map)}")
    if result.errors:
        lines.append("Errors")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("Warnings")
        lines.extend(f"- {warning}" for warning in result.warnings)
    return "\n".join(lines)
