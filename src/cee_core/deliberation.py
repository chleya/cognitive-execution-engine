"""Deterministic deliberation contracts for small-step execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from .schemas import REASONING_STEP_SCHEMA_VERSION, require_schema_version

if TYPE_CHECKING:
    from .tasks import TaskSpec
    from .tools import ToolRegistry


NextAction = Literal[
    "propose_plan",
    "request_read_tool",
    "request_approval",
    "propose_redirect",
    "stop",
]

_TERMINAL_ACTIONS: set[NextAction] = {"propose_plan", "propose_redirect", "stop"}

_MAX_CHAIN_LENGTH = 5


@dataclass(frozen=True)
class ReasoningStep:
    """A bounded deliberation frame that selects the next action only."""

    task_id: str
    summary: str
    hypothesis: str
    missing_information: tuple[str, ...]
    candidate_actions: tuple[NextAction, ...]
    chosen_action: NextAction
    rationale: str
    stop_condition: str
    step_id: str = field(default_factory=lambda: f"rs_{uuid4().hex}")

    @property
    def is_terminal(self) -> bool:
        return self.chosen_action in _TERMINAL_ACTIONS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": REASONING_STEP_SCHEMA_VERSION,
            "step_id": self.step_id,
            "task_id": self.task_id,
            "summary": self.summary,
            "hypothesis": self.hypothesis,
            "missing_information": list(self.missing_information),
            "candidate_actions": list(self.candidate_actions),
            "chosen_action": self.chosen_action,
            "rationale": self.rationale,
            "stop_condition": self.stop_condition,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ReasoningStep":
        require_schema_version(payload, REASONING_STEP_SCHEMA_VERSION)
        return cls(
            step_id=str(payload["step_id"]),
            task_id=str(payload["task_id"]),
            summary=str(payload["summary"]),
            hypothesis=str(payload["hypothesis"]),
            missing_information=tuple(payload.get("missing_information", ())),  # type: ignore[arg-type]
            candidate_actions=tuple(payload["candidate_actions"]),  # type: ignore[arg-type]
            chosen_action=payload["chosen_action"],  # type: ignore[arg-type]
            rationale=str(payload["rationale"]),
            stop_condition=str(payload["stop_condition"]),
        )


@dataclass(frozen=True)
class ReasoningChain:
    """An ordered sequence of reasoning steps leading to a terminal action.

    Each step is audited independently. The chain terminates when a step
    selects a terminal action (propose_plan, propose_redirect, or stop).

    The chain does not write canonical state, execute tools, or bypass
    planner/policy/approval. It only makes the next bounded step explicit.
    """

    steps: tuple[ReasoningStep, ...]
    chain_id: str = field(default_factory=lambda: f"rc_{uuid4().hex}")

    @property
    def final_action(self) -> NextAction:
        if not self.steps:
            return "propose_plan"
        return self.steps[-1].chosen_action

    @property
    def is_terminal(self) -> bool:
        if not self.steps:
            return False
        return self.steps[-1].is_terminal

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict[str, object]:
        return {
            "chain_id": self.chain_id,
            "step_count": self.step_count,
            "final_action": self.final_action,
            "is_terminal": self.is_terminal,
            "steps": [step.to_dict() for step in self.steps],
        }


def deliberate_next_action(
    task: "TaskSpec",
    *,
    tool_registry: "ToolRegistry | None" = None,
) -> ReasoningStep:
    """Choose the next bounded runtime action for the task."""

    candidate_actions: list[NextAction] = ["propose_plan"]
    missing_information: list[str] = []
    chosen_action: NextAction = "propose_plan"
    rationale = "Task has enough structure to proceed directly into deterministic planning."

    lowered_objective = task.objective.lower()
    supports_read_docs = tool_registry is not None and tool_registry.get("read_docs") is not None
    doc_tokens = ("read docs", "read documentation", "search docs", "search documentation")
    needs_docs_lookup = task.kind == "analysis" and any(token in lowered_objective for token in doc_tokens)

    if needs_docs_lookup:
        missing_information.append("External documentation evidence has not been observed yet.")
        candidate_actions.append("request_read_tool")
        if supports_read_docs:
            chosen_action = "request_read_tool"
            rationale = (
                "Task explicitly asks for documentation lookup and a read-only docs tool is available, "
                "so the next step should gather observations before extending the plan."
            )

    if task.risk_level != "low":
        candidate_actions.append("request_approval")
        if chosen_action == "propose_plan":
            rationale = (
                "Task includes medium-or-high risk state change semantics; planning should proceed with "
                "approval-aware transitions."
            )

    if task.kind == "analysis" and task.risk_level != "low":
        candidate_actions.append("propose_redirect")
        if chosen_action == "propose_plan":
            chosen_action = "propose_redirect"
            rationale = (
                "Analysis task with non-trivial risk; the current direction "
                "may benefit from exploration before committing to a plan."
            )

    if len(missing_information) >= 2:
        candidate_actions.append("propose_redirect")
        if chosen_action == "propose_plan":
            chosen_action = "propose_redirect"
            rationale = (
                "Task has multiple missing information items; the current task direction "
                "may be wrong. Propose a redirect to gather more context before planning."
            )

    return ReasoningStep(
        task_id=task.task_id,
        summary=f"Determine the next bounded action for task '{task.objective}'.",
        hypothesis=f"Task kind={task.kind}, risk_level={task.risk_level}, domain={task.domain_name}.",
        missing_information=tuple(missing_information),
        candidate_actions=tuple(dict.fromkeys(candidate_actions)),
        chosen_action=chosen_action,
        rationale=rationale,
        stop_condition="Stop after selecting the next action; execution is handled by later runtime stages.",
    )


def deliberate_chain(
    task: "TaskSpec",
    *,
    tool_registry: "ToolRegistry | None" = None,
    max_steps: int = _MAX_CHAIN_LENGTH,
) -> ReasoningChain:
    """Build a multi-step reasoning chain for a task.

    The chain continues deliberating until a terminal action is reached
    or the maximum step count is hit. Each step refines the reasoning
    based on the previous step's outcome.

    This never writes state, executes tools, or bypasses policy.
    """

    steps: list[ReasoningStep] = []
    for _ in range(max_steps):
        step = _deliberate_chain_step(task, steps, tool_registry=tool_registry)
        steps.append(step)
        if step.is_terminal:
            break

    return ReasoningChain(steps=tuple(steps))


def _deliberate_chain_step(
    task: "TaskSpec",
    previous_steps: list[ReasoningStep],
    *,
    tool_registry: "ToolRegistry | None" = None,
) -> ReasoningStep:
    """Compute one step in a reasoning chain, considering previous steps."""

    step_number = len(previous_steps) + 1
    gathered_info: list[str] = []
    for prev in previous_steps:
        if prev.chosen_action == "request_read_tool":
            gathered_info.append(f"Step {prev.step_id}: requested read tool")
        elif prev.chosen_action == "request_approval":
            gathered_info.append(f"Step {prev.step_id}: requested approval")

    base_step = deliberate_next_action(task, tool_registry=tool_registry)

    if step_number > 1 and base_step.chosen_action == "request_read_tool":
        already_requested_read = any(
            s.chosen_action == "request_read_tool" for s in previous_steps
        )
        if already_requested_read:
            return ReasoningStep(
                task_id=task.task_id,
                summary=f"Step {step_number}: read tool already requested, proceeding to plan.",
                hypothesis=base_step.hypothesis,
                missing_information=base_step.missing_information,
                candidate_actions=("propose_plan",),
                chosen_action="propose_plan",
                rationale="Read tool was already requested in a previous step; proceeding to planning.",
                stop_condition="Terminal: proceeding to plan after gathering observations.",
            )

    if step_number >= _MAX_CHAIN_LENGTH:
        return ReasoningStep(
            task_id=task.task_id,
            summary=f"Step {step_number}: maximum chain length reached, forcing plan.",
            hypothesis=base_step.hypothesis,
            missing_information=base_step.missing_information,
            candidate_actions=("propose_plan",),
            chosen_action="propose_plan",
            rationale="Maximum reasoning chain length reached; forcing plan proposal to avoid infinite deliberation.",
            stop_condition="Terminal: forced plan due to chain length limit.",
        )

    return base_step
