"""State primitives and deterministic patch reducer."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable, Literal

if TYPE_CHECKING:
    from .events import StateTransitionEvent

from .schemas import PATCH_SCHEMA_VERSION, require_schema_version


PatchOp = Literal["set", "append"]


@dataclass(frozen=True)
class StatePatch:
    """A minimal patch against a top-level state section."""

    section: str
    key: str
    op: PatchOp
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PATCH_SCHEMA_VERSION,
            "section": self.section,
            "key": self.key,
            "op": self.op,
            "value": deepcopy(self.value),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StatePatch":
        require_schema_version(payload, PATCH_SCHEMA_VERSION)
        return cls(
            section=payload["section"],
            key=payload["key"],
            op=payload["op"],
            value=deepcopy(payload.get("value")),
        )


@dataclass
class State:
    """Canonical runtime state.

    This is the fixed core state graph trunk.

    Domain-specific state should extend around this trunk through explicit
    plugins and contracts, not by bypassing reducer semantics.
    """

    memory: dict[str, Any] = field(default_factory=dict)
    goals: dict[str, Any] = field(default_factory=dict)
    beliefs: dict[str, Any] = field(default_factory=dict)
    self_model: dict[str, Any] = field(default_factory=dict)
    policy: dict[str, Any] = field(default_factory=dict)
    domain_data: dict[str, Any] = field(default_factory=dict)
    tool_affordances: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=lambda: {"version": 0})

    def snapshot(self) -> dict[str, Any]:
        return {
            "memory": deepcopy(self.memory),
            "goals": deepcopy(self.goals),
            "beliefs": deepcopy(self.beliefs),
            "self_model": deepcopy(self.self_model),
            "policy": deepcopy(self.policy),
            "domain_data": deepcopy(self.domain_data),
            "tool_affordances": deepcopy(self.tool_affordances),
            "meta": deepcopy(self.meta),
        }


_PATCHABLE_SECTIONS = {
    "memory",
    "goals",
    "beliefs",
    "self_model",
    "domain_data",
    "tool_affordances",
}


def apply_patch(state: State, patch: StatePatch) -> State:
    """Apply a deterministic patch and increment state version once."""

    if patch.section not in _PATCHABLE_SECTIONS:
        raise ValueError(f"Section is not patchable: {patch.section}")

    next_state = State(**state.snapshot())
    target = getattr(next_state, patch.section)

    if patch.op == "set":
        target[patch.key] = deepcopy(patch.value)
    elif patch.op == "append":
        current = target.setdefault(patch.key, [])
        if not isinstance(current, list):
            raise ValueError(f"Cannot append to non-list key: {patch.section}.{patch.key}")
        current.append(deepcopy(patch.value))
    else:
        raise ValueError(f"Unsupported patch operation: {patch.op}")

    next_state.meta["version"] = int(next_state.meta.get("version", 0)) + 1
    return next_state


def reduce_event(state: State, event: "StateTransitionEvent") -> State:
    """Apply one auditable transition if policy allows it."""

    if not event.policy_decision.allowed:
        raise PermissionError(
            f"Policy blocked state transition: {event.policy_decision.verdict}"
        )
    return apply_patch(state, event.patch)


def replay(events: Iterable["StateTransitionEvent"], initial_state: State | None = None) -> State:
    """Replay transition events into a deterministic final state."""

    state = initial_state or State()
    for event in events:
        state = reduce_event(state, event)
    return state
