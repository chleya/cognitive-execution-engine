"""Simulation primitives for the world model layer.

Provides hypothesis simulation and action simulation over WorldState,
producing SimulationResult objects that carry the simulated state,
confidence estimate, and assumptions made.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .world_schema import WorldHypothesis, WorldEntity
from .world_state import WorldState, add_hypothesis_to_world, update_hypothesis_status, update_entity


@dataclass(frozen=True)
class SimulationResult:
    simulated_state: WorldState
    confidence: float
    assumptions: tuple[str, ...]
    is_simulated: bool = True


def mark_simulated(state: WorldState) -> WorldState:
    return replace(
        state,
        provenance_refs=state.provenance_refs + ("is_simulated",),
    )


def simulate_hypothesis(state: WorldState, hypothesis: WorldHypothesis) -> SimulationResult:
    conflicts_with_anchor = any(
        fact in hypothesis.statement or hypothesis.statement in fact
        for fact in state.anchored_fact_summaries
    )

    confidence = 0.1 if conflicts_with_anchor else hypothesis.confidence

    assumptions = (hypothesis.statement,)

    existing = state.find_hypothesis(hypothesis.hypothesis_id)

    if existing is not None:
        sim_state = update_hypothesis_status(
            state,
            hypothesis.hypothesis_id,
            "active",
            confidence,
            provenance_ref="simulate_hypothesis",
        )
    else:
        active_hypothesis = replace(hypothesis, status="active", confidence=confidence)
        sim_state = add_hypothesis_to_world(
            state,
            active_hypothesis,
            provenance_ref="simulate_hypothesis",
        )

    for entity_id in hypothesis.related_entity_ids:
        sim_state = update_entity(
            sim_state,
            entity_id,
            confidence=confidence,
            provenance_ref="simulate_hypothesis",
        )

    sim_state = mark_simulated(sim_state)

    return SimulationResult(
        simulated_state=sim_state,
        confidence=confidence,
        assumptions=assumptions,
    )


def simulate_action(
    state: WorldState,
    action_summary: str,
    expected_changes: tuple[str, ...],
) -> SimulationResult:
    assumptions = (action_summary,) + expected_changes

    sim_state = state
    for i, change in enumerate(expected_changes):
        hypothesis = WorldHypothesis(
            hypothesis_id=f"sim_action_{i}",
            statement=change,
            status="tentative",
            confidence=0.5,
        )
        sim_state = add_hypothesis_to_world(
            sim_state,
            hypothesis,
            provenance_ref="simulate_action",
        )

    sim_state = mark_simulated(sim_state)

    return SimulationResult(
        simulated_state=sim_state,
        confidence=0.5,
        assumptions=assumptions,
    )
