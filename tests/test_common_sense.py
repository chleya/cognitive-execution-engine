import pytest

from cee_core import State
from cee_core.common_sense import (
    ConservationLawResult,
    EntropyResult,
    EquipartitionResult,
    GroundStateResult,
    UncertaintyPrincipleResult,
    check_conservation_law,
    check_equipartition,
    check_uncertainty_principle,
    compute_belief_entropy,
    compute_ground_state,
)


class TestConservationLaw:

    def test_empty_state_has_no_invariants(self):
        state = State()
        result = check_conservation_law(state)

        assert result.invariant_count == 0
        assert result.conservation_strength == 0.0
        assert len(result.violated) == 0

    def test_well_verified_beliefs_are_invariant(self):
        state = State(beliefs={
            "axiom_1": {"confidence": 0.99, "evidence_count": 5},
            "axiom_2": {"confidence": 0.95, "evidence_count": 3},
        })
        result = check_conservation_law(state, min_verifications=2)

        assert result.invariant_count == 2
        assert result.conservation_strength == 1.0

    def test_low_evidence_beliefs_are_not_invariant(self):
        state = State(beliefs={
            "weak": {"confidence": 0.99, "evidence_count": 1},
        })
        result = check_conservation_law(state, min_verifications=2)

        assert result.invariant_count == 0

    def test_confidence_drop_is_violation(self):
        prev = State(beliefs={
            "axiom": {"confidence": 0.95, "evidence_count": 5},
        })
        curr = State(beliefs={
            "axiom": {"confidence": 0.5, "evidence_count": 5},
        })
        result = check_conservation_law(curr, previous_state=prev, min_verifications=2)

        assert len(result.violated) > 0
        assert "confidence dropped" in result.violated[0]

    def test_disappeared_invariant_is_violation(self):
        prev = State(beliefs={
            "axiom": {"confidence": 0.95, "evidence_count": 5},
        })
        curr = State(beliefs={})
        result = check_conservation_law(curr, previous_state=prev, min_verifications=2)

        assert len(result.violated) > 0
        assert "disappeared" in result.violated[0]

    def test_stable_invariants_no_violation(self):
        prev = State(beliefs={
            "axiom": {"confidence": 0.95, "evidence_count": 5},
        })
        curr = State(beliefs={
            "axiom": {"confidence": 0.96, "evidence_count": 6},
        })
        result = check_conservation_law(curr, previous_state=prev, min_verifications=2)

        assert len(result.violated) == 0


class TestGroundState:

    def test_empty_state_has_zero_energy(self):
        state = State()
        result = compute_ground_state(state)

        assert result.total_energy == 0.0
        assert result.ground_state_count == 0

    def test_perfect_confidence_is_ground_state(self):
        state = State(beliefs={
            "axiom": {"confidence": 1.0},
        })
        result = compute_ground_state(state)

        assert result.ground_state_count == 1
        assert result.excited_count == 0
        assert result.total_energy == 0.0

    def test_low_confidence_is_excited(self):
        state = State(beliefs={
            "hypothesis": {"confidence": 0.5},
        })
        result = compute_ground_state(state, ground_confidence=0.95)

        assert result.excited_count == 1
        assert result.total_energy > 0.0

    def test_energy_formula(self):
        state = State(beliefs={
            "b1": {"confidence": 0.5},
        })
        result = compute_ground_state(state, ground_confidence=0.95)

        import math
        expected = -math.log2(0.5)
        assert abs(result.total_energy - expected) < 0.01

    def test_mixed_beliefs(self):
        state = State(beliefs={
            "axiom": {"confidence": 0.99},
            "hypothesis": {"confidence": 0.6},
        })
        result = compute_ground_state(state, ground_confidence=0.95)

        assert result.ground_state_count == 1
        assert result.excited_count == 1


class TestBeliefEntropy:

    def test_empty_state_has_zero_entropy(self):
        state = State()
        result = compute_belief_entropy(state)

        assert result.entropy == 0.0

    def test_single_certain_belief_low_entropy(self):
        state = State(beliefs={
            "b1": {"confidence": 0.99},
        })
        result = compute_belief_entropy(state)

        assert result.entropy < 0.1

    def test_uniform_confidence_high_entropy(self):
        state = State(beliefs={
            "b1": {"confidence": 0.5},
            "b2": {"confidence": 0.5},
            "b3": {"confidence": 0.5},
            "b4": {"confidence": 0.5},
        })
        result = compute_belief_entropy(state)

        assert result.entropy > 1.0

    def test_entropy_increase_detected(self):
        prev = State(beliefs={
            "b1": {"confidence": 0.9},
        })
        curr = State(beliefs={
            "b1": {"confidence": 0.5},
            "b2": {"confidence": 0.5},
        })
        result = compute_belief_entropy(curr, previous_state=prev)

        assert result.increasing is True

    def test_entropy_decrease_detected(self):
        prev = State(beliefs={
            "b1": {"confidence": 0.5},
            "b2": {"confidence": 0.5},
        })
        curr = State(beliefs={
            "b1": {"confidence": 0.99},
        })
        result = compute_belief_entropy(curr, previous_state=prev)

        assert result.increasing is False


class TestEquipartition:

    def test_empty_state_all_unknown(self):
        state = State()
        result = check_equipartition(state)

        assert result.unknown_sections > 0
        assert result.max_prior_confidence > 0.0

    def test_populated_state_has_known_sections(self):
        state = State(
            goals={"g1": "done"},
            beliefs={"b1": {"confidence": 0.9}},
        )
        result = check_equipartition(state)

        assert result.known_sections >= 2

    def test_prior_is_reciprocal_of_sections(self):
        state = State()
        result = check_equipartition(state)

        expected_prior = 1.0 / result.total_sections
        assert abs(result.max_prior_confidence - expected_prior) < 0.01


class TestUncertaintyPrinciple:

    def test_precise_belief_with_low_evidence_rate(self):
        state = State(beliefs={
            "b1": {"confidence": 0.99, "evidence_count": 100},
        })
        result = check_uncertainty_principle(state, "b1")

        assert result is not None
        assert result.precision < 0.05
        assert result.evidence_rate < 0.05

    def test_imprecise_belief_with_high_evidence_rate(self):
        state = State(beliefs={
            "b1": {"confidence": 0.3, "evidence_count": 1},
        })
        result = check_uncertainty_principle(
            state, "b1", previous_evidence_count=10,
        )

        assert result is not None
        assert result.precision > 0.5
        assert result.evidence_rate > 5

    def test_nonexistent_belief_returns_none(self):
        state = State()
        result = check_uncertainty_principle(state, "missing")

        assert result is None

    def test_belief_without_confidence_returns_none(self):
        state = State(beliefs={"b1": {"data": "no confidence"}})
        result = check_uncertainty_principle(state, "b1")

        assert result is None

    def test_product_formula(self):
        state = State(beliefs={
            "b1": {"confidence": 0.5, "evidence_count": 2},
        })
        result = check_uncertainty_principle(state, "b1", evidence_quantum=0.1)

        assert result is not None
        expected_precision = 0.5
        expected_rate = 0.5
        expected_product = expected_precision * expected_rate
        assert abs(result.product - expected_product) < 0.01
