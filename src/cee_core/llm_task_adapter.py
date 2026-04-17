"""LLM task compiler adapter boundary.

Stage 1 introduces the adapter contract without calling a real model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from .event_log import EventLog
from .events import Event
from .llm_provider import LLMProvider, LLMProviderRequest
from .primitives import default_primitives_for_task_kind, validate_primitives
from .tasks import TaskSpec


class LLMTaskCompiler(Protocol):
    """Protocol for a constrained model-side task compiler."""

    def compile(self, raw_input: str) -> str:
        """Return a JSON string representing a TaskSpec-like payload."""


@dataclass(frozen=True)
class StaticLLMTaskCompiler:
    """Deterministic fake compiler used to test the adapter boundary."""

    response_json: str

    def compile(self, raw_input: str) -> str:
        return self.response_json


@dataclass(frozen=True)
class ProviderBackedTaskCompiler:
    """Task compiler backed by a provider-neutral LLM interface."""

    provider: LLMProvider
    event_log: EventLog | None = None

    def bind_event_log(self, event_log: EventLog) -> "ProviderBackedTaskCompiler":
        """Return a compiler instance bound to the supplied event log."""

        return ProviderBackedTaskCompiler(provider=self.provider, event_log=event_log)

    def compile(self, raw_input: str) -> str:
        prompt = build_task_compiler_prompt(raw_input)
        request = LLMProviderRequest(prompt=prompt)
        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.provider.requested",
                    payload={
                        "request_id": request.request_id,
                        "provider_name": self.provider.provider_name,
                        "timeout_seconds": request.timeout_seconds,
                        "prompt_role": prompt["role"],
                    },
                    actor="provider_backed_task_compiler",
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
                    "error_type": type(exc).__name__,
                }
                if hasattr(error, "kind"):
                    payload["kind"] = error.kind
                if hasattr(error, "message"):
                    payload["message"] = error.message
                self.event_log.append(
                    Event(
                        event_type="llm.provider.failed",
                        payload=payload,
                        actor="provider_backed_task_compiler",
                    )
                )
            raise

        if self.event_log is not None:
            self.event_log.append(
                Event(
                    event_type="llm.provider.succeeded",
                    payload={
                        "request_id": response.request_id,
                        "provider_name": response.provider_name,
                        "model_name": response.model_name,
                        "response_length": len(response.response_text),
                    },
                    actor="provider_backed_task_compiler",
                )
            )
        return response.response_text


def build_task_compiler_prompt(raw_input: str) -> dict[str, object]:
    """Build a structured prompt envelope for an LLM task compiler."""

    return {
        "role": "task_compiler",
        "instruction": (
            "Compile raw user input into a TaskSpec JSON object only. "
            "Do not produce a plan. Do not produce state patches. "
            "Do not request tools. Do not execute anything."
        ),
        "allowed_schema": {
            "required": [
                "objective",
                "kind",
                "risk_level",
                "success_criteria",
            ],
            "optional": ["requested_primitives", "task_level"],
            "kind_values": ["analysis", "state_update"],
            "risk_level_values": ["low", "medium", "high"],
            "task_level_values": ["L0", "L1", "L2", "L3", "L4"],
            "requested_primitives_values": [
                "observe",
                "interpret",
                "hypothesize",
                "plan",
                "act",
                "verify",
                "reflect",
                "escalate",
            ],
        },
        "raw_input": raw_input,
    }


def parse_llm_task_response(response_json: str, *, raw_input: str) -> TaskSpec:
    """Parse and validate an LLM-produced TaskSpec payload."""

    try:
        payload = json.loads(response_json)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM task compiler returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("LLM task compiler response must be a JSON object")

    _reject_forbidden_llm_task_fields(payload)
    _reject_unexpected_llm_task_fields(payload)

    objective = payload.get("objective")
    kind = payload.get("kind")
    risk_level = payload.get("risk_level")
    task_level = payload.get("task_level")
    success_criteria = payload.get("success_criteria")
    requested_primitives = payload.get("requested_primitives")

    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("LLM task compiler response requires non-empty objective")

    if kind not in {"analysis", "state_update"}:
        raise ValueError("LLM task compiler response has invalid kind")

    if risk_level not in {"low", "medium", "high"}:
        raise ValueError("LLM task compiler response has invalid risk_level")

    if task_level is not None and task_level not in {"L0", "L1", "L2", "L3", "L4"}:
        raise ValueError("LLM task compiler response has invalid task_level")

    if not isinstance(success_criteria, list) or not all(
        isinstance(item, str) and item.strip() for item in success_criteria
    ):
        raise ValueError("LLM task compiler response requires string success_criteria")

    if requested_primitives is None:
        primitive_sequence = default_primitives_for_task_kind(kind)
    else:
        if not isinstance(requested_primitives, list) or not all(
            isinstance(item, str) and item.strip() for item in requested_primitives
        ):
            raise ValueError(
                "LLM task compiler response requires string requested_primitives"
            )
        primitive_sequence = validate_primitives(tuple(requested_primitives))

    return TaskSpec(
        domain_name="core",
        objective=" ".join(objective.strip().split()),
        kind=kind,
        risk_level=risk_level,
        task_level=task_level or "L1",
        success_criteria=tuple(item.strip() for item in success_criteria),
        requested_primitives=primitive_sequence,
        raw_input=raw_input,
    )


def compile_task_with_llm_adapter(
    raw_input: str,
    compiler: LLMTaskCompiler,
    *,
    domain_name: str = "core",
) -> TaskSpec:
    """Compile raw input through a constrained LLM adapter."""

    if not raw_input.strip():
        raise ValueError("raw_input cannot be empty")
    response = compiler.compile(raw_input)
    task = parse_llm_task_response(response, raw_input=raw_input)
    return TaskSpec(
        task_id=task.task_id,
        domain_name=domain_name,
        objective=task.objective,
        kind=task.kind,
        risk_level=task.risk_level,
        task_level=task.task_level,
        success_criteria=task.success_criteria,
        requested_primitives=task.requested_primitives,
        raw_input=task.raw_input,
    )


def _reject_forbidden_llm_task_fields(payload: dict[str, object]) -> None:
    forbidden = {
        "patch",
        "patches",
        "state_patch",
        "state_patches",
        "plan",
        "candidate_patches",
        "tool",
        "tools",
        "tool_calls",
        "execute",
    }
    present = sorted(forbidden.intersection(payload))
    if present:
        raise ValueError(
            "LLM task compiler response contains forbidden execution fields: "
            + ", ".join(present)
        )


def _reject_unexpected_llm_task_fields(payload: dict[str, object]) -> None:
    allowed = {
        "objective",
        "kind",
        "risk_level",
        "task_level",
        "success_criteria",
        "requested_primitives",
    }
    present = sorted(set(payload).difference(allowed))
    if present:
        raise ValueError(
            "LLM task compiler response contains unexpected fields: "
            + ", ".join(present)
        )
