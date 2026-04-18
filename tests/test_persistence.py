"""Tests for state and event log persistence."""

import json
import os
import tempfile

import pytest

from cee_core.persistence import StateStore, PersistenceSnapshot, EventStoreEntry
from cee_core.state import State, StatePatch, apply_patch, replay
from cee_core.event_log import EventLog
from cee_core.events import Event, StateTransitionEvent
from cee_core.policy import PolicyDecision


class TestEventStoreEntry:
    def test_entry_creation(self):
        entry = EventStoreEntry(
            index=0,
            event_type="test.event",
            payload={"key": "value"},
            actor="test_actor",
        )

        assert entry.index == 0
        assert entry.event_type == "test.event"
        assert entry.actor == "test_actor"

    def test_entry_to_dict(self):
        entry = EventStoreEntry(
            index=1,
            event_type="state.patch.requested",
            payload={"section": "goals"},
            actor="planner",
            timestamp="2026-04-17T00:00:00",
        )

        d = entry.to_dict()

        assert d["index"] == 1
        assert d["event_type"] == "state.patch.requested"
        assert d["payload"] == {"section": "goals"}

    def test_entry_from_dict(self):
        data = {
            "index": 2,
            "event_type": "tool.call.result",
            "payload": {"tool_name": "test"},
            "actor": "executor",
            "timestamp": "2026-04-17T01:00:00",
        }

        entry = EventStoreEntry.from_dict(data)

        assert entry.index == 2
        assert entry.event_type == "tool.call.result"


class TestPersistenceSnapshot:
    def test_snapshot_creation(self):
        state = State()
        state.goals["active"] = ["task_1"]
        state.meta["version"] = 1

        log = EventLog()

        snapshot = PersistenceSnapshot.from_state_and_log(state, log)

        assert snapshot.event_count == 0
        assert snapshot.state["goals"]["active"] == ["task_1"]
        assert snapshot.meta["version"] == 1

    def test_snapshot_json_roundtrip(self):
        snapshot = PersistenceSnapshot(
            state={"goals": {"active": ["task_1"]}},
            event_count=5,
            last_event_type="state.patch.requested",
            meta={"version": 3},
        )

        json_str = snapshot.to_json()
        restored = PersistenceSnapshot.from_json(json_str)

        assert restored.event_count == 5
        assert restored.last_event_type == "state.patch.requested"
        assert restored.meta["version"] == 3


class TestStateStore:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = StateStore(self.temp_dir)

    def teardown_method(self):
        self.store.clear()

    def test_save_and_load_state(self):
        state = State()
        state.goals["active"] = ["task_1"]
        state.beliefs["test"] = "data"
        state.meta["version"] = 5

        self.store.save_state(state)
        restored = self.store.load_state()

        assert restored.goals["active"] == ["task_1"]
        assert restored.beliefs["test"] == "data"
        assert restored.meta["version"] == 5

    def test_load_state_from_empty_store(self):
        restored = self.store.load_state()

        assert isinstance(restored, State)
        assert restored.meta["version"] == 0

    def test_append_and_load_events(self):
        event = Event(
            event_type="task.received",
            payload={"task_id": "task_1"},
            actor="compiler",
        )

        index = self.store.append_event(event)

        assert index == 0

        events = self.store.load_events()
        assert len(events) == 1
        assert events[0].event_type == "task.received"

    def test_multiple_events_maintain_order(self):
        for i in range(5):
            event = Event(
                event_type=f"event_{i}",
                payload={"index": i},
                actor="test",
            )
            self.store.append_event(event)

        events = self.store.load_events()
        assert len(events) == 5
        assert events[0].index == 0
        assert events[4].index == 4

    def test_replay_state_from_events(self):
        patch = StatePatch(
            section="goals",
            key="active",
            op="set",
            value=["task_1"],
        )
        event = StateTransitionEvent(
            patch=patch,
            policy_decision=PolicyDecision(
                verdict="allow",
                reason="test allow",
                policy_ref="test_policy",
            ),
            actor="test",
        )

        self.store.append_event(event)
        replayed = self.store.replay_state()

        assert replayed.goals.get("active") == ["task_1"]

    def test_save_and_load_snapshot(self):
        state = State()
        state.goals["active"] = ["task_1"]

        log = EventLog()
        log.append(
            Event(
                event_type="task.received",
                payload={"task_id": "task_1"},
                actor="compiler",
            )
        )

        self.store.save_snapshot(state, log)
        snapshot = self.store.load_snapshot()

        assert snapshot is not None
        assert snapshot.event_count == 1
        assert snapshot.state["goals"]["active"] == ["task_1"]

    def test_clear_storage(self):
        state = State()
        self.store.save_state(state)
        self.store.append_event(
            Event(
                event_type="test",
                payload={},
                actor="test",
            )
        )

        self.store.clear()

        assert not self.store.state_file.exists()
        assert not self.store.events_file.exists()
        assert not self.store.snapshot_file.exists()

    def test_get_storage_info(self):
        state = State()
        state.goals["active"] = ["task_1"]
        self.store.save_state(state)

        info = self.store.get_storage_info()

        assert info["state_file_exists"] is True
        assert info["event_count"] == 0
        assert info["state"]["goals"]["active"] == ["task_1"]

    def test_state_file_persistence_across_instances(self):
        """Test that state persists across store instances."""
        state = State()
        state.beliefs["key"] = "value"
        state.meta["version"] = 10

        self.store.save_state(state)

        new_store = StateStore(self.temp_dir)
        restored = new_store.load_state()

        assert restored.beliefs["key"] == "value"
        assert restored.meta["version"] == 10

    def test_event_store_persistence_across_instances(self):
        """Test that events persist across store instances."""
        for i in range(3):
            event = Event(
                event_type=f"event_{i}",
                payload={"index": i},
                actor="test",
            )
            self.store.append_event(event)

        new_store = StateStore(self.temp_dir)
        events = new_store.load_events()

        assert len(events) == 3
        assert events[0].index == 0
        assert events[2].index == 2

    def test_replay_with_no_state_file(self):
        """Test replay when no state file exists."""
        replayed = self.store.replay_state()

        assert isinstance(replayed, State)
        assert replayed.meta["version"] == 0

    def test_snapshot_load_returns_none_when_missing(self):
        """Test that load_snapshot returns None when no snapshot exists."""
        snapshot = self.store.load_snapshot()

        assert snapshot is None
