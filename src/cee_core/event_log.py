"""Append-only in-memory event log for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .approval import ApprovalAuditEvent
from .commitment import CommitmentEvent
from .events import DeliberationEvent, Event
from .observations import ObservationEvent
from .revision import ModelRevisionEvent
from .tools import ToolCallEvent, ToolResultEvent
from .world_state import WorldState


EventRecord = (
    Event
    | DeliberationEvent
    | ApprovalAuditEvent
    | ToolCallEvent
    | ToolResultEvent
    | ObservationEvent
    | CommitmentEvent
    | ModelRevisionEvent
)


_VALID_EVENT_TYPES = (Event, DeliberationEvent,
                      ApprovalAuditEvent, ToolCallEvent, ToolResultEvent,
                      ObservationEvent, CommitmentEvent, ModelRevisionEvent)


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

    def commitment_events(self) -> tuple[CommitmentEvent, ...]:
        return tuple(
            event
            for event in self._events
            if isinstance(event, CommitmentEvent)
        )

    def revision_events(self) -> tuple[ModelRevisionEvent, ...]:
        return tuple(
            event
            for event in self._events
            if isinstance(event, ModelRevisionEvent)
        )

    def replay_world_state(self, initial: WorldState | None = None) -> WorldState:
        """Replay WorldState from commitment and revision events in this log."""
        return replay_world_state(
            self.commitment_events(),
            self.revision_events(),
            initial=initial,
        )


def replay_world_state(
    commitment_events: Iterable[CommitmentEvent],
    revision_events: Iterable[ModelRevisionEvent],
    initial: WorldState | None = None,
) -> WorldState:
    """Replay a WorldState from commitment and revision events.

    Applies revision events in order to an initial WorldState,
    deriving state transitions from the revision deltas.
    Commitment events are used to track provenance but do not
    directly mutate WorldState — only revision events do.
    """
    ws = initial or WorldState(state_id="ws_0")

    for rev in revision_events:
        ws = _apply_revision_to_world_state(ws, rev)

    return ws


def _apply_revision_to_world_state(
    ws: WorldState,
    rev: ModelRevisionEvent,
) -> WorldState:
    """Apply a single ModelRevisionEvent to a WorldState."""
    import json
    from .world_state import add_anchor_facts, update_hypothesis_status, update_dominant_goals, update_self_model

    new_anchors = []
    for delta in rev.deltas:
        if delta.target_kind in ("hypothesis", "anchored_fact"):
            if delta.after_summary and delta.after_summary not in ws.anchored_fact_summaries:
                new_anchors.append(delta.after_summary)

        if delta.target_kind == "goal_update" and delta.raw_value is not None:
            goals = delta.raw_value
            if isinstance(goals, (list, tuple)):
                ws = update_dominant_goals(ws, tuple(str(g) for g in goals))

        if delta.target_kind == "self_update" and delta.raw_value is not None:
            target_ref = delta.target_ref
            if target_ref == "self_model.capabilities" and isinstance(delta.raw_value, (list, tuple)):
                ws = update_self_model(ws, capability_summary=tuple(str(c) for c in delta.raw_value))
            elif target_ref == "self_model.limits" and isinstance(delta.raw_value, (list, tuple)):
                ws = update_self_model(ws, limit_summary=tuple(str(l) for l in delta.raw_value))
            elif target_ref == "self_model.reliability" and isinstance(delta.raw_value, (int, float)):
                ws = update_self_model(ws, reliability_estimate=float(delta.raw_value))

        if delta.target_kind == "entity_update" and delta.raw_value is not None:
            target_ref = delta.target_ref
            if target_ref.startswith("beliefs."):
                key = target_ref[len("beliefs."):]
                from .world_schema import WorldEntity
                from .world_state import add_entity, update_entity
                existing = ws.find_entity(f"belief-{key}")
                if isinstance(delta.raw_value, str):
                    summary = f"{key} = {delta.raw_value}"
                    kind = "belief_item"
                else:
                    summary = json.dumps(delta.raw_value, default=str)
                    kind = "belief_group"
                if existing:
                    ws = update_entity(ws, f"belief-{key}", summary=summary)
                else:
                    ws = add_entity(ws, WorldEntity(
                        entity_id=f"belief-{key}",
                        kind=kind,
                        summary=summary,
                    ))
            elif target_ref.startswith("domain_data."):
                key = target_ref[len("domain_data."):]
                from .world_schema import WorldEntity
                from .world_state import add_entity, update_entity
                existing = ws.find_entity(f"domain-{key}")
                summary = json.dumps(delta.raw_value, default=str)
                if existing:
                    ws = update_entity(ws, f"domain-{key}", summary=summary)
                else:
                    ws = add_entity(ws, WorldEntity(
                        entity_id=f"domain-{key}",
                        kind="domain_data",
                        summary=summary,
                    ))
            elif target_ref.startswith("memory."):
                key = target_ref[len("memory."):]
                from .world_schema import WorldEntity
                from .world_state import add_entity, update_entity
                existing = ws.find_entity(f"memory-{key}")
                if existing:
                    try:
                        current = json.loads(existing.summary)
                    except (json.JSONDecodeError, ValueError):
                        current = []
                    if isinstance(current, list):
                        current.append(delta.raw_value)
                    else:
                        current = delta.raw_value
                    ws = update_entity(ws, f"memory-{key}", summary=json.dumps(current, default=str))
                else:
                    if isinstance(delta.raw_value, list):
                        value = delta.raw_value
                    else:
                        value = [delta.raw_value]
                    ws = add_entity(ws, WorldEntity(
                        entity_id=f"memory-{key}",
                        kind="memory_entry",
                        summary=json.dumps(value, default=str),
                    ))

    if new_anchors:
        ws = add_anchor_facts(ws, tuple(new_anchors))

    ws = WorldState(
        state_id=rev.resulting_state_id,
        entities=ws.entities,
        relations=ws.relations,
        hypotheses=ws.hypotheses,
        anchored_fact_summaries=ws.anchored_fact_summaries,
        dominant_goals=ws.dominant_goals,
        self_capability_summary=ws.self_capability_summary,
        self_limit_summary=ws.self_limit_summary,
        self_reliability_estimate=ws.self_reliability_estimate,
        active_tensions=ws.active_tensions,
        provenance_refs=ws.provenance_refs + (rev.revision_id,),
        parent_state_id=ws.state_id,
    )

    return ws
