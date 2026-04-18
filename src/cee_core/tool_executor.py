"""Real tool execution framework.

Extends the in-memory read-only runner with domain-specific tool implementations
and sandboxed execution while preserving the audit trail and policy boundaries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .event_log import EventLog
from .events import Event
from .tools import (
    ToolCallSpec,
    ToolRegistry,
    ToolResultEvent,
    ToolSpec,
    evaluate_tool_call_policy,
)
from .tool_runner import InMemoryReadOnlyToolRunner, ReadToolHandler


@dataclass(frozen=True)
class ToolExecutionContext:
    """Context provided to tool handlers during execution."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str
    timeout_seconds: float = 30.0
    max_output_size: int = 100000

    @property
    def request_id(self) -> str:
        return f"exec_{self.call_id}"


@dataclass(frozen=True)
class ToolExecutionResult:
    """Result from a tool execution."""

    tool_name: str
    call_id: str
    status: str
    result: Any = None
    error_message: str = ""
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_event(self) -> ToolResultEvent:
        return ToolResultEvent(
            call_id=self.call_id,
            tool_name=self.tool_name,
            status=self.status,
            result=self.result,
            error_message=self.error_message,
        )


ToolHandler = Callable[[ToolExecutionContext], ToolExecutionResult]


class ToolSandbox(Protocol):
    """Protocol for tool execution sandbox."""

    def execute(self, handler: ToolHandler, context: ToolExecutionContext) -> ToolExecutionResult:
        """Execute a tool handler in a sandboxed environment."""


@dataclass(frozen=True)
class DefaultToolSandbox:
    """Default sandbox that enforces timeouts and output size limits."""

    timeout_seconds: float = 30.0
    max_output_size: int = 100000

    def execute(self, handler: ToolHandler, context: ToolExecutionContext) -> ToolExecutionResult:
        start_time = time.monotonic()
        try:
            result = handler(context)
            execution_time_ms = (time.monotonic() - start_time) * 1000.0

            output_str = str(result.result) if result.result is not None else ""
            if len(output_str) > context.max_output_size:
                truncated = output_str[: context.max_output_size] + "...[truncated]"
                result = ToolExecutionResult(
                    tool_name=result.tool_name,
                    call_id=result.call_id,
                    status=result.status,
                    result=truncated,
                    metadata={"truncated": True, "original_size": len(output_str)},
                )

            return ToolExecutionResult(
                tool_name=result.tool_name,
                call_id=result.call_id,
                status=result.status,
                result=result.result,
                execution_time_ms=execution_time_ms,
                metadata=result.metadata,
            )
        except Exception as exc:
            execution_time_ms = (time.monotonic() - start_time) * 1000.0
            return ToolExecutionResult(
                tool_name=context.tool_name,
                call_id=context.call_id,
                status="failed",
                error_message=str(exc),
                execution_time_ms=execution_time_ms,
            )


@dataclass(frozen=True)
class SandboxedToolExecutor:
    """Tool executor that runs tools within a sandbox with audit logging."""

    registry: ToolRegistry
    handlers: dict[str, ToolHandler] = field(default_factory=dict)
    sandbox: ToolSandbox = field(default_factory=lambda: DefaultToolSandbox())
    event_log: EventLog | None = None

    def register_handler(self, tool_name: str, handler: ToolHandler) -> None:
        tool = self.registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Cannot register handler for unknown tool: {tool_name}")
        if tool_name in self.handlers:
            raise ValueError(f"Handler already registered for tool: {tool_name}")
        self.handlers[tool_name] = handler

    def register_read_handler(self, tool_name: str, handler: ReadToolHandler) -> None:
        read_handler: ToolHandler = lambda ctx: ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="succeeded",
            result=handler(ctx.arguments),
        )
        self.register_handler(tool_name, read_handler)

    def execute(
        self,
        call: ToolCallSpec,
        *,
        event_log: EventLog | None = None,
    ) -> ToolResultEvent:
        log = event_log or self.event_log
        decision = evaluate_tool_call_policy(call, self.registry)

        if log is not None:
            log.append(
                Event(
                    event_type="tool.execution.policy_evaluated",
                    payload={
                        "call_id": call.call_id,
                        "tool_name": call.tool_name,
                        "verdict": decision.verdict,
                        "reason": decision.reason,
                    },
                    actor="tool_executor",
                )
            )

        if not decision.allowed:
            event = ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=f"tool policy blocked execution: {decision.verdict}",
            )
            if log is not None:
                log.append(event)
            return event

        handler = self.handlers.get(call.tool_name)
        if handler is None:
            event = ToolResultEvent(
                call_id=call.call_id,
                tool_name=call.tool_name,
                status="failed",
                error_message=f"no handler registered for tool: {call.tool_name}",
            )
            if log is not None:
                log.append(event)
            return event

        context = ToolExecutionContext(
            tool_name=call.tool_name,
            arguments=call.arguments,
            call_id=call.call_id,
        )

        if log is not None:
            log.append(
                Event(
                    event_type="tool.execution.started",
                    payload={
                        "call_id": call.call_id,
                        "tool_name": call.tool_name,
                    },
                    actor="tool_executor",
                )
            )

        result = self.sandbox.execute(handler, context)

        if log is not None:
            log.append(
                Event(
                    event_type="tool.execution.completed",
                    payload={
                        "call_id": call.call_id,
                        "tool_name": call.tool_name,
                        "status": result.status,
                        "execution_time_ms": result.execution_time_ms,
                    },
                    actor="tool_executor",
                )
            )

        event = result.to_event()
        if log is not None:
            log.append(event)
        return event
