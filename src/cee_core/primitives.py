"""Cognitive primitive contracts."""

from __future__ import annotations

from typing import Literal


CognitivePrimitive = Literal[
    "observe",
    "interpret",
    "hypothesize",
    "plan",
    "act",
    "verify",
    "reflect",
    "escalate",
]

ALL_COGNITIVE_PRIMITIVES: tuple[CognitivePrimitive, ...] = (
    "observe",
    "interpret",
    "hypothesize",
    "plan",
    "act",
    "verify",
    "reflect",
    "escalate",
)


def validate_primitives(values: tuple[str, ...]) -> tuple[CognitivePrimitive, ...]:
    """Validate a primitive sequence against the canonical primitive set."""

    invalid = [value for value in values if value not in ALL_COGNITIVE_PRIMITIVES]
    if invalid:
        raise ValueError(
            "Invalid cognitive primitives: " + ", ".join(sorted(set(invalid)))
        )
    return tuple(values)  # type: ignore[return-value]


def default_primitives_for_task_kind(kind: str) -> tuple[CognitivePrimitive, ...]:
    """Return the bounded default primitive sequence for a task kind."""

    if kind == "analysis":
        return ("observe", "interpret", "plan", "verify")
    if kind == "state_update":
        return ("observe", "interpret", "plan", "act", "verify", "escalate")
    raise ValueError(f"Unsupported task kind for primitive selection: {kind}")
