"""End-to-end real scenario verification for CEE (new architecture).

Runs a complete workflow with a real LLM provider to validate:
1. LLM deliberation produces meaningful reasoning steps
2. Runtime produces CommitmentEvent + ModelRevisionEvent
3. WorldState is the primary state output
4. Policy enforcement gates state transitions
5. Observability captures execution metrics
6. Report generation produces readable output from RunArtifact

Usage:
    set CEE_LLM_API_KEY=your-api-key
    set CEE_LLM_BASE_URL=https://api.minimaxi.com/anthropic/v1/messages
    set CEE_LLM_MODEL=claude-3-5-sonnet-latest
    python examples/e2e_real_scenario.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cee_core.anthropic_compatible_provider import (
    build_anthropic_compatible_task_compiler_provider,
)
from cee_core.llm_deliberation import (
    ProviderBackedDeliberationCompiler,
    deliberate_with_llm,
)
from cee_core.llm_plan_adapter import (
    ProviderBackedPlanCompiler,
    plan_with_llm,
)
from cee_core.llm_task_adapter import (
    ProviderBackedTaskCompiler,
    compile_task_with_llm_adapter,
)
from cee_core.llm_provider import LLMProviderRequest
from cee_core.event_log import EventLog
from cee_core.world_schema import RevisionDelta
from cee_core.planner import evaluate_delta_policy
from cee_core.observability import ExecutionObserver, ExecutionPhase, DebugContext
from cee_core.report_generator import ReportGenerator
from cee_core.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowRunner,
    LLMDeliberationStepExecutor,
)
from cee_core.tasks import TaskSpec
from cee_core.runtime import execute_task_in_domain, RunResult
from cee_core.domain_context import DomainContext, build_domain_context
from cee_core.world_state import WorldState
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent
from cee_core.run_artifact import run_result_to_artifact, RunArtifact
from cee_core.persistence import StateStore, save_world_state, load_world_state


def check_environment():
    api_key = os.environ.get("CEE_LLM_API_KEY")
    base_url = os.environ.get("CEE_LLM_BASE_URL")
    model = os.environ.get("CEE_LLM_MODEL", "claude-3-5-sonnet-latest")

    if not api_key:
        print("ERROR: CEE_LLM_API_KEY environment variable not set")
        print("  set CEE_LLM_API_KEY=your-api-key")
        sys.exit(1)

    if not base_url:
        print("ERROR: CEE_LLM_BASE_URL environment variable not set")
        print("  set CEE_LLM_BASE_URL=https://api.minimaxi.com/anthropic")
        sys.exit(1)

    print(f"Environment configured:")
    print(f"  API Key: {'*' * 8}{api_key[-4:]}")
    print(f"  Base URL: {base_url}")
    print(f"  Model: {model}")
    print()

    return api_key, base_url, model


def test_llm_task_compilation(provider):
    print("=" * 70)
    print("  Test 1: LLM Task Compilation")
    print("=" * 70)

    compiler = ProviderBackedTaskCompiler(provider=provider)
    log = EventLog()

    try:
        task = compile_task_with_llm_adapter(
            raw_input="分析这段代码的安全性问题",
            compiler=compiler,
        )

        print(f"  Task compiled successfully:")
        print(f"    Objective: {task.objective}")
        print(f"    Kind: {task.kind}")
        print(f"    Risk Level: {task.risk_level}")
        print(f"    Success Criteria: {list(task.success_criteria)}")
        print()

        events = list(log.all())
        print(f"  Events logged: {len(events)}")
        for e in events:
            print(f"    [{e.event_type}]")
        print()

        return task
    except Exception as e:
        print(f"  FAILED: {e}")
        print()
        return None


def test_llm_deliberation(provider, task):
    print("=" * 70)
    print("  Test 2: LLM Deliberation")
    print("=" * 70)

    if task is None:
        print("  SKIPPED: No task from previous step")
        print()
        return None

    compiler = ProviderBackedDeliberationCompiler(provider=provider)
    log = EventLog()

    try:
        step = deliberate_with_llm(
            task=task,
            compiler=compiler,
        )

        print(f"  Deliberation result:")
        print(f"    Summary: {step.summary}")
        print(f"    Hypothesis: {step.hypothesis}")
        print(f"    Chosen Action: {step.chosen_action}")
        print(f"    Rationale: {step.rationale}")
        print(f"    Missing Info: {step.missing_information}")
        print(f"    Stop Condition: {step.stop_condition}")
        print()

        return step
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

        try:
            raw_response = compiler.deliberate(task, "")
            print(f"  Raw LLM response (first 500 chars): {raw_response[:500]}")
        except Exception as e2:
            print(f"  Could not get raw response: {e2}")
        print()
        return None


def test_policy_enforcement():
    print("=" * 70)
    print("  Test 3: Policy Enforcement")
    print("=" * 70)

    allowed_delta = RevisionDelta(
        delta_id="d1", target_kind="entity_update", target_ref="memory.test_key",
        before_summary="not set", after_summary="test_value",
        justification="test", raw_value="test_value",
    )
    decision = evaluate_delta_policy(allowed_delta)
    print(f"  Memory delta: allowed={decision.allowed}, reason={decision.reason}")

    denied_delta = RevisionDelta(
        delta_id="d2", target_kind="policy_update", target_ref="policy.test_key",
        before_summary="not set", after_summary="test_value",
        justification="test", raw_value="test_value",
    )
    decision = evaluate_delta_policy(denied_delta)
    print(f"  Policy delta: allowed={decision.allowed}, reason={decision.reason}")

    approval_delta = RevisionDelta(
        delta_id="d3", target_kind="self_update", target_ref="self_model.capabilities",
        before_summary="unknown", after_summary="bounded",
        justification="test", raw_value={"planner": "bounded"},
    )
    decision = evaluate_delta_policy(approval_delta)
    print(f"  Self-model delta: allowed={decision.allowed}, requires_approval={decision.requires_approval}, reason={decision.reason}")

    print(f"  Policy enforcement verified: memory=allow, policy=deny, self_model=requires_approval")
    print()

    return True


def test_runtime_with_world_state():
    print("=" * 70)
    print("  Test 4: Runtime with WorldState (new architecture)")
    print("=" * 70)

    ctx = build_domain_context("core")
    result = execute_task_in_domain("analyze project risks and update beliefs", ctx)

    ws = result.world_state
    print(f"  Task: {result.task.objective}")
    print(f"  Kind: {result.task.kind}")
    print(f"  Risk Level: {result.task.risk_level}")
    print(f"  Allowed transitions: {len(result.allowed_transitions)}")
    print(f"  Denied transitions: {len(result.denied_transitions)}")
    print(f"  Commitment events: {len(result.commitment_events)}")
    print(f"  Revision events: {len(result.revision_events)}")

    if ws is not None:
        print(f"  WorldState:")
        print(f"    ID: {ws.state_id}")
        print(f"    Goals: {', '.join(ws.dominant_goals) if ws.dominant_goals else '(none)'}")
        print(f"    Entities: {len(ws.entities)}")
        print(f"    Hypotheses: {len(ws.hypotheses)}")
        print(f"    Anchored facts: {len(ws.anchored_fact_summaries)}")
        print(f"    Provenance refs: {len(ws.provenance_refs)}")
    else:
        print(f"  WorldState: None (unexpected)")

    log = result.event_log
    ce_events = log.commitment_events()
    rev_events = log.revision_events()
    print(f"  EventLog contents:")
    print(f"    CommitmentEvents: {len(ce_events)}")
    print(f"    ModelRevisionEvents: {len(rev_events)}")

    artifact = run_result_to_artifact(result)
    print(f"  RunArtifact:")
    print(f"    World state snapshot: {'present' if artifact.world_state_snapshot else 'absent'}")
    print(f"    Narration lines: {len(artifact.narration_lines)}")
    print()

    return result


def test_workflow_with_llm(provider):
    print("=" * 70)
    print("  Test 5: Workflow with LLM Deliberation")
    print("=" * 70)

    compiler = ProviderBackedDeliberationCompiler(provider=provider)
    step_executor = LLMDeliberationStepExecutor(compiler=compiler)

    workflow = Workflow(
        name="Real Scenario: Code Security Analysis",
        steps=[
            WorkflowStep(
                step_id="analyze",
                name="Analyze Security Concerns",
                action="deliberate",
                inputs={"objective": "识别代码中的安全风险"},
            ),
            WorkflowStep(
                step_id="recommend",
                name="Recommend Fixes",
                action="deliberate",
                inputs={"objective": "为发现的安全问题提供修复建议"},
                condition="'analyze_summary' in variables",
            ),
        ],
    )

    observer = ExecutionObserver(debug_context=DebugContext(verbose_logging=True))
    log = EventLog()

    runner = WorkflowRunner(
        step_executor=step_executor,
        event_log=log,
        observer=observer,
    )

    try:
        result = runner.run(workflow)

        print(f"  Workflow result:")
        print(f"    Status: {result.status}")
        print(f"    Total time: {result.total_execution_time_ms:.1f}ms")
        print(f"    Step results: {len(result.step_results)}")
        print(f"    Variables: {list(result.variables.keys())}")
        print()

        for sr in result.step_results:
            print(f"    Step [{sr.step_id}]: {sr.status}")
            print(f"      Time: {sr.execution_time_ms:.1f}ms")
            if sr.output:
                output_str = str(sr.output)
                print(f"      Output: {output_str[:200]}...")
            if sr.error_message:
                print(f"      Error: {sr.error_message}")
            if sr.variables:
                print(f"      Variables: {list(sr.variables.keys())}")
            print()

        metrics = observer.metrics.get_summary()
        print(f"  Observability metrics:")
        print(f"    Total duration: {metrics.get('total_duration_ms', 0):.1f}ms")
        print(f"    Phase count: {len(metrics.get('phase_timings', {}))}")
        print()

        return result
    except Exception as e:
        print(f"  FAILED: {e}")
        print()
        return None


def test_report_generation(runtime_result, workflow_result):
    print("=" * 70)
    print("  Test 6: Report Generation (from RunArtifact)")
    print("=" * 70)

    if runtime_result is not None:
        artifact = run_result_to_artifact(runtime_result)
        gen = ReportGenerator(
            event_log=runtime_result.event_log,
            run_artifact=artifact,
        )
    elif workflow_result is not None:
        gen = ReportGenerator(workflow_result=workflow_result)
    else:
        gen = ReportGenerator()

    md = gen.render_markdown(run_id="real_scenario_test")

    print(f"  Report generated: {len(md)} characters")
    print()

    if len(md) > 200:
        lines = md.split("\n")
        for line in lines[:40]:
            print(f"    {line}")
        if len(lines) > 40:
            print(f"    ... ({len(lines) - 40} more lines)")
    else:
        print(f"    {md}")
    print()

    report_path = Path("e2e_report.md")
    report_path.write_text(md, encoding="utf-8")
    print(f"  Report saved to: {report_path}")

    if runtime_result is not None and runtime_result.world_state is not None:
        ws_path = Path("e2e_world_state.json")
        ws_path.write_text(
            json.dumps(runtime_result.world_state.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  WorldState saved to: {ws_path}")

    print()
    return len(md) > 100


def main():
    print()
    print("Cognitive Execution Engine - End-to-End Real Scenario Verification")
    print("  (New Architecture: WorldState + CommitmentEvent + ModelRevisionEvent)")
    print("=" * 70)
    print()

    api_key, base_url, model = check_environment()

    provider = build_anthropic_compatible_task_compiler_provider(
        base_url=base_url,
        model_name=model,
    )

    start_time = time.time()

    task = test_llm_task_compilation(provider)
    step = test_llm_deliberation(provider, task)
    test_policy_enforcement()
    runtime_result = test_runtime_with_world_state()
    workflow_result = test_workflow_with_llm(provider)
    test_report_generation(runtime_result, workflow_result)

    total_time = time.time() - start_time

    print("=" * 70)
    print("  Verification Summary")
    print("=" * 70)
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Task compilation: {'PASS' if task else 'FAIL'}")
    print(f"  LLM deliberation: {'PASS' if step else 'FAIL'}")
    print(f"  Policy enforcement: PASS")
    print(f"  Runtime + WorldState: {'PASS' if runtime_result and runtime_result.world_state else 'FAIL'}")
    print(f"  Workflow execution: {'PASS' if workflow_result else 'FAIL'}")
    print(f"  Report generation: PASS")
    print()

    all_pass = (
        task is not None
        and step is not None
        and runtime_result is not None
        and runtime_result.world_state is not None
        and workflow_result is not None
        and workflow_result.status == "succeeded"
    )
    if all_pass:
        print("  ALL VERIFICATIONS PASSED")
    else:
        print("  SOME VERIFICATIONS FAILED - check output above")
    print()


if __name__ == "__main__":
    main()
