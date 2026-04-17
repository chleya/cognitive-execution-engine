import pytest

from cee_core import (
    DomainContext,
    DomainPluginRegistry,
    EventLog,
    PolicyDecision,
    State,
    StatePatch,
    StateTransitionEvent,
)
from cee_core.domain_plugins import DomainPluginPack, DomainRulePack
from cee_core.principles import (
    ActionCost,
    FreeEnergyResult,
    LagrangianCheckResult,
    LeastActionResult,
    SymmetryCheckResult,
    check_domain_substitution_symmetry,
    check_replay_determinism_symmetry,
    check_state_policy_duality,
    compute_action,
    compute_free_energy,
)


def _deny_patch() -> StatePatch:
    return StatePatch(section="policy", key="rules", op="set", value={"x": True})


def _allow_patch() -> StatePatch:
    return StatePatch(section="goals", key="g1", op="set", value="done")


def _core_ctx() -> DomainContext:
    return DomainContext(domain_name="core")


class TestDomainSubstitutionSymmetry:

    def test_deny_is_conserved_across_domains(self):
        patch = _deny_patch()
        ctx = _core_ctx()
        result = check_domain_substitution_symmetry(patch, (ctx,))

        assert result.invariant_holds is True
        assert result.conserved_quantity == "authority_boundary"

    def test_allow_patch_has_no_conservation_requirement(self):
        patch = _allow_patch()
        ctx = _core_ctx()
        result = check_domain_substitution_symmetry(patch, (ctx,))

        assert result.invariant_holds is True
        assert "no conservation requirement" in result.evidence

    def test_symmetry_with_tightening_domain(self):
        pack = DomainPluginPack(
            domain_name="strict_domain",
            rule_packs=(),
            glossary_packs=(),
            evaluators=(),
            connectors=(),
            state_extensions=(),
            denied_patch_sections=("goals",),
            approval_required_patch_sections=(),
        )
        registry = DomainPluginRegistry()
        registry.register(pack)
        ctx = DomainContext(
            domain_name="strict_domain",
            plugin_pack=pack,
        )

        patch = _allow_patch()
        result = check_domain_substitution_symmetry(patch, (ctx,))

        assert result.invariant_holds is True


class TestReplayDeterminismSymmetry:

    def test_empty_log_is_deterministic(self):
        log = EventLog()
        result = check_replay_determinism_symmetry(log)

        assert result.invariant_holds is True
        assert result.conserved_quantity == "replay_determinism"

    def test_populated_log_is_deterministic(self):
        log = EventLog()
        patch = StatePatch(section="goals", key="g1", op="set", value="v1")
        decision = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
        log.append(StateTransitionEvent(
            patch=patch, policy_decision=decision, actor="test", reason="test",
        ))

        result = check_replay_determinism_symmetry(log)

        assert result.invariant_holds is True


class TestLeastAction:

    def test_all_allowed_is_optimal(self):
        events = tuple([
            StateTransitionEvent(
                patch=StatePatch(section="goals", key="g1", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="allow", reason="ok", policy_ref="test"),
                actor="test",
                reason="test",
            )
            for _ in range(3)
        ])

        result = compute_action(events)

        assert result.total_action == 0.0
        assert result.optimal is True
        assert result.average_action == 0.0

    def test_mixed_verdicts_have_positive_action(self):
        events = (
            StateTransitionEvent(
                patch=StatePatch(section="goals", key="g1", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="allow", reason="ok", policy_ref="test"),
                actor="test",
                reason="test",
            ),
            StateTransitionEvent(
                patch=StatePatch(section="self_model", key="k", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="requires_approval", reason="ok", policy_ref="test"),
                actor="test",
                reason="test",
            ),
        )

        result = compute_action(events)

        assert result.total_action == 1.0
        assert result.optimal is False
        assert result.average_action == 0.5

    def test_denied_has_highest_cost(self):
        events = (
            StateTransitionEvent(
                patch=StatePatch(section="policy", key="k", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="deny", reason="no", policy_ref="test"),
                actor="test",
                reason="test",
            ),
        )

        result = compute_action(events)

        assert result.total_action == 10.0
        assert result.optimal is False

    def test_custom_action_cost(self):
        cost = ActionCost(allow_cost=0.0, requires_approval_cost=5.0, deny_cost=50.0)
        events = (
            StateTransitionEvent(
                patch=StatePatch(section="self_model", key="k", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="requires_approval", reason="ok", policy_ref="test"),
                actor="test",
                reason="test",
            ),
        )

        result = compute_action(events, cost=cost)

        assert result.total_action == 5.0

    def test_empty_events_zero_action(self):
        result = compute_action(())

        assert result.total_action == 0.0
        assert result.transition_count == 0


class TestFreeEnergy:

    def test_empty_state_is_stable(self):
        state = State()
        result = compute_free_energy(state, ())

        assert result.stable is True
        assert result.energy == 0.0

    def test_high_confidence_beliefs_are_stable(self):
        state = State(beliefs={"b1": {"confidence": 0.9, "provenance": "source_a"}})
        result = compute_free_energy(state, ())

        assert result.energy == 0.0
        assert result.entropy == 1.0

    def test_low_confidence_beliefs_increase_energy(self):
        state = State(beliefs={"b1": {"confidence": 0.3, "provenance": "source_a"}})
        result = compute_free_energy(state, ())

        assert result.energy == 1.0

    def test_escalation_increases_temperature(self):
        state = State()
        events = (
            StateTransitionEvent(
                patch=StatePatch(section="self_model", key="k", op="set", value="v"),
                policy_decision=PolicyDecision(verdict="requires_approval", reason="ok", policy_ref="test"),
                actor="test",
                reason="test",
            ),
        )

        result = compute_free_energy(state, events)

        assert result.temperature == 1.0

    def test_source_diversity_increases_entropy(self):
        state = State(beliefs={
            "b1": {"confidence": 0.9, "provenance": ("source_a", "source_b")},
            "b2": {"confidence": 0.8, "provenance": ("source_c",)},
        })

        result = compute_free_energy(state, ())

        assert result.entropy >= 3.0


class TestStatePolicyDuality:

    def test_empty_log_satisfies_duality(self):
        log = EventLog()
        result = check_state_policy_duality(log)

        assert result.duality_holds is True
        assert result.reducer_deterministic is True
        assert result.policy_mediated is True

    def test_populated_log_satisfies_duality(self):
        log = EventLog()
        patch = StatePatch(section="goals", key="g1", op="set", value="v1")
        decision = PolicyDecision(verdict="allow", reason="ok", policy_ref="test")
        log.append(StateTransitionEvent(
            patch=patch, policy_decision=decision, actor="test", reason="test",
        ))

        result = check_state_policy_duality(log)

        assert result.duality_holds is True
        assert result.reducer_deterministic is True
        assert result.policy_mediated is True
