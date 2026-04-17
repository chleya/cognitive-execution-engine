"""Read-only in-memory tool runner.

This runner executes only explicitly registered read tools. It returns
ToolResultEvent and never mutates State.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .event_log import EventLog
from .tools import (
    ToolCallSpec,
    ToolRegistry,
    ToolResultEvent,
    evaluate_tool_call_policy,
)


ReadToolHandler = Callable[[dict[str, Any]], Any]


@dataclass
class InMemoryReadOnlyToolRunner:
    """Executes registered read-only in-memory tool handlers."""

    registry: ToolRegistry
    handlers: dict[str, ReadToolHandler] = field(default_factory=dict)

    def register_handler(self, tool_name: str, handler: ReadToolHandler) -> None:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Cannot register handler for unknown tool: {tool_name}")
        if tool.risk != "read":
            raise ValueError(f"Cannot register read-only handler for non-read tool: {tool_name}")
        if tool_name in self.handlers:
            raise ValueError(f"Handler already registered for tool: {tool_name}")
        self.handlers[tool_name] = handler

    def run(
        self,
        call: ToolCallSpec,
        *,
        event_log: EventLog | None = None,
    ) -> ToolResultEvent:
        decision = evaluate_tool_call_policy(call, self.registry)
        if not decision.allowed:
            event = ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=f"tool policy blocked execution: {decision.verdict}",
            )
            if event_log is not None:
                event_log.append(event)
            return event

        handler = self.handlers.get(call.tool_name)
        if handler is None:
            event = ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=f"no handler registered for tool: {call.tool_name}",
            )
            if event_log is not None:
                event_log.append(event)
            return event

        try:
            result = handler(call.arguments)
        except Exception as exc:
            event = ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=str(exc),
            )
            if event_log is not None:
                event_log.append(event)
            return event

        event = ToolResultEvent(
            call_id=call.call_id,
            tool_name=call.tool_name,
            status="succeeded",
            result=result,
        )
        if event_log is not None:
            event_log.append(event)
        return event

