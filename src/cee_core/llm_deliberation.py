"""LLM-driven deliberation adapter.

Replaces keyword-based deliberation with bounded LLM reasoning while preserving
the audit trail, state semantics, and policy boundaries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from .deliberation import NextAction, ReasoningChain, ReasoningStep, deliberate_next_action
from .event_log import EventLog
from .events import Event
from .llm_provider import LLMProvider, LLMProviderRequest
from .tools import ToolRegistry
from .tasks import TaskSpec


class LLMDeliberationCompiler(Protocol):
    """Protocol for an LLM that produces bounded reasoning steps."""

    def deliberate(self, task: TaskSpec, context: str) -> str:
        """Return a JSON string representing a ReasoningStep payload."""


@dataclass(frozen=True)
class StaticLLMDeliberationCompiler:
    """Deterministic fake deliberation compiler for tests."""

    response_json: str

    def deliberate(self, task: TaskSpec, context: str) -> str:
        return self.response_json


@dataclass(frozen=True)
class ProviderBackedDeliberationCompiler:
    """LLM deliberation backed by a provider-neutral interface."""

    provider: LLMProvider
    event_log: EventLog | None = None

    def deliberate(self, task: TaskSpec, context: str) -> str:
        prompt = build_deliberation_prompt(task, context)
        request = LLMProviderRequest(prompt=prompt)
        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.deliberation.requested",
                    payload={
                        "request_id": request.request_id,
                        "provider_name": self.provider.provider_name,
                        "task_id": task.task_id,
                    },
                    actor="llm_deliberation_compiler",
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
                        event_type="llm.deliberation.failed",
                        payload=payload,
                        actor="llm_deliberation_compiler",
                    )
                )
            raise

        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.deliberation.succeeded",
                    payload={
                        "request_id": response.request_id,
                        "provider_name": response.provider_name,
                        "model_name": response.model_name,
                        "response_length": len(response.response_text),
                    },
                    actor="llm_deliberation_compiler",
                )
            )
        return response.response_text


def build_deliberation_prompt(task: TaskSpec, context: str) -> dict[str, object]:
    """Build a structured prompt for LLM deliberation."""

    return {
        "role": "deliberation",
        "instruction": (
            "Analyze the given task and select exactly ONE next action. "
            "Return ONLY a filled JSON object with these fields: "
            "summary (string), hypothesis (string), missing_information (string), "
            "candidate_actions (array of strings), "
            "chosen_action (one of: propose_plan, request_read_tool, request_approval, propose_redirect, stop), "
            "rationale (string), stop_condition (string). "
            "Do NOT return a schema definition. Return a concrete instance. "
            "Do not execute tools, modify state, or produce plans."
        ),
        "allowed_schema": {
            "chosen_action_values": [
                "propose_plan",
                "request_read_tool",
                "request_approval",
                "propose_redirect",
                "stop",
            ],
            "required_fields": [
                "summary",
                "hypothesis",
                "missing_information",
                "candidate_actions",
                "chosen_action",
                "rationale",
                "stop_condition",
            ],
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


def parse_llm_deliberation_response(
    response_json: str,
    task: TaskSpec,
) -> ReasoningStep:
    """Parse and validate an LLM-produced ReasoningStep payload."""

    cleaned = response_json.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM deliberation compiler returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("LLM deliberation response must be a JSON object")

    allowed_actions = {
        "propose_plan",
        "request_read_tool",
        "request_approval",
        "propose_redirect",
        "stop",
    }

    chosen_action = payload.get("chosen_action")
    if chosen_action not in allowed_actions:
        raise ValueError(
            f"LLM deliberation chosen_action must be one of {allowed_actions}, got: {chosen_action}"
        )

    summary = str(payload.get("summary", ""))
    hypothesis = str(payload.get("hypothesis", ""))
    rationale = str(payload.get("rationale", ""))
    stop_condition = str(payload.get("stop_condition", ""))

    missing_info = payload.get("missing_information", [])
    if not isinstance(missing_info, list):
        missing_info = []
    missing_information = tuple(str(m) for m in missing_info if str(m).strip())

    candidate_actions = payload.get("candidate_actions", [chosen_action])
    if not isinstance(candidate_actions, list):
        candidate_actions = [chosen_action]
    candidate_actions_clean = []
    for ca in candidate_actions:
        if ca in allowed_actions:
            candidate_actions_clean.append(ca)
    if not candidate_actions_clean:
        candidate_actions_clean = [chosen_action]

    return ReasoningStep(
        task_id=task.task_id,
        summary=summary,
        hypothesis=hypothesis,
        missing_information=missing_information,
        candidate_actions=tuple(candidate_actions_clean),
        chosen_action=chosen_action,
        rationale=rationale,
        stop_condition=stop_condition,
    )


def deliberate_with_llm(
    task: TaskSpec,
    compiler: LLMDeliberationCompiler,
    *,
    tool_registry: ToolRegistry | None = None,
    context: str = "",
    fallback_to_deterministic: bool = True,
) -> ReasoningStep:
    """Deliberate using LLM with deterministic fallback."""

    full_context = _build_deliberation_context(task, tool_registry, context)

    try:
        response = compiler.deliberate(task, full_context)
        step = parse_llm_deliberation_response(response, task)
        return step
    except Exception:
        if fallback_to_deterministic:
            return deliberate_next_action(task, tool_registry=tool_registry)
        raise


def deliberate_chain_with_llm(
    task: TaskSpec,
    compiler: LLMDeliberationCompiler,
    *,
    tool_registry: ToolRegistry | None = None,
    context: str = "",
    max_steps: int = 5,
    fallback_to_deterministic: bool = True,
) -> ReasoningChain:
    """Build a multi-step reasoning chain using LLM deliberation."""

    steps: list[ReasoningStep] = []
    full_context = _build_deliberation_context(task, tool_registry, context)

    for step_num in range(max_steps):
        step_context = full_context
        if steps:
            step_context += "\n\nPrevious reasoning steps:\n"
            for i, prev_step in enumerate(steps, 1):
                step_context += (
                    f"Step {i}: chosen_action={prev_step.chosen_action}, "
                    f"rationale={prev_step.rationale}\n"
                )

        try:
            response = compiler.deliberate(task, step_context)
            step = parse_llm_deliberation_response(response, task)
        except Exception:
            if fallback_to_deterministic and not steps:
                return ReasoningChain(
                    steps=(deliberate_next_action(task, tool_registry=tool_registry),)
                )
            break

        steps.append(step)
        if step.is_terminal:
            break

    if steps and not steps[-1].is_terminal and len(steps) == max_steps:
        steps.append(
            ReasoningStep(
                task_id=task.task_id,
                summary=f"Step {max_steps + 1}: maximum chain length reached, forcing plan.",
                hypothesis=steps[-1].hypothesis,
                missing_information=steps[-1].missing_information,
                candidate_actions=("propose_plan",),
                chosen_action="propose_plan",
                rationale="Maximum reasoning chain length reached; forcing plan proposal to avoid infinite deliberation.",
                stop_condition="Terminal: forced plan due to chain length limit.",
            )
        )

    return ReasoningChain(steps=tuple(steps))


def _build_deliberation_context(
    task: TaskSpec,
    tool_registry: ToolRegistry | None,
    context: str,
) -> str:
    """Build the deliberation context string."""

    parts = []

    if context:
        parts.append(context)

    if tool_registry is not None:
        available_tools = tool_registry.list()
        if available_tools:
            tools_str = ", ".join(t.name for t in available_tools)
            parts.append(f"Available tools: {tools_str}")
        else:
            parts.append("Available tools: none")
    else:
        parts.append("Available tools: none")

    return "\n".join(parts) if parts else ""
