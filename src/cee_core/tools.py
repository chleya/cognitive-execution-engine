"""Tool contract primitives.

Stage 1D introduces tool availability as structure, not execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4


ToolRisk = Literal["read", "write", "external_side_effect"]


@dataclass(frozen=True)
class ToolSpec:
    """A tool that may be referenced by plans or policy."""

    name: str
    description: str
    risk: ToolRisk
    input_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_approval(self) -> bool:
        return self.risk in {"write", "external_side_effect"}


@dataclass(frozen=True)
class ToolCallSpec:
    """A proposed tool call, not an executed call."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str = field(default_factory=lambda: f"toolcall_{uuid4().hex}")


@dataclass(frozen=True)
class ToolPolicyDecision:
    """Policy result for a proposed tool call."""

    verdict: Literal["allow", "deny", "requires_approval"]
    reason: str
    tool_name: str

    @property
    def allowed(self) -> bool:
        return self.verdict == "allow"

    @property
    def blocked(self) -> bool:
        return self.verdict in {"deny", "requires_approval"}

    def to_dict(self) -> dict[str, str]:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class ToolCallEvent:
    """Audit event for a proposed tool call and policy verdict."""

    call: ToolCallSpec
    decision: ToolPolicyDecision
    actor: str = "tool_policy"

    @property
    def event_type(self) -> str:
        return "tool.call.proposed"

    @property
    def trace_id(self) -> str:
        return self.call.call_id

    def to_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "call": {
                "call_id": self.call.call_id,
                "tool_name": self.call.tool_name,
                "arguments": self.call.arguments,
            },
            "decision": self.decision.to_dict(),
        }


@dataclass(frozen=True)
class ToolResultEvent:
    """Audit event for a future tool result.

    This event records a result shape only. It does not imply that CEE executed
    the tool; execution runners are a later boundary.
    """

    call_id: str
    tool_name: str
    status: Literal["succeeded", "failed"]
    result: Any | None = None
    error_message: str = ""
    actor: str = "tool_runner"

    @property
    def event_type(self) -> str:
        return "tool.call.result"

    @property
    def trace_id(self) -> str:
        return self.call_id

    def to_dict(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "result": self.result,
            "error_message": self.error_message,
        }


@dataclass
class ToolRegistry:
    """In-memory registry of declared tools."""

    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())


def evaluate_tool_call_policy(
    call: ToolCallSpec,
    registry: ToolRegistry,
) -> ToolPolicyDecision:
    """Evaluate policy for a proposed tool call without executing it."""

    tool = registry.get(call.tool_name)
    if tool is None:
        return ToolPolicyDecision(
            verdict="deny",
            reason=f"unknown tool: {call.tool_name}",
            tool_name=call.tool_name,
        )

    if tool.risk == "read":
        return ToolPolicyDecision(
            verdict="allow",
            reason="read tool allowed by Stage 1D policy",
            tool_name=tool.name,
        )

    if tool.risk == "write":
        return ToolPolicyDecision(
            verdict="requires_approval",
            reason="write tool requires approval",
            tool_name=tool.name,
        )

    return ToolPolicyDecision(
        verdict="requires_approval",
        reason="external side effect tool requires approval",
        tool_name=tool.name,
    )


def build_tool_call_event(
    call: ToolCallSpec,
    registry: ToolRegistry,
    *,
    actor: str = "tool_policy",
) -> ToolCallEvent:
    """Build an audit-only tool call event with policy decision."""

    return ToolCallEvent(
        call=call,
        decision=evaluate_tool_call_policy(call, registry),
        actor=actor,
    )
