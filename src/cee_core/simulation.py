"""Simulation primitives for the world model layer.

Provides hypothesis simulation, action simulation, and multi-trajectory
exploration over WorldState. All simulation results carry the simulated
state, confidence estimate, and assumptions made.

Key invariants:
1. Simulation never modifies the original WorldState - it produces
   new simulated states that are marked with provenance.
2. Simulation results are proposals, not commitments. They must still
   pass through the policy pipeline before affecting real state.
3. Multi-trajectory simulation explores multiple futures but does not
   choose among them - that requires policy + approval.

The simulation engine is the "internal sandbox" described in ARCHITECTURE.md:
"在内部世界中展开多个未来轨迹" (unfold multiple future trajectories
in the internal world).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Sequence
from uuid import uuid4

from .event_log import EventLog
from .events import Event
from .planner import DeltaPolicyDecision, evaluate_delta_policy
from .world_schema import WorldHypothesis, WorldEntity, RevisionDelta
from .world_state import WorldState, add_hypothesis_to_world, update_hypothesis_status, update_entity

SIMULATION_SCHEMA_VERSION = "cee.simulation.v1"


@dataclass(frozen=True)
class SimulationResult:
    simulated_state: WorldState
    confidence: float
    assumptions: tuple[str, ...]
    is_simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SIMULATION_SCHEMA_VERSION,
            "confidence": self.confidence,
            "assumptions": list(self.assumptions),
            "is_simulated": self.is_simulated,
            "state_id": self.simulated_state.state_id,
        }


@dataclass(frozen=True)
class SimulationBranch:
    """A single branch in a multi-trajectory simulation.

    Each branch represents one possible future trajectory, with its
    own confidence, assumptions, and conflict status.
    """

    branch_id: str = field(default_factory=lambda: f"branch_{uuid4().hex[:8]}")
    label: str = ""
    result: SimulationResult | None = None
    confidence: float = 0.5
    assumptions: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    policy_allowed: bool = True

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def is_viable(self) -> bool:
        return self.policy_allowed and not self.has_conflicts and self.confidence > 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "label": self.label,
            "confidence": self.confidence,
            "assumptions": list(self.assumptions),
            "conflicts": list(self.conflicts),
            "policy_allowed": self.policy_allowed,
            "is_viable": self.is_viable,
        }


@dataclass(frozen=True)
class SimulationScenario:
    """A multi-trajectory simulation scenario.

    Represents the exploration of multiple possible futures from a
    single starting state. Each branch is independent - the scenario
    does not choose among them.
    """

    scenario_id: str = field(default_factory=lambda: f"scenario_{uuid4().hex[:8]}")
    source_state_id: str = ""
    branches: tuple[SimulationBranch, ...] = ()
    best_branch_id: str | None = None

    @property
    def viable_branches(self) -> tuple[SimulationBranch, ...]:
        return tuple(b for b in self.branches if b.is_viable)

    @property
    def best_branch(self) -> SimulationBranch | None:
        if self.best_branch_id is not None:
            for b in self.branches:
                if b.branch_id == self.best_branch_id:
                    return b
        viable = self.viable_branches
        if not viable:
            return None
        return max(viable, key=lambda b: b.confidence)

    @property
    def all_blocked(self) -> bool:
        return len(self.branches) > 0 and len(self.viable_branches) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "source_state_id": self.source_state_id,
            "branches": [b.to_dict() for b in self.branches],
            "best_branch_id": self.best_branch_id,
            "viable_count": len(self.viable_branches),
        }


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


def detect_conflicts(state: WorldState) -> tuple[str, ...]:
    """Detect conflicts in a WorldState.

    A conflict exists when:
    1. Two active hypotheses make contradictory claims about the same entities
    2. A hypothesis conflicts with anchored facts
    3. An entity has confidence below threshold while being referenced by active hypotheses
    """

    conflicts: list[str] = []

    active = list(state.active_hypotheses())
    for i, h1 in enumerate(active):
        for h2 in active[i + 1:]:
            shared = set(h1.related_entity_ids) & set(h2.related_entity_ids)
            if shared and h1.statement != h2.statement:
                conflicts.append(
                    f"hypothesis_conflict:{h1.hypothesis_id} vs {h2.hypothesis_id} "
                    f"over entities {shared}"
                )

    for h in active:
        for fact in state.anchored_fact_summaries:
            h_lower = h.statement.lower()
            f_lower = fact.lower()
            h_words = set(h_lower.split())
            f_words = set(f_lower.split())
            overlap = h_words & f_words
            if len(overlap) >= max(2, len(f_words) // 2):
                from .hypothesis_engine import _NEGATION_WORDS
                words = h_lower.split()
                for neg in _NEGATION_WORDS:
                    if neg in words:
                        conflicts.append(
                            f"anchor_conflict:{h.hypothesis_id} negates anchored fact"
                        )
                        break

    for h in active:
        for eid in h.related_entity_ids:
            entity = state.find_entity(eid)
            if entity is not None and entity.confidence < 0.2:
                conflicts.append(
                    f"low_confidence_entity:{eid} referenced by {h.hypothesis_id}"
                )

    return tuple(conflicts)


def simulate_branch(
    state: WorldState,
    deltas: tuple[RevisionDelta, ...],
    *,
    label: str = "",
    check_policy: bool = True,
) -> SimulationBranch:
    """Simulate a single branch by applying deltas to a copy of the state.

    This is the core "what-if" primitive. It applies a sequence of deltas
    to a copy of the current state, checks for conflicts and policy
    violations, and returns a SimulationBranch with the result.

    Key invariant: the original state is never modified.
    """

    sim_state = state
    total_confidence = 1.0
    all_assumptions: list[str] = []
    policy_allowed = True

    for delta in deltas:
        if check_policy:
            policy_decision = evaluate_delta_policy(delta)
            if not policy_decision.allowed and not policy_decision.requires_approval:
                policy_allowed = False
                all_assumptions.append(f"policy_denied:{delta.target_ref}")

        if delta.target_kind == "hypothesis_add" or delta.target_kind == "hypothesis_update":
            hypothesis = WorldHypothesis(
                hypothesis_id=f"sim_{delta.delta_id}",
                statement=delta.after_summary,
                status="tentative",
                confidence=0.5,
            )
            sim_state = add_hypothesis_to_world(
                sim_state,
                hypothesis,
                provenance_ref=f"simulate_branch:{delta.delta_id}",
            )
            total_confidence *= 0.8
        elif delta.target_kind == "entity_add" or delta.target_kind == "entity_update":
            entity = WorldEntity(
                entity_id=f"sim_{delta.delta_id}",
                kind=delta.target_kind,
                summary=delta.after_summary,
                confidence=0.5,
            )
            from .world_state import add_entity
            sim_state = add_entity(
                sim_state,
                entity,
                provenance_ref=f"simulate_branch:{delta.delta_id}",
            )
            total_confidence *= 0.9
        elif delta.target_kind == "goal_update":
            total_confidence *= 0.95
        elif delta.target_kind == "self_update":
            total_confidence *= 0.7
        else:
            total_confidence *= 0.85

        all_assumptions.append(delta.after_summary)

    sim_state = mark_simulated(sim_state)

    conflicts = detect_conflicts(sim_state)

    result = SimulationResult(
        simulated_state=sim_state,
        confidence=max(0.0, min(1.0, total_confidence)),
        assumptions=tuple(all_assumptions),
    )

    return SimulationBranch(
        label=label or f"branch_{len(deltas)}_deltas",
        result=result,
        confidence=result.confidence,
        assumptions=tuple(all_assumptions),
        conflicts=conflicts,
        policy_allowed=policy_allowed,
    )


def simulate_scenario(
    state: WorldState,
    branch_deltas: Sequence[tuple[RevisionDelta, ...]],
    *,
    labels: Sequence[str] | None = None,
    check_policy: bool = True,
    event_log: EventLog | None = None,
) -> SimulationScenario:
    """Simulate multiple branches from a single starting state.

    This is the primary multi-trajectory exploration primitive. It
    explores multiple possible futures without choosing among them.

    Key invariant: the original state is never modified. The scenario
    does not commit to any branch - that requires policy + approval.

    Pipeline:
    1. For each branch_deltas, simulate_branch()
    2. Detect conflicts in each branch
    3. Evaluate policy for each branch
    4. Rank branches by confidence
    5. Record scenario in event log (if provided)
    """

    if event_log is not None:
        event_log.append(Event(
            event_type="simulation.scenario.started",
            payload={
                "source_state_id": state.state_id,
                "branch_count": len(branch_deltas),
            },
            actor="simulation",
        ))

    branches: list[SimulationBranch] = []
    for i, deltas in enumerate(branch_deltas):
        label = labels[i] if labels and i < len(labels) else f"branch_{i}"
        branch = simulate_branch(state, deltas, label=label, check_policy=check_policy)
        branches.append(branch)

    best = None
    viable = [b for b in branches if b.is_viable]
    if viable:
        best = max(viable, key=lambda b: b.confidence)

    scenario = SimulationScenario(
        source_state_id=state.state_id,
        branches=tuple(branches),
        best_branch_id=best.branch_id if best else None,
    )

    if event_log is not None:
        event_log.append(Event(
            event_type="simulation.scenario.completed",
            payload={
                "scenario_id": scenario.scenario_id,
                "branch_count": len(branches),
                "viable_count": len(viable),
                "best_branch_id": scenario.best_branch_id,
                "all_blocked": scenario.all_blocked,
            },
            actor="simulation",
        ))

    return scenario


def compare_simulations(
    scenario: SimulationScenario,
) -> dict[str, Any]:
    """Compare branches in a simulation scenario.

    Returns a structured comparison that can be used for decision-making
    or presentation to a human operator. This function does not make
    decisions - it only provides analysis.
    """

    if not scenario.branches:
        return {
            "scenario_id": scenario.scenario_id,
            "branch_count": 0,
            "viable_count": 0,
            "recommendation": "no_branches",
        }

    viable = scenario.viable_branches
    blocked = [b for b in scenario.branches if not b.is_viable]

    branch_summaries = []
    for b in scenario.branches:
        branch_summaries.append({
            "branch_id": b.branch_id,
            "label": b.label,
            "confidence": b.confidence,
            "is_viable": b.is_viable,
            "conflict_count": len(b.conflicts),
            "policy_allowed": b.policy_allowed,
        })

    confidence_range = (
        min(b.confidence for b in scenario.branches),
        max(b.confidence for b in scenario.branches),
    )

    return {
        "scenario_id": scenario.scenario_id,
        "branch_count": len(scenario.branches),
        "viable_count": len(viable),
        "blocked_count": len(blocked),
        "confidence_range": confidence_range,
        "best_branch_id": scenario.best_branch_id,
        "branches": branch_summaries,
    }
