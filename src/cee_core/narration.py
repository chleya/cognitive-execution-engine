"""Deterministic user-facing narration derived from audit events."""

from __future__ import annotations

from typing import Iterable

from .event_log import EventRecord


def render_event_narration(events: Iterable[EventRecord]) -> tuple[str, ...]:
    """Render a compact progress narration from the audit stream."""

    lines: list[str] = []
    for event in events:
        event_type = getattr(event, "event_type", "")
        line = _render_event_line(event_type, event)
        if line is not None:
            lines.append(line)
    return tuple(lines)


def _render_event_line(event_type: str, event: EventRecord) -> str | None:
    if event_type == "task.received":
        objective = event.payload.get("objective", "task")
        return f"Received task: {objective}"

    if event_type == "task.compiler.requested":
        return "Requested constrained task compilation."

    if event_type == "task.compiler.succeeded":
        objective = event.payload.get("objective", "compiled task")
        return f"Compiled structured task: {objective}"

    if event_type == "task.compiler.rejected":
        return "Rejected compiler output."

    if event_type == "reasoning.step.selected":
        chosen_action = event.reasoning_step.chosen_action
        return f"Selected next action: {chosen_action}"

    if event_type == "tool.call.proposed":
        verdict = event.decision.verdict
        return f"Proposed tool call: {event.call.tool_name} ({verdict})"

    if event_type == "tool.call.result":
        if event.status == "succeeded":
            return f"Completed tool call: {event.tool_name}"
        return f"Tool call failed: {event.tool_name}"

    if event_type == "observation.candidate.recorded":
        return f"Recorded observation from tool: {event.observation.source_tool}"

    if event_type == "commitment":
        kind = event.commitment_kind
        summary = event.intent_summary
        return f"Committed {kind}: {summary}"

    if event_type == "revision":
        kind = event.revision_kind
        summary = event.revision_summary or f"{len(event.deltas)} delta(s)"
        return f"Revised model ({kind}): {summary}"

    if event_type == "state.patch.requested":
        verdict = event.policy_decision.verdict
        return f"Evaluated state patch: {event.patch.section}.{event.patch.key} ({verdict})"

    return None
