"""WorldState: the core object of the generative world layer.

SymbolFlow side owns: WorldState, its generation/expansion/compression/simulation
logic, tension identification, hypothesis generation, internal relation
reorganization, and possible trajectory formation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Optional, Tuple

from .world_schema import (
    Confidence,
    WorldEntity,
    WorldHypothesis,
    WorldRelation,
)

WORLD_STATE_SCHEMA_VERSION = "cee.world_state.v1"


@dataclass(frozen=True)
class WorldState:
    state_id: str
    parent_state_id: Optional[str] = None

    entities: Tuple[WorldEntity, ...] = ()
    relations: Tuple[WorldRelation, ...] = ()
    hypotheses: Tuple[WorldHypothesis, ...] = ()

    dominant_goals: Tuple[str, ...] = ()
    active_tensions: Tuple[str, ...] = ()

    self_capability_summary: Tuple[str, ...] = ()
    self_limit_summary: Tuple[str, ...] = ()
    self_reliability_estimate: Confidence = 0.5

    anchored_fact_summaries: Tuple[str, ...] = ()

    provenance_refs: Tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WORLD_STATE_SCHEMA_VERSION,
            "state_id": self.state_id,
            "parent_state_id": self.parent_state_id,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "dominant_goals": list(self.dominant_goals),
            "active_tensions": list(self.active_tensions),
            "self_capability_summary": list(self.self_capability_summary),
            "self_limit_summary": list(self.self_limit_summary),
            "self_reliability_estimate": self.self_reliability_estimate,
            "anchored_fact_summaries": list(self.anchored_fact_summaries),
            "provenance_refs": list(self.provenance_refs),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorldState:
        from .schemas import require_schema_version
        require_schema_version(payload, WORLD_STATE_SCHEMA_VERSION, required=False)
        return cls(
            state_id=payload.get("state_id", "ws_0"),
            parent_state_id=payload.get("parent_state_id"),
            entities=tuple(WorldEntity.from_dict(e) for e in payload.get("entities", [])),
            relations=tuple(WorldRelation.from_dict(r) for r in payload.get("relations", [])),
            hypotheses=tuple(WorldHypothesis.from_dict(h) for h in payload.get("hypotheses", [])),
            dominant_goals=tuple(payload.get("dominant_goals", [])),
            active_tensions=tuple(payload.get("active_tensions", [])),
            self_capability_summary=tuple(payload.get("self_capability_summary", [])),
            self_limit_summary=tuple(payload.get("self_limit_summary", [])),
            self_reliability_estimate=payload.get("self_reliability_estimate", 0.5),
            anchored_fact_summaries=tuple(payload.get("anchored_fact_summaries", [])),
            provenance_refs=tuple(payload.get("provenance_refs", [])),
        )

    def find_entity(self, entity_id: str) -> Optional[WorldEntity]:
        for e in self.entities:
            if e.entity_id == entity_id:
                return e
        return None

    def find_relation(self, relation_id: str) -> Optional[WorldRelation]:
        for r in self.relations:
            if r.relation_id == relation_id:
                return r
        return None

    def find_hypothesis(self, hypothesis_id: str) -> Optional[WorldHypothesis]:
        for h in self.hypotheses:
            if h.hypothesis_id == hypothesis_id:
                return h
        return None

    def entities_of_kind(self, kind: str) -> Tuple[WorldEntity, ...]:
        return tuple(e for e in self.entities if e.kind == kind)

    def relations_for_subject(self, subject_id: str) -> Tuple[WorldRelation, ...]:
        return tuple(r for r in self.relations if r.subject_id == subject_id)

    def relations_for_object(self, object_id: str) -> Tuple[WorldRelation, ...]:
        return tuple(r for r in self.relations if r.object_id == object_id)

    def active_hypotheses(self) -> Tuple[WorldHypothesis, ...]:
        return tuple(h for h in self.hypotheses if h.status in ("active", "tentative"))

    def rejected_hypotheses(self) -> Tuple[WorldHypothesis, ...]:
        return tuple(h for h in self.hypotheses if h.status == "rejected")

    def is_fact_anchored(self, fact_summary: str) -> bool:
        return fact_summary in self.anchored_fact_summaries


def _next_state_id(state: WorldState) -> str:
    return f"ws_{int(state.state_id.split('_')[-1]) + 1}" if state.state_id.startswith("ws_") else f"ws_1"


def add_entity(state: WorldState, entity: WorldEntity, *, provenance_ref: str = "") -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        entities=state.entities + (entity,),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def add_relation(state: WorldState, relation: WorldRelation, *, provenance_ref: str = "") -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        relations=state.relations + (relation,),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def add_hypothesis_to_world(state: WorldState, hypothesis: WorldHypothesis, *, provenance_ref: str = "") -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        hypotheses=state.hypotheses + (hypothesis,),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def update_hypothesis_status(
    state: WorldState,
    hypothesis_id: str,
    new_status: str,
    new_confidence: Confidence,
    *,
    provenance_ref: str = "",
) -> WorldState:
    updated = []
    for h in state.hypotheses:
        if h.hypothesis_id == hypothesis_id:
            updated.append(replace(h, status=new_status, confidence=new_confidence))
        else:
            updated.append(h)
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        hypotheses=tuple(updated),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def add_anchor_facts(
    state: WorldState,
    fact_summaries: Tuple[str, ...],
    *,
    provenance_ref: str = "",
) -> WorldState:
    merged = tuple(dict.fromkeys(state.anchored_fact_summaries + fact_summaries))
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        anchored_fact_summaries=merged,
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def update_entity(
    state: WorldState,
    entity_id: str,
    *,
    summary: Optional[str] = None,
    confidence: Optional[Confidence] = None,
    provenance_ref: str = "",
) -> WorldState:
    updated = []
    for e in state.entities:
        if e.entity_id == entity_id:
            updated.append(replace(
                e,
                summary=summary if summary is not None else e.summary,
                confidence=confidence if confidence is not None else e.confidence,
            ))
        else:
            updated.append(e)
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        entities=tuple(updated),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def remove_entity(state: WorldState, entity_id: str, *, provenance_ref: str = "") -> WorldState:
    updated_entities = tuple(e for e in state.entities if e.entity_id != entity_id)
    updated_relations = tuple(
        r for r in state.relations
        if r.subject_id != entity_id and r.object_id != entity_id
    )
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        entities=updated_entities,
        relations=updated_relations,
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def add_tension(state: WorldState, tension: str, *, provenance_ref: str = "") -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        active_tensions=state.active_tensions + (tension,),
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def resolve_tension(state: WorldState, tension: str, *, provenance_ref: str = "") -> WorldState:
    updated = tuple(t for t in state.active_tensions if t != tension)
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        active_tensions=updated,
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def update_self_model(
    state: WorldState,
    *,
    capability_summary: Optional[Tuple[str, ...]] = None,
    limit_summary: Optional[Tuple[str, ...]] = None,
    reliability_estimate: Optional[Confidence] = None,
    provenance_ref: str = "",
) -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        self_capability_summary=capability_summary if capability_summary is not None else state.self_capability_summary,
        self_limit_summary=limit_summary if limit_summary is not None else state.self_limit_summary,
        self_reliability_estimate=reliability_estimate if reliability_estimate is not None else state.self_reliability_estimate,
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )


def update_dominant_goals(
    state: WorldState,
    goals: Tuple[str, ...],
    *,
    provenance_ref: str = "",
) -> WorldState:
    return replace(
        state,
        state_id=_next_state_id(state),
        parent_state_id=state.state_id,
        dominant_goals=goals,
        provenance_refs=state.provenance_refs + ((provenance_ref,) if provenance_ref else ()),
    )
