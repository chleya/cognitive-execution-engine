"""End-to-end demo: full pipeline with approval, confidence, and calibration.

Run from repo root:
    python examples/e2e_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cee_core import (
    ApprovalGate,
    BehavioralSnapshot,
    DomainContext,
    DomainPluginPack,
    EventLog,
    RunResult,
    StaticApprovalProvider,
    State,
    execute_task_in_domain,
    extract_behavioral_snapshot,
    run_calibration_cycle,
    run_result_to_artifact,
)


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def demo_basic_run() -> EventLog:
    _print_section("1. Basic Run: deterministic pipeline")

    log = EventLog()
    result = execute_task_in_domain("count to 3", DomainContext(domain_name="core"), event_log=log)

    print(f"Task kind       : {result.task.kind}")
    print(f"Risk level      : {result.task.risk_level}")
    print(f"Allowed         : {len(result.allowed_transitions)}")
    print(f"Denied          : {len(result.denied_transitions)}")
    print(f"Redirect        : {result.redirect_proposed}")

    artifact = run_result_to_artifact(result)
    print(f"Artifact bytes  : {len(artifact.dumps())}")

    return log


def demo_approval_gate() -> EventLog:
    _print_section("2. Approval Gate: self_model changes need approval")

    log = EventLog()
    domain = DomainContext(
        domain_name="approval_demo",
        plugin_pack=DomainPluginPack(
            domain_name="approval_demo",
            approval_required_patch_sections=("self_model",),
        ),
    )
    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = execute_task_in_domain(
        "update self_model capabilities to planner bounded",
        domain,
        event_log=log,
        approval_gate=gate,
    )

    print(f"Approval required : {len(result.approval_required_transitions)}")
    if result.approval_gate_result:
        print(f"Approved          : {result.approval_gate_result.approval_count}")
        print(f"Rejected          : {result.approval_gate_result.rejection_count}")

    return log


def demo_confidence_gate() -> EventLog:
    _print_section("3. Confidence Gate: low-confidence beliefs need approval")

    log = EventLog()
    state = State()
    state.beliefs["uncertain_claim"] = {
        "content": "might be true",
        "confidence": 0.3,
        "provenance": ["weak_source"],
    }

    result = execute_task_in_domain(
        "update beliefs uncertain_claim with new evidence",
        DomainContext(domain_name="core"),
        event_log=log,
    )

    snapshot = extract_behavioral_snapshot(log)
    print(f"Total transitions : {snapshot.total_transitions}")
    print(f"Escalation rate  : {snapshot.approval_escalation_rate:.1%}")
    print(f"Avg confidence    : {snapshot.avg_belief_confidence:.2f}")

    return log


def demo_explore_mode() -> EventLog:
    _print_section("4. Explore Mode: analysis tasks propose redirect")

    log = EventLog()
    result = execute_task_in_domain(
        "analyze unknown system architecture",
        DomainContext(domain_name="core"),
        event_log=log,
    )

    print(f"Chosen action     : {result.reasoning_step.chosen_action}")
    print(f"Candidate actions : {result.reasoning_step.candidate_actions}")
    print(f"Redirect proposed : {result.redirect_proposed}")

    return log


def demo_calibration() -> None:
    _print_section("5. Calibration: self-observation and self-model update")

    log = EventLog()

    from cee_core.events import DeliberationEvent, StateTransitionEvent
    from cee_core.deliberation import ReasoningStep
    from cee_core.policy import PolicyDecision
    from cee_core.state import StatePatch

    for section, verdict in [
        ("goals", "allow"),
        ("goals", "allow"),
        ("beliefs", "allow"),
        ("self_model", "requires_approval"),
        ("policy", "deny"),
        ("beliefs", "deny"),
    ]:
        patch = StatePatch(section=section, key="k1", op="set", value={"v": 1})
        decision = PolicyDecision(verdict=verdict, reason=f"test {verdict}", policy_ref="demo")
        log.append(StateTransitionEvent(patch=patch, policy_decision=decision, actor="demo", reason="demo"))

    step = ReasoningStep(
        task_id="demo",
        summary="demo step",
        hypothesis="testing",
        missing_information=("x", "y"),
        candidate_actions=("propose_redirect",),
        chosen_action="propose_redirect",
        rationale="demo",
        stop_condition="done",
    )
    log.append(DeliberationEvent(reasoning_step=step))

    state = State()
    gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

    result = run_calibration_cycle(log, state, approval_gate=gate)

    print(f"Allow rate         : {result.snapshot.allow_rate:.1%}")
    print(f"Denial rate        : {result.snapshot.denial_rate:.1%}")
    print(f"Redirect count     : {result.snapshot.redirect_count}")
    print(f"Calibration props  : {result.proposal_count}")
    print(f"Approved           : {result.approved_count}")

    for proposal in result.proposals:
        print(f"\n  {proposal.proposal_id}: {proposal.patch_key}")
        for evidence in proposal.evidence[:2]:
            print(f"    - {evidence}")


def main() -> None:
    print("Cognitive Execution Engine - End-to-End Demo")
    print("Planner proposes. Policy decides. EventLog audits. Replay verifies.")

    demo_basic_run()
    demo_approval_gate()
    demo_confidence_gate()
    demo_explore_mode()
    demo_calibration()

    _print_section("Summary")
    print("All 5 demo scenarios completed successfully.")
    print("The system is ready for use via CLI or Python API.")
    print("\nCLI commands:")
    print("  cee run \"your task description\"")
    print("  cee report")
    print("  cee validate")
    print("  cee calibrate --auto-approve")


if __name__ == "__main__":
    main()
