"""Tests for world_schema, world_state, commitment, and revision modules."""

import pytest

from cee_core.world_schema import (
    Confidence,
    RevisionDelta,
    RevisionTargetKind,
    WorldEntity,
    WorldHypothesis,
    WorldRelation,
    WORLD_SCHEMA_VERSION,
)
from cee_core.world_state import (
    WorldState,
    add_anchor_facts,
    add_entity,
    add_hypothesis_to_world,
    add_relation,
    add_tension,
    remove_entity,
    resolve_tension,
    update_entity,
    update_hypothesis_status,
    update_self_model,
    WORLD_STATE_SCHEMA_VERSION,
)
from cee_core.commitment import (
    CommitmentEvent,
    CommitmentKind,
    Reversibility,
    complete_commitment,
    make_act_commitment,
    make_observation_commitment,
    make_tool_contact_commitment,
    COMMITMENT_SCHEMA_VERSION,
)
from cee_core.revision import (
    ModelRevisionEvent,
    RevisionKind,
    revise_from_commitment,
    REVISION_SCHEMA_VERSION,
)


class TestWorldEntity:
    def test_creation(self):
        e = WorldEntity(entity_id="e1", kind="project", summary="Alpha project")
        assert e.entity_id == "e1"
        assert e.kind == "project"
        assert e.confidence == 1.0

    def test_custom_confidence(self):
        e = WorldEntity(entity_id="e2", kind="agent", summary="Dev", confidence=0.7)
        assert e.confidence == 0.7

    def test_round_trip(self):
        e = WorldEntity(entity_id="e3", kind="resource", summary="Server", confidence=0.9)
        d = e.to_dict()
        assert d["schema_version"] == WORLD_SCHEMA_VERSION
        restored = WorldEntity.from_dict(d)
        assert restored == e

    def test_frozen(self):
        e = WorldEntity(entity_id="e4", kind="goal", summary="Ship")
        with pytest.raises(AttributeError):
            e.entity_id = "changed"


class TestWorldRelation:
    def test_creation(self):
        r = WorldRelation(
            relation_id="r1", subject_id="e1", predicate="blocks", object_id="e2",
        )
        assert r.subject_id == "e1"
        assert r.predicate == "blocks"
        assert r.object_id == "e2"

    def test_round_trip(self):
        r = WorldRelation(
            relation_id="r2", subject_id="a", predicate="supports", object_id="b", confidence=0.8,
        )
        d = r.to_dict()
        restored = WorldRelation.from_dict(d)
        assert restored == r


class TestWorldHypothesis:
    def test_creation(self):
        h = WorldHypothesis(hypothesis_id="h1", statement="X = 5")
        assert h.status == "tentative"
        assert h.confidence == 0.5

    def test_active_status(self):
        h = WorldHypothesis(hypothesis_id="h2", statement="Y = 3", status="active", confidence=0.8)
        assert h.status == "active"

    def test_round_trip(self):
        h = WorldHypothesis(
            hypothesis_id="h3",
            statement="Z = 7",
            related_entity_ids=("e1", "e2"),
            related_relation_ids=("r1",),
            confidence=0.6,
            status="stale",
        )
        d = h.to_dict()
        restored = WorldHypothesis.from_dict(d)
        assert restored == h


class TestRevisionDelta:
    def test_creation(self):
        d = RevisionDelta(
            delta_id="d1",
            target_kind="entity_add",
            target_ref="e1",
            before_summary="none",
            after_summary="added entity",
            justification="new observation",
        )
        assert d.target_kind == "entity_add"

    def test_round_trip(self):
        d = RevisionDelta(
            delta_id="d2",
            target_kind="hypothesis_update",
            target_ref="h1",
            before_summary="tentative",
            after_summary="strengthened",
            justification="confirmed by reality",
        )
        restored = RevisionDelta.from_dict(d.to_dict())
        assert restored == d


class TestWorldState:
    def test_creation(self):
        ws = WorldState(state_id="ws_0")
        assert ws.state_id == "ws_0"
        assert ws.parent_state_id is None
        assert ws.entities == ()
        assert ws.hypotheses == ()
        assert ws.anchored_fact_summaries == ()

    def test_round_trip(self):
        ws = WorldState(
            state_id="ws_5",
            parent_state_id="ws_4",
            entities=(WorldEntity(entity_id="e1", kind="project", summary="Alpha"),),
            relations=(WorldRelation(relation_id="r1", subject_id="e1", predicate="blocks", object_id="e2"),),
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="status=ok"),),
            dominant_goals=("ship alpha",),
            active_tensions=("deadline pressure",),
            anchored_fact_summaries=("alpha_status=delayed",),
        )
        d = ws.to_dict()
        assert d["schema_version"] == WORLD_STATE_SCHEMA_VERSION
        restored = WorldState.from_dict(d)
        assert restored == ws

    def test_find_entity(self):
        ws = WorldState(
            state_id="ws_0",
            entities=(
                WorldEntity(entity_id="e1", kind="project", summary="Alpha"),
                WorldEntity(entity_id="e2", kind="project", summary="Beta"),
            ),
        )
        assert ws.find_entity("e1").summary == "Alpha"
        assert ws.find_entity("e3") is None

    def test_find_hypothesis(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(
                WorldHypothesis(hypothesis_id="h1", statement="X=5"),
                WorldHypothesis(hypothesis_id="h2", statement="Y=3", status="rejected"),
            ),
        )
        assert ws.find_hypothesis("h1").statement == "X=5"
        assert ws.find_hypothesis("h3") is None

    def test_active_hypotheses(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(
                WorldHypothesis(hypothesis_id="h1", statement="X=5", status="active"),
                WorldHypothesis(hypothesis_id="h2", statement="Y=3", status="rejected"),
                WorldHypothesis(hypothesis_id="h3", statement="Z=7", status="tentative"),
            ),
        )
        active = ws.active_hypotheses()
        assert len(active) == 2
        assert all(h.status in ("active", "tentative") for h in active)

    def test_is_fact_anchored(self):
        ws = WorldState(
            state_id="ws_0",
            anchored_fact_summaries=("alpha_status=delayed", "beta_status=on_track"),
        )
        assert ws.is_fact_anchored("alpha_status=delayed")
        assert not ws.is_fact_anchored("gamma_status=completed")


class TestWorldStateOperations:
    def test_add_entity(self):
        ws = WorldState(state_id="ws_0")
        e = WorldEntity(entity_id="e1", kind="project", summary="Alpha")
        ws2 = add_entity(ws, e, provenance_ref="report1")
        assert len(ws2.entities) == 1
        assert ws2.entities[0].entity_id == "e1"
        assert ws2.parent_state_id == "ws_0"
        assert "report1" in ws2.provenance_refs

    def test_add_relation(self):
        ws = WorldState(state_id="ws_0")
        r = WorldRelation(relation_id="r1", subject_id="e1", predicate="blocks", object_id="e2")
        ws2 = add_relation(ws, r)
        assert len(ws2.relations) == 1

    def test_add_hypothesis(self):
        ws = WorldState(state_id="ws_0")
        h = WorldHypothesis(hypothesis_id="h1", statement="status=ok")
        ws2 = add_hypothesis_to_world(ws, h)
        assert len(ws2.hypotheses) == 1
        assert ws2.hypotheses[0].status == "tentative"

    def test_update_hypothesis_status(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="X=5", confidence=0.5, status="tentative"),),
        )
        ws2 = update_hypothesis_status(ws, "h1", "active", 0.8, provenance_ref="verified")
        assert ws2.hypotheses[0].status == "active"
        assert ws2.hypotheses[0].confidence == 0.8

    def test_update_hypothesis_reject(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="X=5", confidence=0.5, status="active"),),
        )
        ws2 = update_hypothesis_status(ws, "h1", "rejected", 0.0, provenance_ref="contradicted")
        assert ws2.hypotheses[0].status == "rejected"
        assert ws2.hypotheses[0].confidence == 0.0

    def test_add_anchor_facts(self):
        ws = WorldState(state_id="ws_0")
        ws2 = add_anchor_facts(ws, ("fact1", "fact2"), provenance_ref="commit1")
        assert len(ws2.anchored_fact_summaries) == 2
        assert "fact1" in ws2.anchored_fact_summaries

    def test_add_anchor_facts_dedup(self):
        ws = WorldState(state_id="ws_0", anchored_fact_summaries=("fact1",))
        ws2 = add_anchor_facts(ws, ("fact1", "fact2"))
        assert len(ws2.anchored_fact_summaries) == 2

    def test_update_entity(self):
        ws = WorldState(
            state_id="ws_0",
            entities=(WorldEntity(entity_id="e1", kind="project", summary="Alpha", confidence=0.5),),
        )
        ws2 = update_entity(ws, "e1", summary="Alpha v2", confidence=0.9)
        assert ws2.entities[0].summary == "Alpha v2"
        assert ws2.entities[0].confidence == 0.9

    def test_remove_entity(self):
        ws = WorldState(
            state_id="ws_0",
            entities=(
                WorldEntity(entity_id="e1", kind="project", summary="Alpha"),
                WorldEntity(entity_id="e2", kind="project", summary="Beta"),
            ),
            relations=(
                WorldRelation(relation_id="r1", subject_id="e1", predicate="blocks", object_id="e2"),
            ),
        )
        ws2 = remove_entity(ws, "e1")
        assert len(ws2.entities) == 1
        assert ws2.entities[0].entity_id == "e2"
        assert len(ws2.relations) == 0

    def test_add_resolve_tension(self):
        ws = WorldState(state_id="ws_0")
        ws2 = add_tension(ws, "deadline pressure")
        assert "deadline pressure" in ws2.active_tensions
        ws3 = resolve_tension(ws2, "deadline pressure")
        assert "deadline pressure" not in ws3.active_tensions

    def test_update_self_model(self):
        ws = WorldState(state_id="ws_0")
        ws2 = update_self_model(
            ws,
            capability_summary=("code review", "testing"),
            reliability_estimate=0.7,
        )
        assert ws2.self_capability_summary == ("code review", "testing")
        assert ws2.self_reliability_estimate == 0.7

    def test_state_chain_provenance(self):
        ws = WorldState(state_id="ws_0")
        ws2 = add_entity(ws, WorldEntity(entity_id="e1", kind="project", summary="A"), provenance_ref="src1")
        ws3 = add_hypothesis_to_world(ws2, WorldHypothesis(hypothesis_id="h1", statement="ok"), provenance_ref="src2")
        assert ws3.parent_state_id is not None
        assert len(ws3.provenance_refs) == 2


class TestCommitmentEvent:
    def test_creation(self):
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Verify project status",
        )
        assert ce.commitment_kind == "observe"
        assert ce.success is True
        assert ce.reversibility == "reversible"

    def test_round_trip(self):
        ce = CommitmentEvent(
            event_id="ce2",
            source_state_id="ws_1",
            commitment_kind="act",
            intent_summary="Deploy change",
            affected_entity_ids=("e1",),
            expected_world_change=("service restarted",),
            reversibility="partially_reversible",
        )
        d = ce.to_dict()
        assert d["schema_version"] == COMMITMENT_SCHEMA_VERSION
        restored = CommitmentEvent.from_dict(d)
        assert restored == ce

    def test_make_observation(self):
        ws = WorldState(state_id="ws_0")
        ce = make_observation_commitment(ws, event_id="ce1", intent_summary="Check status")
        assert ce.commitment_kind == "observe"
        assert ce.source_state_id == "ws_0"

    def test_make_act(self):
        ws = WorldState(state_id="ws_0")
        ce = make_act_commitment(
            ws,
            event_id="ce1",
            intent_summary="Deploy",
            action_summary="kubectl apply",
            reversibility="irreversible",
        )
        assert ce.commitment_kind == "act"
        assert ce.reversibility == "irreversible"

    def test_make_tool_contact(self):
        ws = WorldState(state_id="ws_0")
        ce = make_tool_contact_commitment(
            ws,
            event_id="ce1",
            intent_summary="Query API",
            action_summary="GET /status",
        )
        assert ce.commitment_kind == "tool_contact"

    def test_complete_commitment(self):
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Check",
        )
        completed = complete_commitment(
            ce,
            success=True,
            external_result_summary="Status is OK",
            observation_summaries=("service healthy",),
        )
        assert completed.success is True
        assert completed.external_result_summary == "Status is OK"
        assert "service healthy" in completed.observation_summaries


class TestModelRevisionEvent:
    def test_creation(self):
        mr = ModelRevisionEvent(
            revision_id="rev1",
            prior_state_id="ws_0",
            caused_by_event_id="ce1",
            revision_kind="correction",
        )
        assert mr.revision_kind == "correction"
        assert mr.deltas == ()

    def test_round_trip(self):
        mr = ModelRevisionEvent(
            revision_id="rev2",
            prior_state_id="ws_1",
            caused_by_event_id="ce2",
            revision_kind="confirmation",
            deltas=(
                RevisionDelta(
                    delta_id="d1",
                    target_kind="anchor_add",
                    target_ref="fact1",
                    before_summary="not anchored",
                    after_summary="fact1",
                    justification="verified",
                ),
            ),
            strengthened_hypothesis_ids=("h1",),
            new_anchor_fact_summaries=("fact1",),
            resulting_state_id="ws_2",
            revision_summary="Confirmed hypothesis h1",
        )
        d = mr.to_dict()
        assert d["schema_version"] == REVISION_SCHEMA_VERSION
        restored = ModelRevisionEvent.from_dict(d)
        assert restored == mr
        assert len(restored.deltas) == 1


class TestReviseFromCommitment:
    def test_confirmation_revision(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="X=5", confidence=0.5),),
        )
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Verify X",
        )
        rev, new_ws = revise_from_commitment(
            ws,
            ce,
            revision_id="rev1",
            resulting_state_id="ws_final",
            strengthened_hypothesis_ids=("h1",),
            new_anchor_fact_summaries=("X=5",),
            revision_summary="Confirmed X=5",
        )
        assert rev.revision_kind == "expansion"
        assert "X=5" in new_ws.anchored_fact_summaries
        h = new_ws.find_hypothesis("h1")
        assert h.status == "active"
        assert h.confidence > 0.5

    def test_correction_revision(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="X=3", confidence=0.6, status="active"),),
        )
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Verify X",
        )
        rev, new_ws = revise_from_commitment(
            ws,
            ce,
            revision_id="rev1",
            resulting_state_id="ws_final",
            discarded_hypothesis_ids=("h1",),
            new_anchor_fact_summaries=("X=5",),
            revision_summary="Corrected: X=5 not 3",
        )
        assert rev.revision_kind == "correction"
        assert "X=5" in new_ws.anchored_fact_summaries
        h = new_ws.find_hypothesis("h1")
        assert h.status == "rejected"
        assert h.confidence == 0.0

    def test_revision_produces_deltas(self):
        ws = WorldState(
            state_id="ws_0",
            hypotheses=(WorldHypothesis(hypothesis_id="h1", statement="Y=3"),),
        )
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Verify",
        )
        rev, _ = revise_from_commitment(
            ws,
            ce,
            revision_id="rev1",
            resulting_state_id="ws_final",
            discarded_hypothesis_ids=("h1",),
            new_anchor_fact_summaries=("Y=5",),
        )
        assert len(rev.deltas) == 2
        delta_kinds = [d.target_kind for d in rev.deltas]
        assert "anchor_add" in delta_kinds
        assert "hypothesis_remove" in delta_kinds

    def test_resulting_state_id(self):
        ws = WorldState(state_id="ws_0")
        ce = CommitmentEvent(
            event_id="ce1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Verify",
        )
        rev, new_ws = revise_from_commitment(
            ws,
            ce,
            revision_id="rev1",
            resulting_state_id="ws_result",
            new_anchor_fact_summaries=("fact1",),
        )
        assert new_ws.state_id == "ws_result"
        assert rev.resulting_state_id == "ws_result"


class TestEndToEndWorkflow:
    def test_full_observe_revise_cycle(self):
        ws = WorldState(state_id="ws_0")
        ws = add_entity(ws, WorldEntity(entity_id="proj-alpha", kind="project", summary="Alpha"))
        ws = add_hypothesis_to_world(
            ws,
            WorldHypothesis(
                hypothesis_id="h1",
                statement="alpha_status=on_track",
                related_entity_ids=("proj-alpha",),
                confidence=0.6,
            ),
        )

        ce = make_observation_commitment(
            ws, event_id="ce1", intent_summary="Check alpha status",
            target_entity_ids=("proj-alpha",),
        )
        ce = complete_commitment(
            ce,
            success=True,
            external_result_summary="Alpha is delayed",
            observation_summaries=("alpha_status=delayed",),
        )

        rev, ws = revise_from_commitment(
            ws,
            ce,
            revision_id="rev1",
            resulting_state_id="ws_final",
            discarded_hypothesis_ids=("h1",),
            new_anchor_fact_summaries=("alpha_status=delayed",),
            revision_summary="Alpha is delayed, not on track",
        )

        assert rev.revision_kind == "correction"
        assert ws.is_fact_anchored("alpha_status=delayed")
        assert ws.find_hypothesis("h1").status == "rejected"
        assert len(ws.entities) == 1
