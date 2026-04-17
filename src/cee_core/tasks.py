"""Task specification and deterministic task compiler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from .event_log import EventLog
from .events import Event
from .primitives import (
    CognitivePrimitive,
    default_primitives_for_task_kind,
    validate_primitives,
)
from .schemas import TASK_SCHEMA_VERSION, require_schema_version


TaskKind = Literal["analysis", "state_update"]
TaskLevel = Literal["L0", "L1", "L2", "L3", "L4"]


@dataclass(frozen=True)
class TaskSpec:
    """Structured task compiled from user input."""

    objective: str
    kind: TaskKind
    success_criteria: tuple[str, ...]
    requested_primitives: tuple[CognitivePrimitive, ...]
    risk_level: Literal["low", "medium", "high"] = "low"
    task_level: TaskLevel = "L1"
    task_id: str = field(default_factory=lambda: f"task_{uuid4().hex}")
    raw_input: str = ""
    domain_name: str = "core"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "domain_name": self.domain_name,
            "objective": self.objective,
            "kind": self.kind,
            "risk_level": self.risk_level,
            "task_level": self.task_level,
            "success_criteria": list(self.success_criteria),
            "requested_primitives": list(self.requested_primitives),
            "raw_input": self.raw_input,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "TaskSpec":
        require_schema_version(payload, TASK_SCHEMA_VERSION)
        return cls(
            task_id=str(payload["task_id"]),
            domain_name=str(payload.get("domain_name", "core")),
            objective=str(payload["objective"]),
            kind=payload["kind"],  # type: ignore[arg-type]
            risk_level=payload.get("risk_level", "low"),  # type: ignore[arg-type]
            task_level=payload.get("task_level", "L1"),  # type: ignore[arg-type]
            success_criteria=tuple(payload.get("success_criteria", ())),  # type: ignore[arg-type]
            requested_primitives=validate_primitives(
                tuple(payload.get("requested_primitives", ()))  # type: ignore[arg-type]
            ),
            raw_input=str(payload.get("raw_input", "")),
        )


def compile_task(
    raw_input: str,
    *,
    event_log: EventLog | None = None,
    domain_name: str = "core",
) -> TaskSpec:
    """Compile raw user input into a minimal structured task.

    This is intentionally deterministic. A later LLM compiler must preserve the
    same boundary: raw language becomes TaskSpec before planning.
    """

    normalized = " ".join(raw_input.strip().split())
    if not normalized:
        raise ValueError("raw_input cannot be empty")

    lowered = normalized.lower()
    kind: TaskKind = "analysis"
    risk_level: Literal["low", "medium", "high"] = "low"

    update_tokens = (
        "update",
        "set",
        "write",
        "\u4fee\u6539",  # 修改
        "\u5199\u5165",  # 写入
        "\u66f4\u65b0",  # 更新
    )

    if any(token in lowered for token in update_tokens):
        kind = "state_update"
        risk_level = "medium"

    task_level = classify_task_level(
        objective=normalized,
        kind=kind,
        risk_level=risk_level,
    )

    task = TaskSpec(
        domain_name=domain_name,
        objective=normalized,
        kind=kind,
        risk_level=risk_level,
        task_level=task_level,
        success_criteria=(
            "task is represented as structured state",
            "planner receives TaskSpec, not raw user input",
            "policy evaluates every proposed mutation",
        ),
        requested_primitives=default_primitives_for_task_kind(kind),
        raw_input=raw_input,
    )

    if event_log is not None:
        event_log.append(
            Event(
                event_type="task.received",
                payload={
                    "task_id": task.task_id,
                    "domain_name": task.domain_name,
                    "kind": task.kind,
                    "risk_level": task.risk_level,
                    "task_level": task.task_level,
                    "objective": task.objective,
                    "requested_primitives": list(task.requested_primitives),
                },
                actor="task_compiler",
            )
        )

    return task


def classify_task_level(
    *,
    objective: str,
    kind: TaskKind,
    risk_level: Literal["low", "medium", "high"],
) -> TaskLevel:
    """Classify a task into a bounded execution level.

    L0: single lookup or inspection
    L1: bounded local analysis
    L2: multi-step analysis or standard state update
    L3: cross-surface or migration-heavy task
    L4: highest-impact governance or approval-heavy task
    """

    lowered = objective.lower()

    if risk_level == "high":
        return "L4"

    l4_tokens = ("governance", "release", "production", "approval", "authorize")
    if any(token in lowered for token in l4_tokens):
        return "L4"

    l3_tokens = (
        "migrate",
        "migration",
        "cross-session",
        "cross domain",
        "cross-domain",
        "coordinate",
        "orchestrate",
        "plugin",
        "domain",
    )
    if any(token in lowered for token in l3_tokens):
        return "L3"

    if kind == "state_update" or risk_level == "medium":
        return "L2"

    l0_tokens = (
        "read",
        "search",
        "lookup",
        "look up",
        "inspect",
        "check",
        "show",
        "list",
    )
    if any(token in lowered for token in l0_tokens):
        return "L0"

    l2_analysis_tokens = ("compare", "summarize", "investigate", "trace", "analyze")
    if any(token in lowered for token in l2_analysis_tokens):
        return "L1"

    return "L1"
