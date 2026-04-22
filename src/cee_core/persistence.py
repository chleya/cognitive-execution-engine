"""State and event log persistence layer.

Provides file-based storage and recovery for WorldState and EventLog
while maintaining determinism and replay semantics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_SAFE_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

from .event_log import EventLog
from .events import Event, DeliberationEvent
from .tools import ToolCallEvent, ToolResultEvent
from .approval import ApprovalAuditEvent
from .observations import ObservationEvent
from .world_state import WorldState
from .commitment import CommitmentEvent
from .revision import ModelRevisionEvent


@dataclass(frozen=True)
class PersistenceSnapshot:
    """A serializable snapshot of engine state."""

    state: Dict[str, Any]
    event_count: int
    last_event_type: Optional[str]
    meta: Dict[str, Any]
    version: int = 1

    @classmethod
    def from_world_state_and_log(cls, ws: WorldState, event_log: EventLog) -> "PersistenceSnapshot":
        events = event_log.all()
        last_event = events[-1] if events else None
        return cls(
            state=ws.to_dict(),
            event_count=len(events),
            last_event_type=last_event.event_type if last_event else None,
            meta={"state_id": ws.state_id, "version": len(ws.provenance_refs)},
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
        self.world_state_file = self.storage_dir / "world_state.json"
        self.commitment_events_file = self.storage_dir / "commitment_events.jsonl"
        self.revision_events_file = self.storage_dir / "revision_events.jsonl"

    def append_event(self, event: Event | DeliberationEvent | ToolCallEvent | ToolResultEvent | ApprovalAuditEvent | ObservationEvent | CommitmentEvent | ModelRevisionEvent) -> int:
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

    def load_commitment_and_revision_events(self) -> tuple[list[CommitmentEvent], list[ModelRevisionEvent]]:
        """Load commitment and revision events for replay."""
        commitments = load_commitment_events(self)
        revisions = load_revision_events(self)
        return commitments, revisions

    def save_events(self, events: list) -> None:
        """Append events to the event log file."""
        from .events import Event
        from .commitment import CommitmentEvent as CE
        from .revision import ModelRevisionEvent as MRE

        existing = self.load_events()
        next_index = len(existing)

        with open(self.events_file, "a", encoding="utf-8") as f:
            for event in events:
                if isinstance(event, (CE, MRE)):
                    entry = EventStoreEntry(
                        index=next_index,
                        event_type=getattr(event, "event_type", type(event).__name__),
                        payload=event.to_dict(),
                        actor=getattr(event, "actor", "import"),
                    )
                elif isinstance(event, Event):
                    entry = EventStoreEntry(
                        index=next_index,
                        event_type=event.event_type,
                        payload=event.payload,
                        actor=getattr(event, "actor", "import"),
                    )
                elif isinstance(event, dict):
                    entry = EventStoreEntry(
                        index=next_index,
                        event_type=event.get("event_type", "unknown"),
                        payload=event.get("payload", {}),
                        actor=event.get("actor", "import"),
                    )
                else:
                    entry = EventStoreEntry(
                        index=next_index,
                        event_type=type(event).__name__,
                        payload={"data": str(event)},
                        actor="import",
                    )
                next_index += 1
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")

    def save_world_state(self, ws: WorldState) -> str:
        """Save WorldState to file. Returns file path."""
        with open(self.world_state_file, "w", encoding="utf-8") as f:
            json.dump(ws.to_dict(), f, indent=2, default=str)
        return str(self.world_state_file)

    def load_world_state(self) -> WorldState:
        """Load WorldState from file."""
        if not self.world_state_file.exists():
            return WorldState(state_id="ws_0")

        with open(self.world_state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return WorldState.from_dict(data)

    def save_world_snapshot(self, ws: WorldState, event_log: EventLog) -> str:
        """Save a complete snapshot of WorldState and event metadata."""
        snapshot = PersistenceSnapshot.from_world_state_and_log(ws, event_log)

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
        for file_path in [self.state_file, self.events_file, self.snapshot_file,
                          self.world_state_file, self.commitment_events_file,
                          self.revision_events_file]:
            if file_path.exists():
                file_path.unlink()

    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about stored data."""
        return {
            "storage_dir": str(self.storage_dir),
            "state_file_exists": self.state_file.exists(),
            "events_file_exists": self.events_file.exists(),
            "snapshot_file_exists": self.snapshot_file.exists(),
            "world_state_file_exists": self.world_state_file.exists(),
            "event_count": self._get_event_count(),
            "world_state": self.load_world_state().to_dict() if self.world_state_file.exists() else None,
        }

    def save_run_artifact(self, run_id: str, artifact_data: Dict[str, Any]) -> str:
        """Save a RunArtifact keyed by run_id. Returns file path."""
        self._validate_run_id(run_id)
        runs_dir = self.storage_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = runs_dir / f"{run_id}.json"
        resolved = artifact_file.resolve()
        if not str(resolved).startswith(str(runs_dir.resolve())):
            raise ValueError(f"run_id resolves outside runs directory: {run_id}")
        with open(artifact_file, "w", encoding="utf-8") as f:
            json.dump(artifact_data, f, indent=2, default=str)
        return str(artifact_file)

    def load_run_artifact(self, run_id: str) -> Dict[str, Any] | None:
        """Load a RunArtifact by run_id. Returns None if not found."""
        self._validate_run_id(run_id)
        artifact_file = self.storage_dir / "runs" / f"{run_id}.json"
        resolved = artifact_file.resolve()
        runs_dir = (self.storage_dir / "runs").resolve()
        if not str(resolved).startswith(str(runs_dir)):
            raise ValueError(f"run_id resolves outside runs directory: {run_id}")
        if not artifact_file.exists():
            return None
        with open(artifact_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_run_ids(self) -> list[str]:
        """List all stored run IDs."""
        runs_dir = self.storage_dir / "runs"
        if not runs_dir.exists():
            return []
        return [f.stem for f in runs_dir.glob("*.json")]

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not _SAFE_RUN_ID_PATTERN.match(run_id):
            raise ValueError(
                f"Invalid run_id: {run_id!r}. "
                "Must match ^[A-Za-z0-9_-]{1,64}$"
            )


def load_world_state_from_file(path: Path) -> WorldState:
    """Load WorldState from a JSON file."""
    p = Path(path)
    if not p.exists():
        return WorldState(state_id="ws_0")
    data = json.loads(p.read_text(encoding="utf-8"))
    return WorldState.from_dict(data)


def save_world_state(store: StateStore, ws: WorldState) -> str:
    """Save WorldState to file. Returns file path."""
    with open(store.world_state_file, "w", encoding="utf-8") as f:
        json.dump(ws.to_dict(), f, indent=2, default=str)
    return str(store.world_state_file)


def load_world_state(store: StateStore) -> WorldState:
    """Load WorldState from file."""
    if not store.world_state_file.exists():
        return WorldState(state_id="ws_0")

    with open(store.world_state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return WorldState.from_dict(data)


def append_commitment_event(store: StateStore, event: CommitmentEvent) -> int:
    """Append commitment event to store. Returns event index."""
    import datetime
    index = _count_lines(store.commitment_events_file)
    entry = {
        "index": index,
        "event_id": event.event_id,
        "commitment_kind": event.commitment_kind,
        "payload": event.to_dict(),
        "timestamp": datetime.datetime.now().isoformat(),
    }

    with open(store.commitment_events_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return index


def append_revision_event(store: StateStore, event: ModelRevisionEvent) -> int:
    """Append revision event to store. Returns event index."""
    import datetime
    index = _count_lines(store.revision_events_file)
    entry = {
        "index": index,
        "revision_id": event.revision_id,
        "revision_kind": event.revision_kind,
        "payload": event.to_dict(),
        "timestamp": datetime.datetime.now().isoformat(),
    }

    with open(store.revision_events_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    return index


def load_commitment_events(store: StateStore) -> list[CommitmentEvent]:
    """Load all commitment events from store."""
    if not store.commitment_events_file.exists():
        return []

    events = []
    with open(store.commitment_events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                events.append(CommitmentEvent.from_dict(data["payload"]))

    return events


def load_revision_events(store: StateStore) -> list[ModelRevisionEvent]:
    """Load all revision events from store."""
    if not store.revision_events_file.exists():
        return []

    events = []
    with open(store.revision_events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                events.append(ModelRevisionEvent.from_dict(data["payload"]))

    return events


def _count_lines(file_path: Path) -> int:
    if not file_path.exists():
        return 0
    with open(file_path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())
