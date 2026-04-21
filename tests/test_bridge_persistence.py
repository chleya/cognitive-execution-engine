"""Tests for WorldState persistence."""

import json
import tempfile
import pytest
from pathlib import Path

from cee_core.world_state import WorldState, add_entity, add_hypothesis_to_world, add_anchor_facts
from cee_core.world_schema import WorldEntity, WorldHypothesis, WorldRelation, RevisionDelta
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent
from cee_core.persistence import (
    StateStore,
    save_world_state,
    load_world_state,
    append_commitment_event,
    append_revision_event,
    load_commitment_events,
    load_revision_events,
)


class TestWorldStatePersistence:
    def test_save_and_load(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        ws = WorldState(
            state_id="ws_5",
            entities=(WorldEntity(entity_id="e1", kind="project", summary="Alpha"),),
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="X=5"),),
            anchored_fact_summaries=("alpha=delayed",),
            dominant_goals=("ship alpha",),
        )
        save_world_state(store, ws)
        loaded = load_world_state(store)
        assert loaded.state_id == "ws_5"
        assert len(loaded.entities) == 1
        assert loaded.entities[0].entity_id == "e1"
        assert len(loaded.hypotheses) == 1
        assert loaded.anchored_fact_summaries == ("alpha=delayed",)
        assert loaded.dominant_goals == ("ship alpha",)

    def test_load_missing_returns_default(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        ws = load_world_state(store)
        assert ws.state_id == "ws_0"
        assert ws.entities == ()

    def test_full_persistence_roundtrip(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))

        ws = WorldState(state_id="ws_0")
        ws = add_entity(ws, WorldEntity(entity_id="e1", kind="project", summary="Alpha"))
        ws = add_hypothesis_to_world(ws, WorldHypothesis(hypothesis_id="h1", statement="status=ok"))
        ws = add_anchor_facts(ws, ("alpha_status=delayed",))

        save_world_state(store, ws)
        loaded = load_world_state(store)

        assert loaded.state_id == ws.state_id
        assert len(loaded.entities) == 1
        assert len(loaded.hypotheses) == 1
        assert loaded.anchored_fact_summaries == ("alpha_status=delayed",)


class TestCommitmentEventPersistence:
    def test_save_and_load(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Check status",
        )
        append_commitment_event(store, ce)
        events = load_commitment_events(store)
        assert len(events) == 1
        assert events[0].event_id == "ce1"
        assert events[0].commitment_kind == "observe"

    def test_multiple_events(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        for i in range(3):
            ce = CommitmentEvent(
                event_id=f"ce{i}",
                source_state_id="ws_0",
                commitment_kind="observe",
                intent_summary=f"Check {i}",
            )
            append_commitment_event(store, ce)
        events = load_commitment_events(store)
        assert len(events) == 3


class TestRevisionEventPersistence:
    def test_save_and_load(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        rev = ModelRevisionEvent(
            revision_id="rev1",
            prior_state_id="ws_0",
            caused_by_event_id="ce1",
            revision_kind="correction",
            deltas=(RevisionDelta(
                delta_id="d1",
                target_kind="hypothesis_update",
                target_ref="h1",
                before_summary="tentative",
                after_summary="rejected",
                justification="contradicted",
            ),),
        )
        append_revision_event(store, rev)
        events = load_revision_events(store)
        assert len(events) == 1
        assert events[0].revision_id == "rev1"
        assert events[0].revision_kind == "correction"
        assert len(events[0].deltas) == 1
