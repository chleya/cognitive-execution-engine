"""State and event log persistence layer.

Provides file-based storage and recovery for State and EventLog
while maintaining determinism and replay semantics.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .state import State, StatePatch, apply_patch, replay
from .event_log import EventLog
from .events import Event, StateTransitionEvent, DeliberationEvent
from .tools import ToolCallEvent, ToolResultEvent
from .approval import ApprovalAuditEvent
from .observations import ObservationEvent


@dataclass(frozen=True)
class PersistenceSnapshot:
    """A serializable snapshot of engine state."""

    state: Dict[str, Any]
    event_count: int
    last_event_type: Optional[str]
    meta: Dict[str, Any]
    version: int = 1

    @classmethod
    def from_state_and_log(cls, state: State, event_log: EventLog) -> "PersistenceSnapshot":
        events = event_log.all()
        last_event = events[-1] if events else None
        return cls(
            state=state.snapshot(),
            event_count=len(events),
            last_event_type=last_event.event_type if last_event else None,
            meta=state.meta,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "state": self.state,
                "event_count": self.event_count,
                "last_event_type": self.last_event_type,
                "meta": self.meta,
            },
            indent=2,
            default=str,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "PersistenceSnapshot":
        data = json.loads(json_str)
        return cls(
            version=data.get("version", 1),
            state=data["state"],
            event_count=data["event_count"],
            last_event_type=data.get("last_event_type"),
            meta=data.get("meta", {}),
        )


@dataclass(frozen=True)
class EventStoreEntry:
    """A single entry in the event store."""

    index: int
    event_type: str
    payload: Dict[str, Any]
    actor: str
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "event_type": self.event_type,
            "payload": self.payload,
            "actor": self.actor,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventStoreEntry":
        return cls(
            index=data["index"],
            event_type=data["event_type"],
            payload=data["payload"],
            actor=data["actor"],
            timestamp=data.get("timestamp"),
        )


class StateStore:
    """File-based state persistence store."""

    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.storage_dir / "state.json"
        self.events_file = self.storage_dir / "events.jsonl"
        self.snapshot_file = self.storage_dir / "snapshot.json"

    def save_state(self, state: State) -> str:
        """Save state to file. Returns file path."""
        state_data = state.snapshot()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, default=str)
        return str(self.state_file)

    def load_state(self) -> State:
        """Load state from file."""
        if not self.state_file.exists():
            return State()
        
        with open(self.state_file, "r", encoding="utf-8") as f:
            state_data = json.load(f)
        
        return State(
            memory=state_data.get("memory", {}),
            goals=state_data.get("goals", {}),
            beliefs=state_data.get("beliefs", {}),
            self_model=state_data.get("self_model", {}),
            policy=state_data.get("policy", {}),
            domain_data=state_data.get("domain_data", {}),
            tool_affordances=state_data.get("tool_affordances", {}),
            meta=state_data.get("meta", {"version": 0}),
        )

    def append_event(self, event: Event | StateTransitionEvent | DeliberationEvent | ToolCallEvent | ToolResultEvent | ApprovalAuditEvent | ObservationEvent) -> int:
        """Append event to event store. Returns event index."""
        import datetime
        index = self._get_event_count()
        entry = EventStoreEntry(
            index=index,
            event_type=event.event_type,
            payload=event.to_dict() if hasattr(event, 'to_dict') else {},
            actor=getattr(event, 'actor', 'unknown'),
            timestamp=datetime.datetime.now().isoformat(),
        )
        
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        
        return index

    def load_events(self) -> list[EventStoreEntry]:
        """Load all events from store."""
        if not self.events_file.exists():
            return []
        
        events = []
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    events.append(EventStoreEntry.from_dict(data))
        
        return events

    def load_state_transitions(self) -> list[StateTransitionEvent]:
        """Load only state transition events for replay."""
        entries = self.load_events()
        transitions = []
        
        for entry in entries:
            if entry.event_type == "state.patch.requested":
                try:
                    event = StateTransitionEvent.from_dict(entry.payload)
                    if event.policy_decision.allowed:
                        transitions.append(event)
                except Exception:
                    pass
        
        return transitions

    def replay_state(self, initial_state: State | None = None) -> State:
        """Replay state from stored events."""
        transitions = self.load_state_transitions()
        if not transitions:
            return self.load_state() if self.state_file.exists() else initial_state or State()
        
        return replay(transitions, initial_state=initial_state)

    def save_snapshot(self, state: State, event_log: EventLog) -> str:
        """Save a complete snapshot of state and event metadata."""
        snapshot = PersistenceSnapshot.from_state_and_log(state, event_log)
        
        with open(self.snapshot_file, "w", encoding="utf-8") as f:
            f.write(snapshot.to_json())
        
        return str(self.snapshot_file)

    def load_snapshot(self) -> PersistenceSnapshot | None:
        """Load snapshot if it exists."""
        if not self.snapshot_file.exists():
            return None
        
        with open(self.snapshot_file, "r", encoding="utf-8") as f:
            return PersistenceSnapshot.from_json(f.read())

    def _get_event_count(self) -> int:
        """Get current event count."""
        if not self.events_file.exists():
            return 0
        
        with open(self.events_file, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def clear(self) -> None:
        """Clear all stored data."""
        for file_path in [self.state_file, self.events_file, self.snapshot_file]:
            if file_path.exists():
                file_path.unlink()

    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about stored data."""
        return {
            "storage_dir": str(self.storage_dir),
            "state_file_exists": self.state_file.exists(),
            "events_file_exists": self.events_file.exists(),
            "snapshot_file_exists": self.snapshot_file.exists(),
            "event_count": self._get_event_count(),
            "state": self.load_state().snapshot() if self.state_file.exists() else None,
        }


def load_state_from_file(path: Path) -> State:
    """Load state from a JSON file.

    This is the canonical way to load state from a file,
    shared by CLI and API layers.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    state = State()
    for section, value in data.items():
        if isinstance(value, dict):
            for key, val in value.items():
                state.__dict__[section][key] = val
    return state
