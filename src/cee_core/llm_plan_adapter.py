"""LLM-driven plan generation adapter.

Replaces deterministic patch generation with LLM-powered plan synthesis
while preserving the PlanSpec contract, policy evaluation, and audit trail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from .event_log import EventLog
from .events import Event
from .llm_provider import LLMProvider, LLMProviderRequest
from .planner import PlanSpec, plan_from_task
from .state import StatePatch
from .tasks import TaskSpec
from .tools import ToolCallSpec, ToolRegistry
from .deliberation import ReasoningStep


class LLMPlanCompiler(Protocol):
    """Protocol for an LLM that produces PlanSpec-like structures."""

    def compile_plan(self, task: TaskSpec, context: str) -> str:
        """Return a JSON string representing plan patches and tool calls."""


@dataclass(frozen=True)
class StaticLLMPlanCompiler:
    """Deterministic fake plan compiler for tests."""

    response_json: str

    def compile_plan(self, task: TaskSpec, context: str) -> str:
        return self.response_json


@dataclass(frozen=True)
class ProviderBackedPlanCompiler:
    """LLM plan compiler backed by a provider-neutral interface."""

    provider: LLMProvider
    event_log: EventLog | None = None

    def compile_plan(self, task: TaskSpec, context: str) -> str:
        prompt = build_plan_compiler_prompt(task, context)
        request = LLMProviderRequest(prompt=prompt)
        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.plan_compiler.requested",
                    payload={
                        "request_id": request.request_id,
                        "provider_name": self.provider.provider_name,
                        "task_id": task.task_id,
                    },
                    actor="llm_plan_compiler",
                )
            )

        try:
            response = self.provider.complete(request)
        except RuntimeError as exc:
            if self.event_log is not None:
                error = exc.args[0] if exc.args else None
                payload = {
                    "request_id": request.request_id,
                    "provider_name": self.provider.provider_name,
                    "task_id": task.task_id,
                    "error_type": type(exc).__name__,
                }
                if hasattr(error, "kind"):
                    payload["kind"] = error.kind
                if hasattr(error, "message"):
                    payload["message"] = error.message
                self.event_log.append(
                    Event(
                        event_type="llm.plan_compiler.failed",
                        payload=payload,
                        actor="llm_plan_compiler",
                    )
                )
            raise

        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.plan_compiler.succeeded",
                    payload={
                        "request_id": response.request_id,
                        "provider_name": response.provider_name,
                        "model_name": response.model_name,
                        "response_length": len(response.response_text),
                    },
                    actor="llm_plan_compiler",
                )
            )
        return response.response_text


def build_plan_compiler_prompt(task: TaskSpec, context: str) -> dict[str, object]:
    """Build a structured prompt for LLM plan generation."""

    return {
        "role": "plan_compiler",
        "instruction": (
            "Generate a plan as a JSON object with state patches and optional tool calls. "
            "Do not execute anything. Only describe the intended state changes and tool usage. "
            "All patches must use valid operations: set, append, merge, or delete."
        ),
        "allowed_schema": {
            "patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section", "key", "op", "value"],
                    "properties": {
                        "section": {"type": "string"},
                        "key": {"type": "string"},
                        "op": {"type": "string", "enum": ["set", "append", "merge", "delete"]},
                        "value": {},
                    },
                },
            },
            "tool_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["tool_name", "arguments"],
                    "properties": {
                        "tool_name": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                },
            },
            "rationale": {"type": "string"},
        },
        "task": {
            "task_id": task.task_id,
            "objective": task.objective,
            "kind": task.kind,
            "risk_level": task.risk_level,
            "task_level": task.task_level,
            "domain_name": task.domain_name,
            "success_criteria": list(task.success_criteria),
            "requested_primitives": list(task.requested_primitives),
        },
        "context": context,
    }


def parse_llm_plan_response(
    response_json: str,
    task: TaskSpec,
    *,
    actor: str = "llm_planner",
) -> PlanSpec:
    """Parse and validate an LLM-produced plan payload."""

    try:
        payload = json.loads(response_json)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM plan compiler returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("LLM plan compiler response must be a JSON object")

    patches_data = payload.get("patches", [])
    if not isinstance(patches_data, list):
        raise ValueError("LLM plan compiler response must contain a patches array")

    patches = []
    for patch_data in patches_data:
        if not isinstance(patch_data, dict):
            raise ValueError("Each patch must be a JSON object")
        if "section" not in patch_data or "key" not in patch_data:
            raise ValueError("Each patch must have section and key fields")
        if "op" not in patch_data:
            raise ValueError("Each patch must have an op field")
        if patch_data["op"] not in ("set", "append", "merge", "delete"):
            raise ValueError(f"Invalid patch op: {patch_data['op']}")

        patches.append(
            StatePatch(
                section=str(patch_data["section"]),
                key=str(patch_data["key"]),
                op=str(patch_data["op"]),
                value=patch_data.get("value"),
            )
        )

    tool_calls_data = payload.get("tool_calls", [])
    if not isinstance(tool_calls_data, list):
        tool_calls_data = []

    tool_calls = []
    for tc_data in tool_calls_data:
        if not isinstance(tc_data, dict):
            continue
        if "tool_name" not in tc_data or "arguments" not in tc_data:
            continue
        tool_calls.append(
            ToolCallSpec(
                tool_name=str(tc_data["tool_name"]),
                arguments=tc_data["arguments"],
            )
        )

    return PlanSpec(
        objective=task.objective,
        candidate_patches=tuple(patches),
        proposed_tool_calls=tuple(tool_calls),
        actor=actor,
    )


def plan_with_llm(
    task: TaskSpec,
    compiler: LLMPlanCompiler,
    *,
    tool_registry: ToolRegistry | None = None,
    reasoning_step: ReasoningStep | None = None,
    context: str = "",
    fallback_to_deterministic: bool = True,
    actor: str = "llm_planner",
) -> PlanSpec:
    """Generate a plan using LLM with deterministic fallback."""

    full_context = _build_plan_context(task, tool_registry, reasoning_step, context)

    try:
        response = compiler.compile_plan(task, full_context)
        plan = parse_llm_plan_response(response, task, actor=actor)
        return plan
    except Exception:
        if fallback_to_deterministic:
            return plan_from_task(
                task,
                actor=actor,
                tool_registry=tool_registry,
                reasoning_step=reasoning_step,
            )
        raise


def _build_plan_context(
    task: TaskSpec,
    tool_registry: ToolRegistry | None,
    reasoning_step: ReasoningStep | None,
    context: str,
) -> str:
    """Build the plan generation context string."""

    parts = []

    if context:
        parts.append(context)

    if reasoning_step is not None:
        parts.append(
            f"Reasoning: chosen_action={reasoning_step.chosen_action}, "
            f"rationale={reasoning_step.rationale}"
        )

    if tool_registry is not None:
        available_tools = tool_registry.list()
        if available_tools:
            tools_str = ", ".join(
                f"{t.name} (risk={t.risk})" for t in available_tools
            )
            parts.append(f"Available tools: {tools_str}")
        else:
            parts.append("Available tools: none")
    else:
        parts.append("Available tools: none")

    return "\n".join(parts) if parts else ""
