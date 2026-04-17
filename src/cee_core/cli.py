"""Command-line interface for the Cognitive Execution Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .calibration import run_calibration_cycle
from .approval import ApprovalGate, StaticApprovalProvider
from .event_log import EventLog
from .handoff_report import build_handoff_report
from .handoff_validator import validate_handoff_state_file
from .runtime import execute_task, execute_task_in_domain
from .domain_context import DomainContext
from .state import State
from .run_artifact import run_result_to_artifact


def _cmd_run(args: argparse.Namespace) -> None:
    """Run a task through the deterministic pipeline."""

    domain = DomainContext(domain_name=args.domain)
    log = EventLog()

    gate = None
    if args.auto_approve:
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = execute_task_in_domain(
        args.task,
        domain,
        event_log=log,
        approval_gate=gate,
    )

    artifact = run_result_to_artifact(result)
    replayed = artifact.replay_state()

    print(f"Task        : {args.task}")
    print(f"Kind        : {result.task.kind}")
    print(f"Risk level  : {result.task.risk_level}")
    print(f"Events      : {len(list(log.all()))}")
    print(f"Allowed     : {len(result.allowed_transitions)}")
    print(f"Denied      : {len(result.denied_transitions)}")
    print(f"Approval req: {len(result.approval_required_transitions)}")
    print(f"Redirect    : {result.redirect_proposed}")

    if result.approval_gate_result is not None:
        print(f"Approved    : {result.approval_gate_result.approval_count}")
        print(f"Rejected    : {result.approval_gate_result.rejection_count}")

    if args.save:
        _save_run(args.save, artifact, log)


def _cmd_report(args: argparse.Namespace) -> None:
    """Generate a handoff readiness report."""

    state_path = args.state_file
    if not Path(state_path).exists():
        print(f"Error: {state_path} not found", file=sys.stderr)
        sys.exit(1)

    print(build_handoff_report(state_path))

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


def _cmd_calibrate(args: argparse.Namespace) -> None:
    """Run a self-model calibration cycle."""

    state_path = Path(args.state_file)
    if not state_path.exists():
        state = State()
    else:
        state = _load_state(state_path)

    log_path = Path(args.log_file) if args.log_file else None
    log = EventLog()

    if log_path and log_path.exists():
        log = _load_event_log(log_path)

    gate = None
    if args.auto_approve:
        gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = run_calibration_cycle(log, state, approval_gate=gate)

    print(f"Transitions observed : {result.snapshot.total_transitions}")
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

    if args.save_state and result.approved_count > 0:
        _save_state(args.save_state, state)


def _cmd_validate(args: argparse.Namespace) -> None:
    """Validate a handoff state file."""

    state_path = args.state_file
    result = validate_handoff_state_file(state_path)

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


def _save_run(path: str, artifact, log: EventLog) -> None:
    """Save run artifact and event log to files."""

    artifact_path = Path(path)
    artifact_path.write_text(artifact.dumps(), encoding="utf-8")
    print(f"Artifact saved to {artifact_path}")

    log_path = artifact_path.with_suffix(".events.json")
    events_data = [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in log.all()]
    log_path.write_text(json.dumps(events_data, indent=2, default=str), encoding="utf-8")
    print(f"Events saved to {log_path}")


def _save_state(path: str, state: State) -> None:
    """Save state to a JSON file."""

    state_path = Path(path)
    state_path.write_text(
        json.dumps(state.snapshot(), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"State saved to {state_path}")


def _load_state(path: Path) -> State:
    """Load state from a JSON file."""

    data = json.loads(path.read_text(encoding="utf-8"))
    state = State()
    for section, value in data.items():
        if isinstance(value, dict):
            for key, val in value.items():
                state.__dict__[section][key] = val
    return state


def _load_event_log(path: Path) -> EventLog:
    """Load event log from a JSON file (best-effort)."""

    log = EventLog()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        from .events import StateTransitionEvent
        from .policy import PolicyDecision
        from .state import StatePatch

        for entry in data:
            if isinstance(entry, dict) and "patch" in entry:
                try:
                    patch = StatePatch(
                        section=entry["patch"]["section"],
                        key=entry["patch"]["key"],
                        op=entry["patch"]["op"],
                        value=entry["patch"].get("value", {}),
                    )
                    decision = PolicyDecision(
                        verdict=entry["policy_decision"]["verdict"],
                        reason=entry["policy_decision"]["reason"],
                        policy_ref=entry["policy_decision"]["policy_ref"],
                    )
                    event = StateTransitionEvent(
                        patch=patch,
                        policy_decision=decision,
                        actor=entry.get("actor", "replay"),
                        reason=entry.get("reason", ""),
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
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run a task through the pipeline")
    run_parser.add_argument("task", help="Task description to execute")
    run_parser.add_argument("--domain", default="core", help="Domain context name")
    run_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve requires_approval transitions")
    run_parser.add_argument("--save", metavar="FILE", help="Save run artifact to file")

    # report
    report_parser = subparsers.add_parser("report", help="Generate handoff readiness report")
    report_parser.add_argument("state_file", nargs="?", default="handoff_state.json", help="Path to handoff_state.json")
    report_parser.add_argument("--validate", action="store_true", help="Also run validation")

    # calibrate
    cal_parser = subparsers.add_parser("calibrate", help="Run self-model calibration")
    cal_parser.add_argument("--state-file", default="cee_state.json", help="Path to state file")
    cal_parser.add_argument("--log-file", help="Path to event log file")
    cal_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve calibration patches")
    cal_parser.add_argument("--save-state", metavar="FILE", help="Save updated state to file")

    # validate
    val_parser = subparsers.add_parser("validate", help="Validate handoff state file")
    val_parser.add_argument("state_file", nargs="?", default="handoff_state.json", help="Path to handoff_state.json")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "run": _cmd_run,
        "report": _cmd_report,
        "calibrate": _cmd_calibrate,
        "validate": _cmd_validate,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
