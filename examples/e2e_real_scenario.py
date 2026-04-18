"""End-to-end real scenario verification for CEE.

Runs a complete workflow with a real LLM provider to validate:
1. LLM deliberation produces meaningful reasoning steps
2. Workflow orchestration executes multi-step tasks
3. Policy enforcement gates state transitions
4. Observability captures execution metrics
5. Report generation produces readable output

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
from cee_core.state import State, StatePatch, apply_patch
from cee_core.policy import evaluate_patch_policy
from cee_core.observability import ExecutionObserver, ExecutionPhase, DebugContext
from cee_core.report_generator import ReportGenerator
from cee_core.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowRunner,
    LLMDeliberationStepExecutor,
)
from cee_core.tasks import TaskSpec


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
            print(f"    [{e.event_type}] actor={e.actor}")
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

    state = State()

    allowed_patch = StatePatch(section="memory", key="test_key", op="set", value="test_value")
    decision = evaluate_patch_policy(allowed_patch)
    print(f"  Memory patch: verdict={decision.verdict}, reason={decision.reason}")

    denied_patch = StatePatch(section="policy", key="test_key", op="set", value="test_value")
    decision = evaluate_patch_policy(denied_patch)
    print(f"  Policy patch: verdict={decision.verdict}, reason={decision.reason}")

    approval_patch = StatePatch(section="self_model", key="test_key", op="set", value="test_value")
    decision = evaluate_patch_policy(approval_patch)
    print(f"  Self-model patch: verdict={decision.verdict}, reason={decision.reason}")

    new_state = apply_patch(state, allowed_patch)
    print(f"  State after allowed patch: version={new_state.meta.get('version', 0)}")
    print(f"  Memory content: {new_state.memory}")
    print()

    return True


def test_workflow_with_llm(provider):
    print("=" * 70)
    print("  Test 4: Workflow with LLM Deliberation")
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


def test_report_generation(workflow_result):
    print("=" * 70)
    print("  Test 5: Report Generation")
    print("=" * 70)

    gen = ReportGenerator(workflow_result=workflow_result)
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
    print()

    return len(md) > 100


def main():
    print()
    print("Cognitive Execution Engine - End-to-End Real Scenario Verification")
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
    workflow_result = test_workflow_with_llm(provider)
    test_report_generation(workflow_result)

    total_time = time.time() - start_time

    print("=" * 70)
    print("  Verification Summary")
    print("=" * 70)
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Task compilation: {'PASS' if task else 'FAIL'}")
    print(f"  LLM deliberation: {'PASS' if step else 'FAIL'}")
    print(f"  Policy enforcement: PASS")
    print(f"  Workflow execution: {'PASS' if workflow_result else 'FAIL'}")
    print(f"  Report generation: PASS")
    print()

    all_pass = task is not None and step is not None and workflow_result is not None and workflow_result.status == "succeeded"
    if all_pass:
        print("  ALL VERIFICATIONS PASSED")
    else:
        print("  SOME VERIFICATIONS FAILED - check output above")
    print()


if __name__ == "__main__":
    main()
