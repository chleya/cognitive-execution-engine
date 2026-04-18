"""Workflow orchestration for multi-step task execution.

Provides bounded workflow definition and execution with audit trail,
policy enforcement, and observability integration.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol
from uuid import uuid4

from .event_log import EventLog
from .events import Event
from .llm_deliberation import LLMDeliberationCompiler, TaskSpec, deliberate_with_llm
from .observability import (
    ConsoleMetricsExporter,
    ExecutionMetricsCollector,
    ExecutionObserver,
    ExecutionPhase,
)
from .tool_executor import SandboxedToolExecutor, ToolExecutionResult, ToolExecutionContext
from .tools import ToolCallSpec, ToolRegistry, ToolResultEvent


@dataclass(frozen=True)
class WorkflowStep:
    """A single step in a workflow."""

    step_id: str
    name: str
    action: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    timeout_seconds: float = 30.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "condition": self.condition,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowStep":
        return cls(
            step_id=str(payload["step_id"]),
            name=str(payload["name"]),
            action=str(payload["action"]),
            inputs=payload.get("inputs", {}),
            outputs=payload.get("outputs", []),
            condition=payload.get("condition"),
            timeout_seconds=float(payload.get("timeout_seconds", 30.0)),
            retry_count=int(payload.get("retry_count", 0)),
            metadata=payload.get("metadata", {}),
        )


@dataclass(frozen=True)
class Workflow:
    """A multi-step workflow definition."""

    name: str
    steps: List[WorkflowStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    workflow_id: str = field(default_factory=lambda: f"wf_{uuid4().hex}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Workflow":
        steps = [
            WorkflowStep.from_dict(s)
            for s in payload.get("steps", [])
        ]
        return cls(
            name=str(payload["name"]),
            steps=steps,
            metadata=payload.get("metadata", {}),
            workflow_id=str(payload.get("workflow_id", f"wf_{uuid4().hex}")),
        )


@dataclass(frozen=True)
class StepResult:
    """Result from executing a workflow step."""

    step_id: str
    status: str
    output: Any = None
    error_message: str = ""
    execution_time_ms: float = 0.0
    variables: Dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "output": self.output,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "variables": self.variables,
        }


@dataclass(frozen=True)
class WorkflowResult:
    """Result from executing a workflow."""

    workflow_id: str
    status: str
    step_results: List[StepResult] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    total_execution_time_ms: float = 0.0
    error_message: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "step_results": [r.to_dict() for r in self.step_results],
            "variables": self.variables,
            "total_execution_time_ms": self.total_execution_time_ms,
            "error_message": self.error_message,
        }


class StepExecutor(Protocol):
    """Protocol for executing workflow steps."""

    def execute(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any],
        event_log: Optional[EventLog] = None,
    ) -> StepResult:
        """Execute a workflow step and return result."""


@dataclass(frozen=True)
class LLMDeliberationStepExecutor:
    """Executes workflow steps using LLM deliberation."""

    compiler: LLMDeliberationCompiler
    tool_registry: Optional[ToolRegistry] = None
    fallback_to_deterministic: bool = True

    def execute(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any],
        event_log: Optional[EventLog] = None,
    ) -> StepResult:
        start_time = time.monotonic()

        context = self._build_context(step, variables)

        task = TaskSpec(
            objective=step.action,
            kind="analysis",
            success_criteria=(f"Step {step.name} completed",),
            requested_primitives=("deliberate",),
            task_id=f"wf_task_{step.step_id}",
            domain_name="workflow",
        )

        try:
            reasoning_step = deliberate_with_llm(
                task=task,
                compiler=self.compiler,
                tool_registry=self.tool_registry,
                context=context,
                fallback_to_deterministic=self.fallback_to_deterministic,
            )

            execution_time_ms = (time.monotonic() - start_time) * 1000.0

            result = StepResult(
                step_id=step.step_id,
                status="succeeded",
                output=reasoning_step.to_dict(),
                variables={
                    f"{step.step_id}_summary": reasoning_step.summary,
                    f"{step.step_id}_rationale": reasoning_step.rationale,
                    f"{step.step_id}_chosen_action": reasoning_step.chosen_action,
                },
                execution_time_ms=execution_time_ms,
            )

            if event_log is not None:
                event_log.append(
                    Event(
                        event_type="workflow.step.completed",
                        payload={
                            "step_id": step.step_id,
                            "step_name": step.name,
                            "status": "succeeded",
                            "execution_time_ms": execution_time_ms,
                        },
                        actor="workflow_runner",
                    )
                )

            return result

        except Exception as exc:
            execution_time_ms = (time.monotonic() - start_time) * 1000.0

            result = StepResult(
                step_id=step.step_id,
                status="failed",
                error_message=str(exc),
                execution_time_ms=execution_time_ms,
            )

            if event_log is not None:
                event_log.append(
                    Event(
                        event_type="workflow.step.failed",
                        payload={
                            "step_id": step.step_id,
                            "step_name": step.name,
                            "error": str(exc),
                            "execution_time_ms": execution_time_ms,
                        },
                        actor="workflow_runner",
                    )
                )

            return result

    def _build_context(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any],
    ) -> str:
        parts = []

        if variables:
            parts.append("Available variables from previous steps:")
            for key, value in variables.items():
                parts.append(f"  {key}: {value}")

        if step.inputs:
            parts.append("Step inputs:")
            for key, value in step.inputs.items():
                parts.append(f"  {key}: {value}")

        if self.tool_registry:
            available_tools = self.tool_registry.list()
            if available_tools:
                tools_str = ", ".join(t.name for t in available_tools)
                parts.append(f"Available tools: {tools_str}")

        return "\n".join(parts)


@dataclass(frozen=True)
class ToolExecutionStepExecutor:
    """Executes workflow steps using tool executor."""

    tool_executor: SandboxedToolExecutor

    def execute(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any],
        event_log: Optional[EventLog] = None,
    ) -> StepResult:
        start_time = time.monotonic()

        arguments = dict(step.inputs)
        for key, value in arguments.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                if var_name in variables:
                    arguments[key] = variables[var_name]

        call = ToolCallSpec(
            tool_name=step.action,
            arguments=arguments,
            call_id=f"wf_toolcall_{step.step_id}",
        )

        try:
            result_event = self.tool_executor.execute(call, event_log=event_log)

            execution_time_ms = (time.monotonic() - start_time) * 1000.0

            if result_event.status == "succeeded":
                return StepResult(
                    step_id=step.step_id,
                    status="succeeded",
                    output=result_event.result,
                    variables={
                        f"{step.step_id}_result": result_event.result,
                    },
                    execution_time_ms=execution_time_ms,
                )
            else:
                return StepResult(
                    step_id=step.step_id,
                    status="failed",
                    error_message=result_event.error_message,
                    execution_time_ms=execution_time_ms,
                )

        except Exception as exc:
            execution_time_ms = (time.monotonic() - start_time) * 1000.0

            return StepResult(
                step_id=step.step_id,
                status="failed",
                error_message=str(exc),
                execution_time_ms=execution_time_ms,
            )


_FORBIDDEN_NAMES = frozenset({
    "__import__", "__class__", "exec", "eval", "compile",
    "open", "getattr", "setattr", "delattr",
})


def _check_dunder(name: str) -> bool:
    return "__" in name


def _is_node_safe(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if child.id in _FORBIDDEN_NAMES or _check_dunder(child.id):
                return False
        if isinstance(child, ast.Attribute):
            if _check_dunder(child.attr):
                return False
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name) and child.func.id in _FORBIDDEN_NAMES:
                return False
    return True


def _eval_node(node: ast.AST, variables: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
        if node.id == "variables":
            return variables
        if node.id in variables:
            return variables[node.id]
        raise ValueError(f"Unknown name: {node.id}")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, variables)
            if isinstance(op, ast.Eq):
                result = left == right
            elif isinstance(op, ast.NotEq):
                result = left != right
            elif isinstance(op, ast.Gt):
                result = left > right
            elif isinstance(op, ast.Lt):
                result = left < right
            elif isinstance(op, ast.GtE):
                result = left >= right
            elif isinstance(op, ast.LtE):
                result = left <= right
            elif isinstance(op, ast.In):
                result = left in right
            elif isinstance(op, ast.NotIn):
                result = left not in right
            else:
                raise ValueError(f"Unsupported operator: {type(op).__name__}")
            if not result:
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            obj = _eval_node(node.func.value, variables)
            method_name = node.func.attr
            if method_name == "get" and isinstance(obj, dict):
                if len(node.args) >= 1:
                    key = _eval_node(node.args[0], variables)
                    default = (
                        _eval_node(node.args[1], variables)
                        if len(node.args) >= 2
                        else None
                    )
                    return obj.get(key, default)
            raise ValueError(f"Unsupported method: {method_name}")
        raise ValueError("Unsupported call expression")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        operand = _eval_node(node.operand, variables)
        return not operand

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _eval_node(value, variables):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value in node.values:
                if _eval_node(value, variables):
                    return True
            return False

    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def _evaluate_condition(
    condition: str,
    variables: Dict[str, Any],
) -> bool:
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError:
        return False

    if not _is_node_safe(tree):
        return False

    try:
        result = _eval_node(tree.body, variables)
        return bool(result)
    except Exception:
        return False


@dataclass
class WorkflowRunner:
    """Executes workflow steps sequentially with variable passing."""

    step_executor: StepExecutor
    event_log: Optional[EventLog] = None
    observer: Optional[ExecutionObserver] = None
    stop_on_error: bool = True

    def run(
        self,
        workflow: Workflow,
        initial_variables: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        start_time = time.monotonic()

        if self.observer is not None:
            self.observer.metrics.start_phase(ExecutionPhase.EXECUTION)

        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="workflow.started",
                    payload={
                        "workflow_id": workflow.workflow_id,
                        "workflow_name": workflow.name,
                        "step_count": len(workflow.steps),
                    },
                    actor="workflow_runner",
                )
            )

        variables = dict(initial_variables or {})
        step_results: List[StepResult] = []

        for step in workflow.steps:
            if step.condition is not None:
                if not _evaluate_condition(step.condition, variables):
                    if self.event_log is not None:
                        self.event_log.append(
                            Event(
                                event_type="workflow.step.skipped",
                                payload={
                                    "step_id": step.step_id,
                                    "step_name": step.name,
                                    "reason": "condition_not_met",
                                    "condition": step.condition,
                                },
                                actor="workflow_runner",
                            )
                        )

                    skipped = StepResult(
                        step_id=step.step_id,
                        status="skipped",
                        variables={},
                    )
                    step_results.append(skipped)

                    if self.observer is not None:
                        self.observer.metrics.record_event(
                            Event(
                                event_type="workflow.step.skipped",
                                payload={"step_id": step.step_id},
                                actor="workflow_runner",
                            )
                        )

                    continue

            if self.observer is not None:
                self.observer.metrics.record_metric(
                    name="workflow.step.started",
                    value=1,
                    unit="count",
                    tags={"step_id": step.step_id, "step_name": step.name},
                )

            result = self.step_executor.execute(
                step=step,
                variables=variables,
                event_log=self.event_log,
            )

            step_results.append(result)

            if self.observer is not None:
                self.observer.metrics.record_tool_execution_time(
                    result.execution_time_ms
                )
                self.observer.metrics.record_event(
                    Event(
                        event_type="workflow.step.completed",
                        payload={
                            "step_id": step.step_id,
                            "status": result.status,
                        },
                        actor="workflow_runner",
                    )
                )

            if result.succeeded:
                variables.update(result.variables)
            elif result.status != "skipped":
                if self.stop_on_error:
                    total_execution_time_ms = (time.monotonic() - start_time) * 1000.0

                    if self.observer is not None:
                        self.observer.metrics.end_phase(ExecutionPhase.EXECUTION)
                        self.observer.metrics.record_error(result.error_message)

                    return WorkflowResult(
                        workflow_id=workflow.workflow_id,
                        status="failed",
                        step_results=step_results,
                        variables=variables,
                        total_execution_time_ms=total_execution_time_ms,
                        error_message=result.error_message,
                    )

        total_execution_time_ms = (time.monotonic() - start_time) * 1000.0

        if self.observer is not None:
            self.observer.metrics.end_phase(ExecutionPhase.EXECUTION)

        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="workflow.completed",
                    payload={
                        "workflow_id": workflow.workflow_id,
                        "workflow_name": workflow.name,
                        "status": "succeeded",
                        "total_execution_time_ms": total_execution_time_ms,
                        "step_count": len(step_results),
                    },
                    actor="workflow_runner",
                )
            )

        return WorkflowResult(
            workflow_id=workflow.workflow_id,
            status="succeeded",
            step_results=step_results,
            variables=variables,
            total_execution_time_ms=total_execution_time_ms,
        )

    def run_with_export(
        self,
        workflow: Workflow,
        initial_variables: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        result = self.run(workflow, initial_variables)

        if self.observer is not None:
            self.observer.export_metrics()

        return result
