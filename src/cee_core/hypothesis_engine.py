"""Hypothesis engine: generates and ranks hypothesis candidates from tensions and conflicts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from itertools import combinations
from typing import Tuple

from .world_schema import WorldHypothesis
from .world_state import WorldState


@dataclass(frozen=True)
class HypothesisCandidate:
    candidate_id: str
    statement: str
    source_tension: str
    source_conflict: str
    confidence: float = 0.5
    related_entity_ids: Tuple[str, ...] = ()


_NEGATION_WORDS = frozenset(
    {"not", "never", "no", "false", "isn't", "aren't", "wasn't", "weren't", "cannot", "can't"}
)


def _extract_entity_ids_from_text(
    text: str, entities: Tuple
) -> Tuple[str, ...]:
    text_lower = text.lower()
    matched = []
    for entity in entities:
        if entity.entity_id.lower() in text_lower:
            matched.append(entity.entity_id)
    return tuple(matched)


def _count_relations_for_entities(
    entity_ids: Tuple[str, ...], state: WorldState
) -> int:
    count = 0
    for eid in entity_ids:
        count += len(state.relations_for_subject(eid))
        count += len(state.relations_for_object(eid))
    return count


def _conflicts_with_anchored(
    statement: str, anchored_facts: Tuple[str, ...]
) -> bool:
    statement_lower = statement.lower()
    for fact in anchored_facts:
        fact_lower = fact.lower()
        if fact_lower in statement_lower:
            words = statement_lower.split()
            for neg in _NEGATION_WORDS:
                if neg in words:
                    return True
    return False


def generate_from_tension(state: WorldState) -> list[HypothesisCandidate]:
    candidates: list[HypothesisCandidate] = []
    for idx, tension in enumerate(state.active_tensions):
        entity_ids = _extract_entity_ids_from_text(tension, state.entities)
        candidate = HypothesisCandidate(
            candidate_id=f"hc_t_{idx}_{uuid.uuid4().hex[:8]}",
            statement=f"Possible resolution of tension: {tension}",
            source_tension=tension,
            source_conflict="",
            confidence=0.5,
            related_entity_ids=entity_ids,
        )
        candidates.append(candidate)
    return candidates


def generate_from_conflict(state: WorldState) -> list[HypothesisCandidate]:
    active = list(state.active_hypotheses())
    candidates: list[HypothesisCandidate] = []
    idx = 0
    for h1, h2 in combinations(active, 2):
        shared_entities = set(h1.related_entity_ids) & set(h2.related_entity_ids)
        if shared_entities and h1.statement != h2.statement:
            conflict_label = f"{h1.hypothesis_id} vs {h2.hypothesis_id}"
            candidate = HypothesisCandidate(
                candidate_id=f"hc_c_{idx}_{uuid.uuid4().hex[:8]}",
                statement=f"Resolution of conflict between '{h1.statement}' and '{h2.statement}'",
                source_tension="",
                source_conflict=conflict_label,
                confidence=0.4,
                related_entity_ids=tuple(shared_entities),
            )
            candidates.append(candidate)
            idx += 1
    return candidates


def rank_hypotheses(
    candidates: list[HypothesisCandidate], state: WorldState
) -> list[HypothesisCandidate]:
    scored: list[HypothesisCandidate] = []
    for c in candidates:
        score = c.confidence
        relation_count = _count_relations_for_entities(c.related_entity_ids, state)
        if relation_count > 0:
            score += min(0.1, 0.01 * relation_count)
        if _conflicts_with_anchored(c.statement, state.anchored_fact_summaries):
            score -= 0.15
        score = max(0.0, min(1.0, score))
        updated = HypothesisCandidate(
            candidate_id=c.candidate_id,
            statement=c.statement,
            source_tension=c.source_tension,
            source_conflict=c.source_conflict,
            confidence=round(score, 4),
            related_entity_ids=c.related_entity_ids,
        )
        scored.append(updated)
    scored.sort(key=lambda c: c.confidence, reverse=True)
    return scored
