"""JSON artifact helpers for serialized event payloads."""

from __future__ import annotations

import json
from typing import Iterable

from .event_log import EventRecord, replay_serialized_transition_events
from .state import State


def events_to_payloads(events: Iterable[EventRecord]) -> list[dict[str, object]]:
    """Convert event records into serializable payload dictionaries."""

    payloads: list[dict[str, object]] = []
    for event in events:
        payloads.append(event.to_dict())
    return payloads


def dumps_event_payloads(events: Iterable[EventRecord]) -> str:
    """Dump event records into a deterministic JSON artifact string."""

    return json.dumps(
        events_to_payloads(events),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def loads_event_payloads(artifact: str) -> list[dict[str, object]]:
    """Load event payload dictionaries from a JSON artifact string."""

    payloads = json.loads(artifact)
    if not isinstance(payloads, list):
        raise ValueError("Event artifact must be a JSON array")

    for payload in payloads:
        if not isinstance(payload, dict):
            raise ValueError("Event artifact entries must be JSON objects")

    return payloads


def replay_event_payload_artifact(
    artifact: str,
    initial_state: State | None = None,
) -> State:
    """Replay allowed transitions from a JSON event payload artifact."""

    return replay_serialized_transition_events(
        loads_event_payloads(artifact),
        initial_state=initial_state,
    )

