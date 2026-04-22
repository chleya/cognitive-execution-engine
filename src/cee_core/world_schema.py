"""Shared protocol types for the world model layer.

These objects live in the shared protocol layer because both SymbolFlow
(generative world layer) and CEE (reality commitment layer) read and write them.
They define the basic syntax of world representation, not implementation details
of either side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Tuple

Confidence = float

from .schemas import require_schema_version

WORLD_SCHEMA_VERSION = "cee.world_schema.v1"


@dataclass(frozen=True)
class WorldEntity:
    entity_id: str
    kind: str
    summary: str
    confidence: Confidence = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WORLD_SCHEMA_VERSION,
            "entity_id": self.entity_id,
            "kind": self.kind,
            "summary": self.summary,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorldEntity:
        require_schema_version(payload, WORLD_SCHEMA_VERSION, required=False)
        return cls(
            entity_id=payload["entity_id"],
            kind=payload["kind"],
            summary=payload["summary"],
            confidence=payload.get("confidence", 1.0),
        )


@dataclass(frozen=True)
class WorldRelation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    confidence: Confidence = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WORLD_SCHEMA_VERSION,
            "relation_id": self.relation_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorldRelation:
        require_schema_version(payload, WORLD_SCHEMA_VERSION, required=False)
        return cls(
            relation_id=payload["relation_id"],
            subject_id=payload["subject_id"],
            predicate=payload["predicate"],
            object_id=payload["object_id"],
            confidence=payload.get("confidence", 1.0),
        )


@dataclass(frozen=True)
class WorldHypothesis:
    hypothesis_id: str
    statement: str
    related_entity_ids: Tuple[str, ...] = ()
    related_relation_ids: Tuple[str, ...] = ()
    confidence: Confidence = 0.5
    status: Literal["active", "tentative", "stale", "rejected"] = "tentative"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": WORLD_SCHEMA_VERSION,
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "related_entity_ids": list(self.related_entity_ids),
            "related_relation_ids": list(self.related_relation_ids),
            "confidence": self.confidence,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorldHypothesis:
        require_schema_version(payload, WORLD_SCHEMA_VERSION, required=False)
        return cls(
            hypothesis_id=payload["hypothesis_id"],
            statement=payload["statement"],
            related_entity_ids=tuple(payload.get("related_entity_ids", ())),
            related_relation_ids=tuple(payload.get("related_relation_ids", ())),
            confidence=payload.get("confidence", 0.5),
            status=payload.get("status", "tentative"),
        )


RevisionTargetKind = Literal[
    "entity_add",
    "entity_update",
    "entity_remove",
    "relation_add",
    "relation_update",
    "relation_remove",
    "hypothesis_add",
    "hypothesis_update",
    "hypothesis_remove",
    "goal_update",
    "tension_update",
    "anchor_add",
    "self_update",
]


@dataclass(frozen=True)
class RevisionDelta:
    delta_id: str
    target_kind: RevisionTargetKind
    target_ref: str
    before_summary: str
    after_summary: str
    justification: str
    raw_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": WORLD_SCHEMA_VERSION,
            "delta_id": self.delta_id,
            "target_kind": self.target_kind,
            "target_ref": self.target_ref,
            "before_summary": self.before_summary,
            "after_summary": self.after_summary,
            "justification": self.justification,
        }
        if self.raw_value is not None:
            d["raw_value"] = self.raw_value
        return d

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RevisionDelta:
        require_schema_version(payload, WORLD_SCHEMA_VERSION, required=False)
        return cls(
            delta_id=payload["delta_id"],
            target_kind=payload["target_kind"],
            target_ref=payload["target_ref"],
            before_summary=payload["before_summary"],
            after_summary=payload["after_summary"],
            justification=payload["justification"],
            raw_value=payload.get("raw_value"),
        )
