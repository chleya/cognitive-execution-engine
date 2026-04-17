"""Append-only in-memory event log for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .approval import ApprovalAuditEvent
from .events import DeliberationEvent, Event, StateTransitionEvent
from .observations import ObservationEvent
from .state import State, replay
from .tools import ToolCallEvent, ToolResultEvent


EventRecord = (
    Event
    | StateTransitionEvent
    | DeliberationEvent
    | ApprovalAuditEvent
    | ToolCallEvent
    | ToolResultEvent
    | ObservationEvent
)


_VALID_EVENT_TYPES = (Event, StateTransitionEvent, DeliberationEvent,
                      ApprovalAuditEvent, ToolCallEvent, ToolResultEvent,
                      ObservationEvent)


@dataclass
class EventLog:
    """Minimal append-only event log.

    This is intentionally in-memory. Persistence is a later boundary after
    replay and event typing are stable.
    """

    _events: list[EventRecord] = field(default_factory=list)

    def append(self, event: EventRecord) -> None:
        if not isinstance(event, _VALID_EVENT_TYPES):
            raise TypeError(
                f"Expected EventRecord, got {type(event).__name__}"
            )
        self._events.append(event)

    def all(self) -> tuple[EventRecord, ...]:
        return tuple(self._events)

    def by_trace(self, trace_id: str) -> tuple[EventRecord, ...]:
        return tuple(event for event in self._events if event.trace_id == trace_id)

    def transition_events(self) -> tuple[StateTransitionEvent, ...]:
        return tuple(
            event
            for event in self._events
            if isinstance(event, StateTransitionEvent)
            and event.policy_decision.allowed
        )

    def replay_state(self, initial_state: State | None = None) -> State:
        return replay(self.transition_events(), initial_state=initial_state)


def replay_transition_events(
    events: Iterable[EventRecord],
    initial_state: State | None = None,
) -> State:
    """Replay only allowed state-transition events from a mixed event stream."""

    transitions = tuple(
        event
        for event in events
        if isinstance(event, StateTransitionEvent)
        and event.policy_decision.allowed
    )
    return replay(transitions, initial_state=initial_state)


def replay_serialized_transition_events(
    payloads: Iterable[dict[str, object]],
    initial_state: State | None = None,
) -> State:
    """Replay allowed state-transition events from serialized payloads."""

    events = []
    for payload in payloads:
        if payload.get("event_type") != "state.patch.requested":
            continue
        event = StateTransitionEvent.from_dict(payload)  # type: ignore[arg-type]
        if event.policy_decision.allowed:
            events.append(event)

    return replay(events, initial_state=initial_state)
