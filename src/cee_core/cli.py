"""Enhanced CLI for the Cognitive Execution Engine.

Adds:
1. Rich output formatting with progress display
2. Multiple output formats (text, json)
3. LLM integration support
4. Real-time execution monitoring
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .calibration import run_calibration_cycle
from .config import CEEConfig, load_config
from .approval import ApprovalGate, StaticApprovalProvider
from .event_log import EventLog
from .events import Event
from .handoff_report import build_handoff_report
from .handoff_validator import validate_handoff_state_file
from .runtime import execute_task, execute_task_in_domain
from .domain_context import DomainContext
from .world_state import WorldState
from .persistence import StateStore, save_world_state, load_world_state, load_world_state_from_file
from .run_artifact import run_result_to_artifact
from .tasks import TaskSpec
from .observability import ExecutionObserver, ExecutionPhase, DebugContext
from .import_export import ImportExportManager
from .llm_deliberation import (
    StaticLLMDeliberationCompiler,
    ProviderBackedDeliberationCompiler,
    deliberate_with_llm,
)
from .llm_provider import StaticLLMProvider, OpenAIProvider, get_api_key_from_env
from .tool_executor import SandboxedToolExecutor
from .report_generator import ReportGenerator
from .workflow import Workflow, WorkflowResult, StepResult


def _build_llm_provider(args: argparse.Namespace):
    """Build LLM provider based on CLI arguments."""
    provider_type = getattr(args, "llm_provider", "static")
    model = getattr(args, "model", None)

    if provider_type == "openai":
        api_key = get_api_key_from_env()
        model_name = model or "gpt-4o-mini"
        return OpenAIProvider(api_key=api_key, model_name=model_name)

    return StaticLLMProvider(response_text='{"summary": "static", "hypothesis": "static", "missing_information": [], "candidate_actions": ["propose_plan"], "chosen_action": "propose_plan", "rationale": "static provider", "stop_condition": "static"}')


def _format_task_result(result, event_count: int, output_format: str = "text") -> str:
    """Format task execution result."""

    ws = result.world_state

    if output_format == "json":
        data = {
            "task": {
                "objective": result.task.objective,
                "kind": result.task.kind,
                "risk_level": result.task.risk_level,
                "task_level": result.task.task_level,
            },
            "events": event_count,
            "allowed_transitions": result.allowed_count,
            "denied_transitions": len(result.denied_transitions),
            "approval_required": result.requires_approval_count,
            "redirect_proposed": result.redirect_proposed,
            "commitment_events": len(result.commitment_events),
            "revision_events": len(result.revision_events),
            "world_state": ws.to_dict() if ws else None,
        }
        return json.dumps(data, indent=2, default=str)

    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("Task Execution Result")
    lines.append("=" * 60)
    lines.append(f"  Objective   : {result.task.objective}")
    lines.append(f"  Kind        : {result.task.kind}")
    lines.append(f"  Risk Level  : {result.task.risk_level}")
    lines.append(f"  Task Level  : {result.task.task_level}")
    lines.append(f"")
    lines.append(f"  Events      : {event_count}")
    lines.append(f"  Allowed     : {result.allowed_count}")
    lines.append(f"  Denied      : {len(result.denied_transitions)}")
    lines.append(f"  Approval    : {result.requires_approval_count}")
    lines.append(f"  Redirect    : {result.redirect_proposed}")
    lines.append(f"  Commitments : {len(result.commitment_events)}")
    lines.append(f"  Revisions   : {len(result.revision_events)}")

    if ws is not None:
        lines.append(f"")
        lines.append(f"  World State :")
        lines.append(f"    ID        : {ws.state_id}")
        lines.append(f"    Goals     : {', '.join(ws.dominant_goals) if ws.dominant_goals else '(none)'}")
        lines.append(f"    Entities  : {len(ws.entities)}")
        lines.append(f"    Hypotheses: {len(ws.hypotheses)}")
        lines.append(f"    Anchored  : {len(ws.anchored_fact_summaries)}")
        lines.append(f"    Provenance: {len(ws.provenance_refs)} refs")

    lines.append(f"")
    lines.append(f"=" * 60)
    return "\n".join(lines)


def _cmd_run(args: argparse.Namespace, config: CEEConfig) -> None:
    """Run a task through the deterministic pipeline."""

    domain = DomainContext(domain_name=args.domain)
    log = EventLog()

    gate = None
    if args.auto_approve:
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    observer = None
    verbose = args.verbose or config.observability.verbose_logging
    if verbose:
        observer = ExecutionObserver(
            debug_context=DebugContext(verbose_logging=True)
        )
        observer.metrics.start_phase(ExecutionPhase.COMPILATION)

    result = execute_task_in_domain(
        args.task,
        domain,
        event_log=log,
        approval_gate=gate,
    )

    if observer is not None:
        observer.metrics.end_phase(ExecutionPhase.COMPILATION)

    artifact = run_result_to_artifact(result)

    event_count = len(list(log.all()))
    print(_format_task_result(result, event_count, output_format=args.output))

    if observer is not None:
        observer.export_metrics()

    if args.save:
        _save_run(args.save, artifact, log, result)


def _cmd_report(args: argparse.Namespace) -> None:
    if getattr(args, "exec_report", False):
        _cmd_exec_report(args)
        return

    state_path = args.state_file
    if not Path(state_path).exists():
        print(f"Error: {state_path} not found", file=sys.stderr)
        sys.exit(1)

    if args.output == "json":
        state_data = json.loads(Path(state_path).read_text(encoding="utf-8"))
        report = {
            "state": state_data,
            "report": build_handoff_report(state_path),
        }

        ws_path = Path(state_path).with_suffix(".world_state.json")
        if ws_path.exists():
            ws_data = json.loads(ws_path.read_text(encoding="utf-8"))
            report["world_state"] = ws_data

        print(json.dumps(report, indent=2, default=str))
    else:
        print(build_handoff_report(state_path))

        ws_path = Path(state_path).with_suffix(".world_state.json")
        if ws_path.exists():
            print(f"\nWorldState file: {ws_path}")

    if args.validate:
        result = validate_handoff_state_file(state_path)
        if not result.is_valid:
            print("\nValidation errors:")
            for error in result.errors:
                print(f"  - {error}")
        if result.warnings:
            print("\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")


def _cmd_exec_report(args: argparse.Namespace) -> None:
    log_path = Path(args.log_file) if args.log_file else None
    event_log = EventLog()

    if log_path and log_path.exists():
        event_log = _load_event_log(log_path)

    workflow = None
    workflow_result = None
    metrics_summary = None

    wf_path = Path(args.workflow_file) if args.workflow_file else None
    if wf_path and wf_path.exists():
        wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
        workflow = Workflow.from_dict(wf_data)

    wr_path = Path(args.workflow_result_file) if args.workflow_result_file else None
    if wr_path and wr_path.exists():
        wr_data = json.loads(wr_path.read_text(encoding="utf-8"))
        workflow_result = WorkflowResult(
            workflow_id=wr_data.get("workflow_id", "unknown"),
            status=wr_data.get("status", "unknown"),
            step_results=[StepResult(**sr) for sr in wr_data.get("step_results", [])],
            variables=wr_data.get("variables", {}),
            total_execution_time_ms=wr_data.get("total_execution_time_ms", 0.0),
            error_message=wr_data.get("error_message", ""),
        )

    gen = ReportGenerator(
        event_log=event_log,
        workflow=workflow,
        workflow_result=workflow_result,
        metrics_summary=metrics_summary,
    )

    run_id = args.run_id or "cli_run"
    output = gen.render_markdown(run_id=run_id)

    if args.output_file:
        out_path = Path(args.output_file)
        out_path.write_text(output, encoding="utf-8")
        print(f"Report saved to {out_path}")
    else:
        print(output)


def _cmd_calibrate(args: argparse.Namespace, config: CEEConfig) -> None:
    """Run a self-model calibration cycle."""

    state_path = Path(args.state_file)
    self_model: dict[str, object] = {}
    ws: WorldState | None = None
    if state_path.exists():
        ws = load_world_state_from_file(state_path)
        self_model = {
            "capabilities": list(ws.self_capability_summary),
            "limits": list(ws.self_limit_summary),
            "reliability": ws.self_reliability_estimate,
        }

    log_path = Path(args.log_file) if args.log_file else None
    log = EventLog()

    if log_path and log_path.exists():
        log = _load_event_log(log_path)

    gate = None
    if args.auto_approve:
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = run_calibration_cycle(log, current_self_model=self_model, approval_gate=gate)

    if args.output == "json":
        data = {
            "total_transitions": result.snapshot.total_transitions,
            "commitment_count": result.snapshot.commitment_count,
            "allow_rate": result.snapshot.allow_rate,
            "denial_rate": result.snapshot.denial_rate,
            "escalation_rate": result.snapshot.approval_escalation_rate,
            "redirect_count": result.snapshot.redirect_count,
            "proposal_count": result.proposal_count,
            "approved_count": result.approved_count,
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "patch_key": p.patch_key,
                    "evidence": p.evidence[:3],
                }
                for p in result.proposals
            ],
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Transitions observed : {result.snapshot.total_transitions}")
        print(f"Commitments observed : {result.snapshot.commitment_count}")
        print(f"Allow rate           : {result.snapshot.allow_rate:.1%}")
        print(f"Denial rate          : {result.snapshot.denial_rate:.1%}")
        print(f"Escalation rate      : {result.snapshot.approval_escalation_rate:.1%}")
        print(f"Redirect count       : {result.snapshot.redirect_count}")
        print(f"Calibration proposals: {result.proposal_count}")
        print(f"Approved             : {result.approved_count}")

        for proposal in result.proposals:
            print(f"\n  Proposal {proposal.proposal_id}:")
            print(f"    Key      : {proposal.patch_key}")
            print(f"    Evidence : {', '.join(proposal.evidence[:3])}")

    if args.save_state and result.approved_count > 0 and ws is not None:
        _save_world_state(args.save_state, ws)


def _cmd_validate(args: argparse.Namespace) -> None:
    """Validate a handoff state file."""

    state_path = args.state_file
    result = validate_handoff_state_file(state_path)

    if args.output == "json":
        data = {
            "is_valid": result.is_valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        if result.is_valid:
            print(f"Valid: yes")
        else:
            print(f"Valid: no")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  - {error}")

        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for warning in result.warnings:
                print(f"  - {warning}")


def _cmd_export(args: argparse.Namespace) -> None:
    """Export execution state to file."""

    state_path = Path(args.state_file)
    if not state_path.exists():
        print(f"Error: {state_path} not found", file=sys.stderr)
        sys.exit(1)

    ws = load_world_state_from_file(state_path)
    log_path = Path(args.log_file) if args.log_file else None
    log = EventLog()

    if log_path and log_path.exists():
        log = _load_event_log(log_path)

    manager = ImportExportManager()
    export_path = manager.export_to_file(
        ws,
        log,
        args.output_file,
        source_name=args.source_name or "cli",
        domain_name=args.domain or "core",
    )

    ws_path = state_path.with_suffix(".world_state.json")
    if ws_path.exists():
        ws_data = json.loads(ws_path.read_text(encoding="utf-8"))
        ws_export_path = Path(args.output_file).with_suffix(".world_state.json")
        ws_export_path.write_text(json.dumps(ws_data, indent=2, default=str), encoding="utf-8")

    if args.output == "json":
        print(json.dumps({
            "status": "succeeded",
            "export_path": export_path,
            "info": manager.get_export_info(export_path),
        }, indent=2, default=str))
    else:
        print(f"\nExport successful!")
        print(f"  Path: {export_path}")
        info = manager.get_export_info(export_path)
        print(f"  Events: {info['manifest']['event_count']}")
        print(f"  Source: {info['manifest']['source_name']}")
        print(f"  Domain: {info['manifest']['domain_name']}")


def _cmd_import(args: argparse.Namespace) -> None:
    """Import execution state from file."""

    if not Path(args.input_file).exists():
        print(f"Error: {args.input_file} not found", file=sys.stderr)
        sys.exit(1)

    manager = ImportExportManager()
    result = manager.import_from_file(args.input_file)

    if args.output == "json":
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\nImport Result:")
        print(f"  Status          : {result['status']}")
        print(f"  State Restored  : {result['state_restored']}")
        print(f"  Events Imported : {result['events_imported']}")
        if result['warnings']:
            print(f"\n  Warnings:")
            for w in result['warnings']:
                print(f"    - {w}")


def _save_run(path: str, artifact, log: EventLog, result=None) -> None:
    """Save run artifact, event log, and WorldState to files."""

    artifact_path = Path(path)
    artifact_path.write_text(artifact.dumps(), encoding="utf-8")
    print(f"Artifact saved to {artifact_path}")

    log_path = artifact_path.with_suffix(".events.json")
    events_data = [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in log.all()]
    log_path.write_text(json.dumps(events_data, indent=2, default=str), encoding="utf-8")
    print(f"Events saved to {log_path}")

    if result is not None and result.world_state is not None:
        ws_path = artifact_path.with_suffix(".world_state.json")
        ws_path.write_text(
            json.dumps(result.world_state.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"WorldState saved to {ws_path}")


def _save_world_state(path: str, ws: WorldState) -> None:
    """Save WorldState to a JSON file."""

    state_path = Path(path)
    state_path.write_text(
        json.dumps(ws.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"WorldState saved to {state_path}")


def _load_event_log(path: Path) -> EventLog:
    """Load event log from a JSON file (best-effort)."""

    log = EventLog()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        from .commitment import CommitmentEvent
        from .revision import ModelRevisionEvent
        from .events import DeliberationEvent
        from .tools import ToolCallEvent, ToolResultEvent

        for entry in data:
            if not isinstance(entry, dict):
                continue
            event_type = entry.get("event_type", "")
            try:
                if event_type == "commitment":
                    event = CommitmentEvent.from_dict(entry)
                    log.append(event)
                elif event_type == "revision":
                    event = ModelRevisionEvent.from_dict(entry)
                    log.append(event)
                elif event_type == "deliberation.step":
                    event = DeliberationEvent.from_dict(entry)
                    log.append(event)
                elif event_type == "tool.call":
                    event = ToolCallEvent.from_dict(entry)
                    log.append(event)
                elif event_type == "tool.result":
                    event = ToolResultEvent.from_dict(entry)
                    log.append(event)
                else:
                    event = Event(
                        event_type=event_type,
                        payload=entry.get("payload", {}),
                        actor=entry.get("actor", "unknown"),
                    )
                    log.append(event)
            except (KeyError, TypeError):
                continue
    return log


def main() -> None:
    """CLI entry point."""

    parser = argparse.ArgumentParser(
        prog="cee",
        description="Cognitive Execution Engine - State-first, policy-guarded runtime",
    )
    parser.add_argument("--config", help="Path to configuration file (yaml/json)")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run a task through the pipeline")
    run_parser.add_argument("task", help="Task description to execute")
    run_parser.add_argument("--domain", default="core", help="Domain context name")
    run_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve requires_approval transitions")
    run_parser.add_argument("--save", metavar="FILE", help="Save run artifact to file")
    run_parser.add_argument("--verbose", action="store_true", help="Show verbose execution metrics")
    run_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    run_parser.add_argument("--llm-provider", choices=["openai", "static"], default="static", help="LLM provider to use")
    run_parser.add_argument("--model", help="Model name for LLM provider")

    # report
    report_parser = subparsers.add_parser("report", help="Generate handoff readiness report")
    report_parser.add_argument("state_file", nargs="?", default="handoff_state.json", help="Path to handoff_state.json")
    report_parser.add_argument("--validate", action="store_true", help="Also run validation")
    report_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    # exec-report
    exec_report_parser = subparsers.add_parser("exec-report", help="Generate execution report in Markdown")
    exec_report_parser.add_argument("--log-file", help="Path to event log file")
    exec_report_parser.add_argument("--workflow-file", help="Path to workflow definition JSON")
    exec_report_parser.add_argument("--workflow-result-file", help="Path to workflow result JSON")
    exec_report_parser.add_argument("--run-id", help="Run ID for the report")
    exec_report_parser.add_argument("--output-file", help="Output file path for the report")
    exec_report_parser.add_argument("--format", choices=["markdown"], default="markdown", help="Output format")

    # calibrate
    cal_parser = subparsers.add_parser("calibrate", help="Run self-model calibration")
    cal_parser.add_argument("--state-file", default="cee_state.json", help="Path to state file")
    cal_parser.add_argument("--log-file", help="Path to event log file")
    cal_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve calibration patches")
    cal_parser.add_argument("--save-state", metavar="FILE", help="Save updated state to file")
    cal_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate handoff state file")
    val_parser.add_argument("state_file", nargs="?", default="handoff_state.json", help="Path to handoff_state.json")
    val_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    # export
    export_parser = subparsers.add_parser("export", help="Export execution state")
    export_parser.add_argument("--state-file", default="cee_state.json", help="Path to state file")
    export_parser.add_argument("--log-file", help="Path to event log file")
    export_parser.add_argument("--output-file", default="cee_export.json", help="Export output file")
    export_parser.add_argument("--source-name", help="Source name for export manifest")
    export_parser.add_argument("--domain", default="core", help="Domain name")
    export_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    # import
    import_parser = subparsers.add_parser("import", help="Import execution state")
    import_parser.add_argument("input_file", help="Path to export file")
    import_parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    config = load_config(args.config)

    commands = {
        "run": _cmd_run,
        "report": _cmd_report,
        "exec-report": _cmd_exec_report,
        "calibrate": _cmd_calibrate,
        "validate": _cmd_validate,
        "export": _cmd_export,
        "import": _cmd_import,
    }

    if args.command in ("run", "calibrate"):
        commands[args.command](args, config)
    else:
        commands[args.command](args)


if __name__ == "__main__":
    main()
