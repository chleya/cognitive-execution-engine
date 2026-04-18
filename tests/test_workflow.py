"""Tests for workflow orchestration."""

import json
import pytest

from cee_core.event_log import EventLog
from cee_core.events import Event
from cee_core.llm_deliberation import StaticLLMDeliberationCompiler
from cee_core.llm_provider import StaticLLMProvider
from cee_core.observability import (
    ExecutionMetricsCollector,
    ExecutionObserver,
)
from cee_core.tool_executor import DefaultToolSandbox, SandboxedToolExecutor, ToolExecutionResult, ToolExecutionContext
from cee_core.tools import ToolCallSpec, ToolRegistry, ToolSpec, ToolResultEvent
from cee_core.workflow import (
    LLMDeliberationStepExecutor,
    StepResult,
    ToolExecutionStepExecutor,
    Workflow,
    WorkflowResult,
    WorkflowRunner,
    WorkflowStep,
    _evaluate_condition,
)


class TestWorkflowStep:
    def test_create_step(self):
        step = WorkflowStep(
            step_id="step_1",
            name="Test Step",
            action="Do something",
        )

        assert step.step_id == "step_1"
        assert step.name == "Test Step"
        assert step.action == "Do something"
        assert step.inputs == {}
        assert step.outputs == []
        assert step.condition is None
        assert step.timeout_seconds == 30.0
        assert step.retry_count == 0

    def test_create_step_with_inputs_outputs(self):
        step = WorkflowStep(
            step_id="step_2",
            name="Complex Step",
            action="Process data",
            inputs={"key": "value", "number": 42},
            outputs=["result_1", "result_2"],
            condition="True",
            timeout_seconds=60.0,
        )

        assert step.inputs["key"] == "value"
        assert step.inputs["number"] == 42
        assert len(step.outputs) == 2
        assert step.condition == "True"
        assert step.timeout_seconds == 60.0

    def test_step_to_dict(self):
        step = WorkflowStep(
            step_id="step_1",
            name="Test",
            action="action",
            inputs={"a": 1},
            metadata={"version": "1.0"},
        )

        d = step.to_dict()

        assert d["step_id"] == "step_1"
        assert d["name"] == "Test"
        assert d["action"] == "action"
        assert d["inputs"] == {"a": 1}
        assert d["metadata"]["version"] == "1.0"

    def test_step_from_dict(self):
        payload = {
            "step_id": "step_3",
            "name": "From Dict",
            "action": "execute",
            "inputs": {"x": 10},
            "outputs": ["y"],
            "condition": "x > 5",
            "timeout_seconds": 15.0,
            "retry_count": 2,
        }

        step = WorkflowStep.from_dict(payload)

        assert step.step_id == "step_3"
        assert step.name == "From Dict"
        assert step.action == "execute"
        assert step.inputs["x"] == 10
        assert step.outputs == ["y"]
        assert step.condition == "x > 5"
        assert step.timeout_seconds == 15.0
        assert step.retry_count == 2


class TestWorkflow:
    def test_create_workflow(self):
        steps = [
            WorkflowStep(step_id="s1", name="Step 1", action="act1"),
            WorkflowStep(step_id="s2", name="Step 2", action="act2"),
        ]

        wf = Workflow(
            name="Test Workflow",
            steps=steps,
        )

        assert wf.name == "Test Workflow"
        assert len(wf.steps) == 2
        assert wf.workflow_id.startswith("wf_")

    def test_workflow_with_metadata(self):
        steps = [
            WorkflowStep(step_id="s1", name="Step 1", action="act1"),
        ]

        wf = Workflow(
            name="Meta Workflow",
            steps=steps,
            metadata={"domain": "test", "version": "2.0"},
        )

        assert wf.metadata["domain"] == "test"
        assert wf.metadata["version"] == "2.0"

    def test_workflow_to_dict(self):
        steps = [
            WorkflowStep(step_id="s1", name="Step 1", action="act1"),
        ]

        wf = Workflow(name="Dict Workflow", steps=steps)
        d = wf.to_dict()

        assert d["name"] == "Dict Workflow"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["step_id"] == "s1"

    def test_workflow_from_dict(self):
        payload = {
            "workflow_id": "wf_test123",
            "name": "From Dict Workflow",
            "steps": [
                {
                    "step_id": "s1",
                    "name": "Step 1",
                    "action": "act1",
                },
                {
                    "step_id": "s2",
                    "name": "Step 2",
                    "action": "act2",
                    "inputs": {"key": "value"},
                },
            ],
            "metadata": {"type": "test"},
        }

        wf = Workflow.from_dict(payload)

        assert wf.workflow_id == "wf_test123"
        assert wf.name == "From Dict Workflow"
        assert len(wf.steps) == 2
        assert wf.steps[1].inputs["key"] == "value"


class TestStepResult:
    def test_succeeded_result(self):
        result = StepResult(
            step_id="s1",
            status="succeeded",
            output="data",
            variables={"var1": "value1"},
        )

        assert result.succeeded is True
        assert result.step_id == "s1"
        assert result.variables["var1"] == "value1"

    def test_failed_result(self):
        result = StepResult(
            step_id="s1",
            status="failed",
            error_message="Something went wrong",
        )

        assert result.succeeded is False
        assert result.error_message == "Something went wrong"

    def test_skipped_result(self):
        result = StepResult(
            step_id="s1",
            status="skipped",
        )

        assert result.succeeded is False
        assert result.status == "skipped"

    def test_result_to_dict(self):
        result = StepResult(
            step_id="s1",
            status="succeeded",
            execution_time_ms=150.0,
        )

        d = result.to_dict()

        assert d["step_id"] == "s1"
        assert d["status"] == "succeeded"
        assert d["execution_time_ms"] == 150.0


class TestWorkflowResult:
    def test_succeeded_workflow(self):
        result = WorkflowResult(
            workflow_id="wf_1",
            status="succeeded",
        )

        assert result.succeeded is True

    def test_failed_workflow(self):
        result = WorkflowResult(
            workflow_id="wf_1",
            status="failed",
            error_message="Step failed",
        )

        assert result.succeeded is False

    def test_workflow_result_to_dict(self):
        result = WorkflowResult(
            workflow_id="wf_1",
            status="succeeded",
            total_execution_time_ms=500.0,
        )

        d = result.to_dict()

        assert d["workflow_id"] == "wf_1"
        assert d["status"] == "succeeded"
        assert d["total_execution_time_ms"] == 500.0


class TestEvaluateCondition:
    def test_true_condition(self):
        assert _evaluate_condition("True", {}) is True

    def test_false_condition(self):
        assert _evaluate_condition("False", {}) is False

    def test_variable_condition(self):
        variables = {"x": 10, "y": 5}
        assert _evaluate_condition("x > y", variables) is True
        assert _evaluate_condition("x < y", variables) is False

    def test_variable_exists_check(self):
        variables = {"key": "value"}
        assert _evaluate_condition("'key' in variables", variables) is True
        assert _evaluate_condition("'missing' in variables", variables) is False

    def test_invalid_condition_defaults_to_false(self):
        assert _evaluate_condition("invalid_syntax()", {}) is False

    def test_malicious_eval_rejected(self):
        assert _evaluate_condition("eval('1+1')", {}) is False

    def test_malicious_import_rejected(self):
        assert _evaluate_condition("__import__('os')", {}) is False

    def test_dunder_rejected(self):
        assert _evaluate_condition("variables.__class__", {}) is False

    def test_open_rejected(self):
        assert _evaluate_condition("open('/etc/passwd')", {}) is False

    def test_getattr_rejected(self):
        assert _evaluate_condition("getattr(variables, 'x')", {}) is False

    def test_variables_get_condition(self):
        variables = {"key": "value"}
        assert _evaluate_condition("variables.get('key')", variables) is True
        assert _evaluate_condition("variables.get('missing')", variables) is False

    def test_equality_condition(self):
        variables = {"status": "ready"}
        assert _evaluate_condition("status == 'ready'", variables) is True
        assert _evaluate_condition("status != 'done'", variables) is True

    def test_numeric_comparison(self):
        variables = {"count": 5}
        assert _evaluate_condition("count > 3", variables) is True
        assert _evaluate_condition("count < 3", variables) is False


class TestLLMDeliberationStepExecutor:
    def test_execute_step(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Test summary",
                "hypothesis": "test hypothesis",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test rationale",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        step = WorkflowStep(
            step_id="test_1",
            name="Test Step",
            action="Analyze something",
            inputs={"data": "test_data"},
        )

        result = executor.execute(step, variables={})

        assert result.succeeded is True
        assert result.step_id == "test_1"
        assert "test_1_summary" in result.variables
        assert result.variables["test_1_summary"] == "Test summary"

    def test_execute_step_with_variables(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Used previous",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        step = WorkflowStep(
            step_id="test_2",
            name="Variable Step",
            action="Use variables",
            inputs={"prev": "${test_1_summary}"},
        )

        variables = {"test_1_summary": "Previous result"}
        result = executor.execute(step, variables=variables)

        assert result.succeeded is True

    def test_execute_step_with_event_log(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Logged step",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)
        event_log = EventLog()

        step = WorkflowStep(
            step_id="log_1",
            name="Logged Step",
            action="Do something",
        )

        result = executor.execute(step, variables={}, event_log=event_log)

        assert result.succeeded is True
        assert len(event_log.all()) > 0

    def test_execute_step_with_tool_registry(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Tool aware",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        registry = ToolRegistry()
        registry.register(ToolSpec(name="test_tool", description="Test", risk="read"))

        executor = LLMDeliberationStepExecutor(
            compiler=compiler,
            tool_registry=registry,
        )

        step = WorkflowStep(
            step_id="tool_aware",
            name="Tool Aware Step",
            action="Use tools",
        )

        result = executor.execute(step, variables={})

        assert result.succeeded is True

    def test_execute_step_failure(self):
        class FailingCompiler:
            def deliberate(self, task, context):
                raise ValueError("Deliberation failed")

        executor = LLMDeliberationStepExecutor(
            compiler=FailingCompiler(),
            fallback_to_deterministic=False,
        )

        step = WorkflowStep(
            step_id="fail_1",
            name="Failing Step",
            action="Will fail",
        )

        result = executor.execute(step, variables={})

        assert result.succeeded is False
        assert result.status == "failed"
        assert "Deliberation failed" in result.error_message


class TestToolExecutionStepExecutor:
    def test_execute_tool_step(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="mock_tool", description="Mock", risk="read"))

        def mock_handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result=f"Processed {ctx.arguments.get('input', 'none')}",
            )

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_handler("mock_tool", mock_handler)

        step_executor = ToolExecutionStepExecutor(tool_executor=executor)

        step = WorkflowStep(
            step_id="tool_1",
            name="Tool Step",
            action="mock_tool",
            inputs={"input": "test_data"},
        )

        result = step_executor.execute(step, variables={})

        assert result.succeeded is True
        assert "test_data" in result.output

    def test_execute_tool_step_with_variable_substitution(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="process_tool", description="Process", risk="read"))

        def process_handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result=f"Processed: {ctx.arguments.get('data', '')}",
            )

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_handler("process_tool", process_handler)

        step_executor = ToolExecutionStepExecutor(tool_executor=executor)

        step = WorkflowStep(
            step_id="tool_2",
            name="Variable Tool Step",
            action="process_tool",
            inputs={"data": "${previous_result}"},
        )

        variables = {"previous_result": "injected_data"}
        result = step_executor.execute(step, variables=variables)

        assert result.succeeded is True
        assert "injected_data" in result.output

    def test_execute_tool_step_failure(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="failing_tool", description="Fails", risk="read"))

        def failing_handler(ctx):
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="failed",
                error_message="Tool execution failed",
            )

        executor = SandboxedToolExecutor(registry=registry)
        executor.register_handler("failing_tool", failing_handler)

        step_executor = ToolExecutionStepExecutor(tool_executor=executor)

        step = WorkflowStep(
            step_id="fail_tool",
            name="Failing Tool Step",
            action="failing_tool",
        )

        result = step_executor.execute(step, variables={})

        assert result.succeeded is False
        assert result.status == "failed"


class TestWorkflowRunner:
    def test_run_sequential_steps(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Step done",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        workflow = Workflow(
            name="Sequential Test",
            steps=[
                WorkflowStep(step_id="s1", name="Step 1", action="act1"),
                WorkflowStep(step_id="s2", name="Step 2", action="act2"),
                WorkflowStep(step_id="s3", name="Step 3", action="act3"),
            ],
        )

        runner = WorkflowRunner(step_executor=executor)
        result = runner.run(workflow)

        assert result.succeeded is True
        assert len(result.step_results) == 3
        assert all(r.succeeded for r in result.step_results)

    def test_run_with_variable_passing(self):
        responses = [
            json.dumps({
                "summary": "First result",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            }),
            json.dumps({
                "summary": "Used first",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            }),
        ]

        call_count = [0]

        class SequentialCompiler:
            def deliberate(self, task, context):
                idx = call_count[0]
                call_count[0] += 1
                return responses[idx % len(responses)]

        executor = LLMDeliberationStepExecutor(compiler=SequentialCompiler())

        workflow = Workflow(
            name="Variable Passing Test",
            steps=[
                WorkflowStep(
                    step_id="v1",
                    name="First",
                    action="Produce data",
                    outputs=["data"],
                ),
                WorkflowStep(
                    step_id="v2",
                    name="Second",
                    action="Use data",
                    inputs={"prev": "${v1_summary}"},
                ),
            ],
        )

        runner = WorkflowRunner(step_executor=executor)
        result = runner.run(workflow)

        assert result.succeeded is True
        assert "v1_summary" in result.variables
        assert result.variables["v1_summary"] == "First result"

    def test_run_with_initial_variables(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Used initial",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        workflow = Workflow(
            name="Initial Vars Test",
            steps=[
                WorkflowStep(
                    step_id="iv1",
                    name="Step",
                    action="Use init vars",
                    inputs={"init": "${initial_key}"},
                ),
            ],
        )

        runner = WorkflowRunner(step_executor=executor)
        result = runner.run(workflow, initial_variables={"initial_key": "initial_value"})

        assert result.succeeded is True
        assert "initial_key" in result.variables
        assert result.variables["initial_key"] == "initial_value"

    def test_run_with_conditional_steps(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Conditional",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        workflow = Workflow(
            name="Conditional Test",
            steps=[
                WorkflowStep(step_id="c1", name="Always", action="act1"),
                WorkflowStep(
                    step_id="c2",
                    name="Conditional",
                    action="act2",
                    condition="True",
                ),
                WorkflowStep(
                    step_id="c3",
                    name="Skipped",
                    action="act3",
                    condition="False",
                ),
            ],
        )

        runner = WorkflowRunner(step_executor=executor)
        result = runner.run(workflow)

        assert result.succeeded is True
        assert len(result.step_results) == 3
        assert result.step_results[0].status == "succeeded"
        assert result.step_results[1].status == "succeeded"
        assert result.step_results[2].status == "skipped"

    def test_run_stop_on_error(self):
        class FailingCompiler:
            def deliberate(self, task, context):
                raise RuntimeError("Step failed")

        executor = LLMDeliberationStepExecutor(
            compiler=FailingCompiler(),
            fallback_to_deterministic=False,
        )

        workflow = Workflow(
            name="Error Stop Test",
            steps=[
                WorkflowStep(step_id="e1", name="Will Fail", action="act1"),
                WorkflowStep(step_id="e2", name="Should Not Run", action="act2"),
            ],
        )

        runner = WorkflowRunner(step_executor=executor, stop_on_error=True)
        result = runner.run(workflow)

        assert result.succeeded is False
        assert len(result.step_results) == 1
        assert result.step_results[0].status == "failed"

    def test_run_continue_on_error(self):
        responses = [
            "invalid json",
            json.dumps({
                "summary": "Second succeeded",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            }),
        ]

        call_count = [0]

        class MixedCompiler:
            def deliberate(self, task, context):
                idx = call_count[0]
                call_count[0] += 1
                return responses[idx % len(responses)]

        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Fallback",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        workflow = Workflow(
            name="Continue Test",
            steps=[
                WorkflowStep(step_id="cont1", name="Step 1", action="act1"),
                WorkflowStep(step_id="cont2", name="Step 2", action="act2"),
            ],
        )

        runner = WorkflowRunner(step_executor=executor, stop_on_error=False)
        result = runner.run(workflow)

        assert len(result.step_results) == 2

    def test_run_with_event_log(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Logged",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)
        event_log = EventLog()

        workflow = Workflow(
            name="Event Log Test",
            steps=[
                WorkflowStep(step_id="el1", name="Step", action="act1"),
            ],
        )

        runner = WorkflowRunner(step_executor=executor, event_log=event_log)
        result = runner.run(workflow)

        assert result.succeeded is True
        assert len(event_log.all()) >= 2

    def test_run_with_observability(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Observed",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        metrics = ExecutionMetricsCollector()
        observer = ExecutionObserver(metrics_collector=metrics)

        workflow = Workflow(
            name="Observability Test",
            steps=[
                WorkflowStep(step_id="obs1", name="Step 1", action="act1"),
                WorkflowStep(step_id="obs2", name="Step 2", action="act2"),
            ],
        )

        runner = WorkflowRunner(
            step_executor=executor,
            observer=observer,
        )
        result = runner.run(workflow)

        assert result.succeeded is True
        assert observer.metrics.total_events > 0

    def test_run_with_export(self, capsys):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Exported",
                "hypothesis": "test",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Test",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        metrics = ExecutionMetricsCollector()
        observer = ExecutionObserver(
            metrics_collector=metrics,
        )

        workflow = Workflow(
            name="Export Test",
            steps=[
                WorkflowStep(step_id="exp1", name="Step", action="act1"),
            ],
        )

        runner = WorkflowRunner(
            step_executor=executor,
            observer=observer,
        )
        result = runner.run_with_export(workflow)

        captured = capsys.readouterr()
        assert result.succeeded is True


class TestWorkflowIntegration:
    def test_full_workflow_with_all_features(self):
        compiler = StaticLLMDeliberationCompiler(
            response_json=json.dumps({
                "summary": "Integration test",
                "hypothesis": "full pipeline",
                "missing_information": [],
                "candidate_actions": ["propose_plan"],
                "chosen_action": "propose_plan",
                "rationale": "Integration",
                "stop_condition": "done",
            })
        )

        executor = LLMDeliberationStepExecutor(compiler=compiler)

        event_log = EventLog()
        metrics = ExecutionMetricsCollector()
        observer = ExecutionObserver(
            metrics_collector=metrics,
        )

        workflow = Workflow(
            name="Integration Test",
            steps=[
                WorkflowStep(
                    step_id="int1",
                    name="Initialize",
                    action="Setup",
                    inputs={"mode": "test"},
                    outputs=["setup_complete"],
                ),
                WorkflowStep(
                    step_id="int2",
                    name="Process",
                    action="Process",
                    inputs={"setup": "${int1_summary}"},
                    condition="'int1_summary' in variables",
                ),
                WorkflowStep(
                    step_id="int3",
                    name="Finalize",
                    action="Finalize",
                    inputs={"processed": "${int2_summary}"},
                ),
            ],
            metadata={"type": "integration"},
        )

        runner = WorkflowRunner(
            step_executor=executor,
            event_log=event_log,
            observer=observer,
        )
        result = runner.run(workflow)

        assert result.succeeded is True
        assert len(result.step_results) == 3
        assert all(r.succeeded for r in result.step_results)
        assert result.total_execution_time_ms > 0
        assert len(event_log.all()) >= 2
        assert observer.metrics.total_events > 0

    def test_workflow_serialization_roundtrip(self):
        workflow = Workflow(
            name="Roundtrip Test",
            steps=[
                WorkflowStep(
                    step_id="rt1",
                    name="Step 1",
                    action="act1",
                    inputs={"key": "value"},
                    outputs=["out1"],
                    condition="True",
                ),
                WorkflowStep(
                    step_id="rt2",
                    name="Step 2",
                    action="act2",
                    metadata={"priority": "high"},
                ),
            ],
            metadata={"version": "1.0"},
        )

        serialized = workflow.to_dict()
        restored = Workflow.from_dict(serialized)

        assert restored.name == workflow.name
        assert len(restored.steps) == len(workflow.steps)
        assert restored.steps[0].step_id == "rt1"
        assert restored.steps[0].inputs["key"] == "value"
        assert restored.steps[1].metadata["priority"] == "high"

    def test_workflow_with_tool_execution(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="transform", description="Transform", risk="read"))

        def transform_handler(ctx):
            input_data = ctx.arguments.get("input", "")
            return ToolExecutionResult(
                tool_name=ctx.tool_name,
                call_id=ctx.call_id,
                status="succeeded",
                result=f"transformed({input_data})",
            )

        tool_executor = SandboxedToolExecutor(registry=registry)
        tool_executor.register_handler("transform", transform_handler)

        step_executor = ToolExecutionStepExecutor(tool_executor=tool_executor)

        workflow = Workflow(
            name="Tool Workflow",
            steps=[
                WorkflowStep(
                    step_id="tw1",
                    name="Transform",
                    action="transform",
                    inputs={"input": "raw_data"},
                ),
            ],
        )

        runner = WorkflowRunner(step_executor=step_executor)
        result = runner.run(workflow)

        assert result.succeeded is True
        assert result.step_results[0].output == "transformed(raw_data)"
