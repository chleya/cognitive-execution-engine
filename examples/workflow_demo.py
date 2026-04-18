"""Workflow orchestration demo: multi-step document analysis pipeline.

Run from repo root:
    python examples/workflow_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json

from cee_core.event_log import EventLog
from cee_core.llm_deliberation import StaticLLMDeliberationCompiler
from cee_core.llm_provider import StaticLLMProvider
from cee_core.observability import (
    ConsoleMetricsExporter,
    ExecutionMetricsCollector,
    ExecutionObserver,
)
from cee_core.tool_executor import (
    DefaultToolSandbox,
    SandboxedToolExecutor,
    ToolExecutionContext,
    ToolExecutionResult,
)
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolResultEvent, ToolSpec
from cee_core.workflow import (
    LLMDeliberationStepExecutor,
    StepResult,
    ToolExecutionStepExecutor,
    Workflow,
    WorkflowResult,
    WorkflowRunner,
    WorkflowStep,
)


def _print_section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def _print_step_result(result: StepResult) -> None:
    print(f"  Step: {result.step_id}")
    print(f"  Status: {result.status}")
    if result.succeeded:
        print(f"  Execution time: {result.execution_time_ms:.2f}ms")
        if result.variables:
            print(f"  Variables produced:")
            for k, v in result.variables.items():
                print(f"    {k}: {v}")
    elif result.status == "skipped":
        print(f"  Reason: condition not met")
    else:
        print(f"  Error: {result.error_message}")
    print()


def build_document_analysis_workflow() -> Workflow:
    return Workflow(
        name="Document Analysis Pipeline",
        steps=[
            WorkflowStep(
                step_id="step_1",
                name="Analyze Document Structure",
                action="Analyze the document structure and identify key sections, metadata, and content types.",
                inputs={
                    "document_type": "technical_specification",
                    "format": "markdown",
                },
                outputs=["structure_summary", "section_count"],
            ),
            WorkflowStep(
                step_id="step_2",
                name="Extract Key Information",
                action="Extract key information from the analyzed document structure including requirements, constraints, and dependencies.",
                inputs={
                    "structure": "${step_1_summary}",
                    "extraction_targets": ["requirements", "constraints", "dependencies"],
                },
                outputs=["extracted_requirements", "key_findings"],
                condition="'step_1_summary' in variables",
            ),
            WorkflowStep(
                step_id="step_3",
                name="Generate Analysis Report",
                action="Generate a comprehensive analysis report summarizing document structure and extracted information.",
                inputs={
                    "structure_analysis": "${step_1_summary}",
                    "extracted_info": "${step_2_summary}",
                },
                outputs=["final_report"],
            ),
        ],
        metadata={
            "domain": "document_analysis",
            "version": "1.0",
        },
    )


def build_code_review_workflow() -> Workflow:
    return Workflow(
        name="Code Review Pipeline",
        steps=[
            WorkflowStep(
                step_id="review_1",
                name="Static Analysis",
                action="Perform static code analysis to identify potential issues, code smells, and best practice violations.",
                inputs={
                    "code_language": "python",
                    "analysis_depth": "standard",
                },
                outputs=["issues_found", "severity_count"],
            ),
            WorkflowStep(
                step_id="review_2",
                name="Security Review",
                action="Review code for security vulnerabilities including injection risks, authentication issues, and data exposure.",
                inputs={
                    "static_analysis_results": "${review_1_summary}",
                },
                outputs=["security_issues", "risk_level"],
                condition="'review_1_summary' in variables",
            ),
            WorkflowStep(
                step_id="review_3",
                name="Generate Review Report",
                action="Generate a comprehensive code review report with findings and recommendations.",
                inputs={
                    "static_issues": "${review_1_summary}",
                    "security_issues": "${review_2_summary}",
                },
                outputs=["review_report"],
            ),
        ],
        metadata={
            "domain": "code_review",
            "version": "1.0",
        },
    )


def build_report_generation_workflow() -> Workflow:
    return Workflow(
        name="Report Generation Pipeline",
        steps=[
            WorkflowStep(
                step_id="report_1",
                name="Gather Metrics",
                action="Gather and aggregate all relevant metrics from previous analysis steps.",
                inputs={
                    "source": "analysis_results",
                },
                outputs=["metrics_summary"],
            ),
            WorkflowStep(
                step_id="report_2",
                name="Format Report",
                action="Format the collected metrics into a structured report with executive summary, detailed findings, and recommendations.",
                inputs={
                    "metrics": "${report_1_summary}",
                    "format": "markdown",
                },
                outputs=["formatted_report"],
            ),
            WorkflowStep(
                step_id="report_3",
                name="Finalize Report",
                action="Add metadata, timestamps, and validation checksums to the final report.",
                inputs={
                    "draft_report": "${report_2_summary}",
                },
                outputs=["final_report"],
            ),
        ],
        metadata={
            "domain": "report_generation",
            "version": "1.0",
        },
    )


def demo_single_workflow(name: str, workflow: Workflow, runner: WorkflowRunner) -> WorkflowResult:
    _print_section(name)

    print(f"Workflow: {workflow.name}")
    print(f"ID: {workflow.workflow_id}")
    print(f"Steps: {len(workflow.steps)}")
    print()

    for step in workflow.steps:
        print(f"  [{step.step_id}] {step.name}")
        if step.condition:
            print(f"       Condition: {step.condition}")
    print()

    result = runner.run_with_export(workflow)

    print(f"Execution Results:")
    print(f"  Status: {result.status}")
    print(f"  Total time: {result.total_execution_time_ms:.2f}ms")
    print()

    for step_result in result.step_results:
        _print_step_result(step_result)

    return result


def demo_conditional_workflow() -> WorkflowResult:
    _print_section("Conditional Execution Demo")

    compiler = StaticLLMDeliberationCompiler(
        response_json=json.dumps({
            "summary": "Step executed",
            "hypothesis": "workflow test",
            "missing_information": [],
            "candidate_actions": ["propose_plan"],
            "chosen_action": "propose_plan",
            "rationale": "Deterministic test step",
            "stop_condition": "done",
        })
    )

    executor = LLMDeliberationStepExecutor(compiler=compiler)

    event_log = EventLog()
    metrics = ExecutionMetricsCollector()
    observer = ExecutionObserver(
        metrics_collector=metrics,
        exporters=[ConsoleMetricsExporter()],
    )

    runner = WorkflowRunner(
        step_executor=executor,
        event_log=event_log,
        observer=observer,
        stop_on_error=False,
    )

    workflow = Workflow(
        name="Conditional Test Workflow",
        steps=[
            WorkflowStep(
                step_id="cond_1",
                name="Always Run",
                action="Execute first step unconditionally.",
                inputs={"data": "initial"},
                outputs=["result_1"],
            ),
            WorkflowStep(
                step_id="cond_2",
                name="Conditional Run",
                action="Execute only if condition is met.",
                inputs={"data": "${cond_1_summary}"},
                outputs=["result_2"],
                condition="True",
            ),
            WorkflowStep(
                step_id="cond_3",
                name="Skipped Step",
                action="This step should be skipped.",
                inputs={},
                outputs=[],
                condition="False",
            ),
            WorkflowStep(
                step_id="cond_4",
                name="Variable Dependent",
                action="Execute if variable exists.",
                inputs={"prev": "${cond_2_summary}"},
                outputs=["result_4"],
                condition="'cond_2_summary' in variables",
            ),
        ],
        metadata={"test": True},
    )

    print(f"Workflow: {workflow.name}")
    print(f"Steps: {len(workflow.steps)}")
    print()

    result = runner.run_with_export(workflow)

    print(f"\nExecution Results:")
    print(f"  Status: {result.status}")
    print(f"  Total time: {result.total_execution_time_ms:.2f}ms")
    print()

    for step_result in result.step_results:
        _print_step_result(step_result)

    return result


def demo_tool_execution_workflow() -> WorkflowResult:
    _print_section("Tool Execution Demo")

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="read_file",
        description="Read file contents",
        risk="read",
    ))
    registry.register(ToolSpec(
        name="analyze_text",
        description="Analyze text content",
        risk="read",
    ))

    tool_executor = SandboxedToolExecutor(
        registry=registry,
        sandbox=DefaultToolSandbox(),
    )

    def mock_read_file(ctx):
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="succeeded",
            result=f"Contents of {ctx.arguments.get('path', 'unknown')}",
        )

    def mock_analyze_text(ctx):
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="succeeded",
            result=f"Analysis of: {ctx.arguments.get('text', 'empty')}",
        )

    tool_executor.register_handler("read_file", mock_read_file)
    tool_executor.register_handler("analyze_text", mock_analyze_text)

    executor = ToolExecutionStepExecutor(tool_executor=tool_executor)

    event_log = EventLog()
    metrics = ExecutionMetricsCollector()
    observer = ExecutionObserver(
        metrics_collector=metrics,
        exporters=[ConsoleMetricsExporter()],
    )

    runner = WorkflowRunner(
        step_executor=executor,
        event_log=event_log,
        observer=observer,
    )

    workflow = Workflow(
        name="Tool Execution Test",
        steps=[
            WorkflowStep(
                step_id="tool_1",
                name="Read Document",
                action="read_file",
                inputs={"path": "/docs/spec.md"},
                outputs=["file_contents"],
            ),
            WorkflowStep(
                step_id="tool_2",
                name="Analyze Content",
                action="analyze_text",
                inputs={"text": "${tool_1_result}"},
                outputs=["analysis"],
            ),
        ],
        metadata={"type": "tool_demo"},
    )

    print(f"Workflow: {workflow.name}")
    print(f"Steps: {len(workflow.steps)}")
    print()

    result = runner.run_with_export(workflow)

    print(f"\nExecution Results:")
    print(f"  Status: {result.status}")
    print(f"  Total time: {result.total_execution_time_ms:.2f}ms")
    print()

    for step_result in result.step_results:
        _print_step_result(step_result)

    return result


def main() -> None:
    print("Cognitive Execution Engine - Workflow Orchestration Demo")
    print("WorkflowRunner orchestrates. Steps execute. Observability tracks.")

    compiler = StaticLLMDeliberationCompiler(
        response_json=json.dumps({
            "summary": "Step completed successfully",
            "hypothesis": "workflow processing",
            "missing_information": [],
            "candidate_actions": ["propose_plan"],
            "chosen_action": "propose_plan",
            "rationale": "Deterministic workflow step execution",
            "stop_condition": "done",
        })
    )

    executor = LLMDeliberationStepExecutor(compiler=compiler)

    event_log = EventLog()
    metrics = ExecutionMetricsCollector()
    observer = ExecutionObserver(
        metrics_collector=metrics,
        exporters=[ConsoleMetricsExporter()],
    )

    runner = WorkflowRunner(
        step_executor=executor,
        event_log=event_log,
        observer=observer,
    )

    demo_single_workflow(
        "1. Document Analysis Workflow",
        build_document_analysis_workflow(),
        runner,
    )

    demo_single_workflow(
        "2. Code Review Workflow",
        build_code_review_workflow(),
        runner,
    )

    demo_single_workflow(
        "3. Report Generation Workflow",
        build_report_generation_workflow(),
        runner,
    )

    demo_conditional_workflow()

    demo_tool_execution_workflow()

    _print_section("Summary")
    print("All workflow scenarios completed successfully.")
    print("Demonstrated:")
    print("  - Sequential step execution with LLM deliberation")
    print("  - Variable passing between steps")
    print("  - Conditional execution")
    print("  - Tool execution integration")
    print("  - Observability and metrics collection")
    print("  - Audit trail via event log")


if __name__ == "__main__":
    main()
