"""Tests for enhanced Simulation Engine.

Tests cover:
- SimulationBranch: viability, conflicts, policy status
- SimulationScenario: multi-trajectory exploration, best branch selection
- detect_conflicts(): hypothesis conflicts, anchor conflicts, low confidence entities
- simulate_branch(): policy-aware evaluation, delta application
- simulate_scenario(): multi-branch exploration with audit trail
- compare_simulations(): branch comparison analysis
- Original functions still work (backward compatibility)
"""

import pytest

from cee_core.event_log import EventLog
from cee_core.simulation import (
    SimulationBranch,
    SimulationResult,
    SimulationScenario,
    compare_simulations,
    detect_conflicts,
    mark_simulated,
    simulate_action,
    simulate_branch,
    simulate_hypothesis,
    simulate_scenario,
)
from cee_core.world_schema import WorldEntity, WorldHypothesis, RevisionDelta
from cee_core.world_state import WorldState, add_entity, add_hypothesis_to_world


def _make_state(**kwargs) -> WorldState:
    return WorldState(state_id="ws_0", **kwargs)


def _make_delta(
    target_kind: str = "entity_update",
    target_ref: str = "beliefs.test",
    after_summary: str = "updated",
) -> RevisionDelta:
    return RevisionDelta(
        delta_id="delta-1",
        target_kind=target_kind,
        target_ref=target_ref,
        before_summary="unknown",
        after_summary=after_summary,
        justification="test simulation",
    )


class TestSimulationBranch:
    def test_default_values(self):
        branch = SimulationBranch()
        assert branch.confidence == 0.5
        assert branch.policy_allowed is True
        assert not branch.has_conflicts
        assert branch.is_viable

    def test_has_conflicts(self):
        branch = SimulationBranch(conflicts=("conflict_1",))
        assert branch.has_conflicts

    def test_no_conflicts(self):
        branch = SimulationBranch(conflicts=())
        assert not branch.has_conflicts

    def test_is_viable_when_all_clear(self):
        branch = SimulationBranch(confidence=0.8, policy_allowed=True, conflicts=())
        assert branch.is_viable

    def test_not_viable_when_policy_blocked(self):
        branch = SimulationBranch(confidence=0.8, policy_allowed=False, conflicts=())
        assert not branch.is_viable

    def test_not_viable_when_conflicts(self):
        branch = SimulationBranch(confidence=0.8, policy_allowed=True, conflicts=("c1",))
        assert not branch.is_viable

    def test_not_viable_when_zero_confidence(self):
        branch = SimulationBranch(confidence=0.0, policy_allowed=True, conflicts=())
        assert not branch.is_viable

    def test_to_dict(self):
        branch = SimulationBranch(
            branch_id="b1",
            label="test",
            confidence=0.7,
            policy_allowed=True,
        )
        d = branch.to_dict()
        assert d["branch_id"] == "b1"
        assert d["label"] == "test"
        assert d["confidence"] == 0.7
        assert d["is_viable"] is True

    def test_unique_branch_ids(self):
        b1 = SimulationBranch()
        b2 = SimulationBranch()
        assert b1.branch_id != b2.branch_id


class TestSimulationScenario:
    def test_empty_scenario(self):
        scenario = SimulationScenario()
        assert scenario.viable_branches == ()
        assert scenario.best_branch is None
        assert not scenario.all_blocked

    def test_single_viable_branch(self):
        branch = SimulationBranch(branch_id="b1", confidence=0.8, policy_allowed=True)
        scenario = SimulationScenario(branches=(branch,), best_branch_id="b1")
        assert len(scenario.viable_branches) == 1
        assert scenario.best_branch is not None
        assert scenario.best_branch.branch_id == "b1"

    def test_multiple_viable_branches_best_by_confidence(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.5, policy_allowed=True)
        b2 = SimulationBranch(branch_id="b2", confidence=0.9, policy_allowed=True)
        b3 = SimulationBranch(branch_id="b3", confidence=0.7, policy_allowed=True)
        scenario = SimulationScenario(branches=(b1, b2, b3))
        assert scenario.best_branch is not None
        assert scenario.best_branch.branch_id == "b2"

    def test_all_blocked(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.5, policy_allowed=False)
        b2 = SimulationBranch(branch_id="b2", confidence=0.3, conflicts=("c1",))
        scenario = SimulationScenario(branches=(b1, b2))
        assert scenario.all_blocked
        assert scenario.best_branch is None

    def test_not_all_blocked_with_viable(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.5, policy_allowed=False)
        b2 = SimulationBranch(branch_id="b2", confidence=0.8, policy_allowed=True)
        scenario = SimulationScenario(branches=(b1, b2))
        assert not scenario.all_blocked

    def test_to_dict(self):
        branch = SimulationBranch(branch_id="b1", confidence=0.8)
        scenario = SimulationScenario(
            source_state_id="ws_0",
            branches=(branch,),
            best_branch_id="b1",
        )
        d = scenario.to_dict()
        assert d["source_state_id"] == "ws_0"
        assert d["viable_count"] == 1
        assert len(d["branches"]) == 1

    def test_best_branch_by_id(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.9)
        b2 = SimulationBranch(branch_id="b2", confidence=0.5)
        scenario = SimulationScenario(branches=(b1, b2), best_branch_id="b1")
        assert scenario.best_branch is not None
        assert scenario.best_branch.branch_id == "b1"


class TestDetectConflicts:
    def test_no_conflicts_in_empty_state(self):
        state = _make_state()
        conflicts = detect_conflicts(state)
        assert conflicts == ()

    def test_hypothesis_conflict_detected(self):
        state = _make_state()
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="X is true",
            status="active",
            confidence=0.8,
            related_entity_ids=("e1",),
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="X is false",
            status="active",
            confidence=0.7,
            related_entity_ids=("e1",),
        )
        state = add_hypothesis_to_world(state, h1, provenance_ref="test")
        state = add_hypothesis_to_world(state, h2, provenance_ref="test")

        conflicts = detect_conflicts(state)
        assert len(conflicts) > 0
        assert any("hypothesis_conflict" in c for c in conflicts)

    def test_no_conflict_for_unrelated_hypotheses(self):
        state = _make_state()
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="A is true",
            status="active",
            confidence=0.8,
            related_entity_ids=("e1",),
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="B is true",
            status="active",
            confidence=0.7,
            related_entity_ids=("e2",),
        )
        state = add_hypothesis_to_world(state, h1, provenance_ref="test")
        state = add_hypothesis_to_world(state, h2, provenance_ref="test")

        conflicts = detect_conflicts(state)
        assert not any("hypothesis_conflict" in c for c in conflicts)

    def test_anchor_conflict_detected(self):
        state = _make_state(anchored_fact_summaries=("the sky is blue",))
        h = WorldHypothesis(
            hypothesis_id="h1",
            statement="the sky is not blue",
            status="active",
            confidence=0.5,
        )
        state = add_hypothesis_to_world(state, h, provenance_ref="test")

        conflicts = detect_conflicts(state)
        assert any("anchor_conflict" in c for c in conflicts)

    def test_low_confidence_entity_conflict(self):
        state = _make_state()
        entity = WorldEntity(
            entity_id="e1",
            kind="test",
            summary="low confidence entity",
            confidence=0.1,
        )
        state = add_entity(state, entity, provenance_ref="test")
        h = WorldHypothesis(
            hypothesis_id="h1",
            statement="test",
            status="active",
            confidence=0.8,
            related_entity_ids=("e1",),
        )
        state = add_hypothesis_to_world(state, h, provenance_ref="test")

        conflicts = detect_conflicts(state)
        assert any("low_confidence_entity" in c for c in conflicts)


class TestSimulateBranch:
    def test_basic_branch_simulation(self):
        state = _make_state()
        deltas = (_make_delta(),)
        branch = simulate_branch(state, deltas, label="test_branch")

        assert branch.label == "test_branch"
        assert branch.result is not None
        assert branch.result.is_simulated

    def test_branch_preserves_original_state(self):
        state = _make_state()
        deltas = (_make_delta(),)
        simulate_branch(state, deltas)

        assert state.state_id == "ws_0"
        assert "is_simulated" not in state.provenance_refs

    def test_branch_with_policy_denied_delta(self):
        state = _make_state()
        delta = _make_delta(target_kind="entity_update", target_ref="policy.rule1")
        branch = simulate_branch(state, (delta,), check_policy=True)

        assert not branch.policy_allowed

    def test_branch_without_policy_check(self):
        state = _make_state()
        delta = _make_delta(target_kind="entity_update", target_ref="policy.rule1")
        branch = simulate_branch(state, (delta,), check_policy=False)

        assert branch.policy_allowed

    def test_branch_with_goal_update(self):
        state = _make_state()
        delta = _make_delta(target_kind="goal_update", target_ref="goals.active")
        branch = simulate_branch(state, (delta,))

        assert branch.confidence > 0.0

    def test_branch_with_self_update(self):
        state = _make_state()
        delta = _make_delta(target_kind="self_update", target_ref="self_model.cap")
        branch = simulate_branch(state, (delta,))

        assert branch.confidence > 0.0

    def test_branch_confidence_decreases_with_more_deltas(self):
        state = _make_state()
        single = simulate_branch(state, (_make_delta(),), label="single")
        double = simulate_branch(state, (_make_delta(), _make_delta()), label="double")

        assert double.confidence <= single.confidence

    def test_branch_empty_deltas(self):
        state = _make_state()
        branch = simulate_branch(state, (), label="empty")

        assert branch.confidence == 1.0
        assert branch.is_viable


class TestSimulateScenario:
    def test_multi_branch_scenario(self):
        state = _make_state()
        branch_deltas = [
            (_make_delta(target_ref="beliefs.a"),),
            (_make_delta(target_ref="beliefs.b"),),
            (_make_delta(target_ref="goals.active", target_kind="goal_update"),),
        ]
        scenario = simulate_scenario(state, branch_deltas, labels=["A", "B", "C"])

        assert len(scenario.branches) == 3
        assert scenario.best_branch is not None

    def test_scenario_with_labels(self):
        state = _make_state()
        branch_deltas = [
            (_make_delta(),),
            (_make_delta(),),
        ]
        scenario = simulate_scenario(state, branch_deltas, labels=["conservative", "aggressive"])

        assert scenario.branches[0].label == "conservative"
        assert scenario.branches[1].label == "aggressive"

    def test_scenario_without_labels(self):
        state = _make_state()
        branch_deltas = [
            (_make_delta(),),
            (_make_delta(),),
        ]
        scenario = simulate_scenario(state, branch_deltas)

        assert scenario.branches[0].label == "branch_0"
        assert scenario.branches[1].label == "branch_1"

    def test_scenario_with_event_log(self):
        state = _make_state()
        log = EventLog()
        branch_deltas = [(_make_delta(),)]
        simulate_scenario(state, branch_deltas, event_log=log)

        event_types = [e.event_type for e in log.all()]
        assert "simulation.scenario.started" in event_types
        assert "simulation.scenario.completed" in event_types

    def test_scenario_all_blocked(self):
        state = _make_state()
        branch_deltas = [
            (_make_delta(target_ref="policy.rule1"),),
            (_make_delta(target_ref="meta.config"),),
        ]
        scenario = simulate_scenario(state, branch_deltas)

        assert scenario.all_blocked

    def test_scenario_preserves_original_state(self):
        state = _make_state()
        branch_deltas = [(_make_delta(),)]
        simulate_scenario(state, branch_deltas)

        assert state.state_id == "ws_0"
        assert "is_simulated" not in state.provenance_refs

    def test_scenario_empty_branches(self):
        state = _make_state()
        scenario = simulate_scenario(state, [])

        assert len(scenario.branches) == 0
        assert scenario.best_branch is None


class TestCompareSimulations:
    def test_compare_empty_scenario(self):
        scenario = SimulationScenario()
        comparison = compare_simulations(scenario)

        assert comparison["branch_count"] == 0
        assert comparison["recommendation"] == "no_branches"

    def test_compare_with_viable_branches(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.5, policy_allowed=True)
        b2 = SimulationBranch(branch_id="b2", confidence=0.9, policy_allowed=True)
        scenario = SimulationScenario(branches=(b1, b2), best_branch_id="b2")

        comparison = compare_simulations(scenario)
        assert comparison["viable_count"] == 2
        assert comparison["blocked_count"] == 0
        assert comparison["best_branch_id"] == "b2"

    def test_compare_with_blocked_branches(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.5, policy_allowed=False)
        b2 = SimulationBranch(branch_id="b2", confidence=0.9, policy_allowed=True)
        scenario = SimulationScenario(branches=(b1, b2), best_branch_id="b2")

        comparison = compare_simulations(scenario)
        assert comparison["viable_count"] == 1
        assert comparison["blocked_count"] == 1

    def test_compare_confidence_range(self):
        b1 = SimulationBranch(branch_id="b1", confidence=0.3)
        b2 = SimulationBranch(branch_id="b2", confidence=0.9)
        scenario = SimulationScenario(branches=(b1, b2))

        comparison = compare_simulations(scenario)
        assert comparison["confidence_range"] == (0.3, 0.9)

    def test_compare_branch_summaries(self):
        b1 = SimulationBranch(branch_id="b1", label="safe", confidence=0.8, policy_allowed=True)
        scenario = SimulationScenario(branches=(b1,))

        comparison = compare_simulations(scenario)
        assert len(comparison["branches"]) == 1
        assert comparison["branches"][0]["label"] == "safe"
        assert comparison["branches"][0]["is_viable"] is True


class TestSimulationResultSerialization:
    def test_result_to_dict(self):
        state = _make_state()
        result = SimulationResult(
            simulated_state=state,
            confidence=0.75,
            assumptions=("a1", "a2"),
        )
        d = result.to_dict()
        assert d["confidence"] == 0.75
        assert d["assumptions"] == ["a1", "a2"]
        assert d["is_simulated"] is True


class TestBackwardCompatibility:
    def test_simulate_hypothesis_still_works(self):
        state = _make_state()
        h = WorldHypothesis(
            hypothesis_id="h1",
            statement="test hypothesis",
            status="tentative",
            confidence=0.7,
        )
        result = simulate_hypothesis(state, h)

        assert result.confidence == 0.7
        assert result.is_simulated

    def test_simulate_action_still_works(self):
        state = _make_state()
        result = simulate_action(state, "test action", ("change1", "change2"))

        assert result.confidence == 0.5
        assert len(result.assumptions) == 3

    def test_mark_simulated_still_works(self):
        state = _make_state()
        marked = mark_simulated(state)

        assert "is_simulated" in marked.provenance_refs
