"""Comprehensive tests for the 5 new world-model modules:
- reality_interface
- commitment_policy
- revision_policy
- simulation
- hypothesis_engine
"""

import pytest

from cee_core.commitment import CommitmentEvent, CommitmentKind, Reversibility
from cee_core.reality_interface import (
    DefaultRealityInterface,
    RealityContactResult,
    REALITY_INTERFACE_SCHEMA_VERSION,
    execute_commitment,
)
from cee_core.commitment_policy import (
    CommitmentPolicyDecision,
    DefaultCommitmentPolicy,
    evaluate_commitment_policy,
    COMMITMENT_POLICY_SCHEMA_VERSION,
)
from cee_core.revision_policy import (
    RevisionPolicyDecision,
    DefaultRevisionPolicy,
    evaluate_revision_policy,
    REVISION_POLICY_SCHEMA_VERSION,
)
from cee_core.simulation import (
    SimulationResult,
    simulate_hypothesis,
    simulate_action,
    mark_simulated,
)
from cee_core.hypothesis_engine import (
    HypothesisCandidate,
    generate_from_tension,
    generate_from_conflict,
    rank_hypotheses,
)
from cee_core.world_schema import (
    WorldEntity,
    WorldRelation,
    WorldHypothesis,
    RevisionDelta,
)
from cee_core.world_state import (
    WorldState,
    add_entity,
    add_relation,
    add_hypothesis_to_world,
    add_anchor_facts,
    add_tension,
)
from cee_core.tools import ToolRegistry, ToolSpec


def _make_state(**overrides) -> WorldState:
    defaults = dict(
        state_id="ws_0",
    )
    defaults.update(overrides)
    return WorldState(**defaults)


def _make_commitment(kind: CommitmentKind = "observe", **overrides) -> CommitmentEvent:
    defaults = dict(
        event_id="evt_1",
        source_state_id="ws_0",
        commitment_kind=kind,
        intent_summary="test intent",
    )
    defaults.update(overrides)
    return CommitmentEvent(**defaults)


def _ok_reality_fn(commitment: CommitmentEvent) -> str:
    return "observed ok"


def _fail_reality_fn(commitment: CommitmentEvent) -> str:
    raise RuntimeError("reality failure")


# ============================================================
# 1. RealityInterface tests
# ============================================================


class TestRealityInterfaceProtocol:
    def test_default_interface_has_observe(self):
        iface = DefaultRealityInterface()
        assert hasattr(iface, "observe")
        assert callable(iface.observe)

    def test_default_interface_has_act(self):
        iface = DefaultRealityInterface()
        assert hasattr(iface, "act")
        assert callable(iface.act)

    def test_default_interface_has_tool_contact(self):
        iface = DefaultRealityInterface()
        assert hasattr(iface, "tool_contact")
        assert callable(iface.tool_contact)


class TestDefaultRealityInterfaceObserve:
    def test_observe_success(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="observe")
        result = iface.observe(commitment, _ok_reality_fn)
        assert result.success is True
        assert result.external_result_summary == "observed ok"
        assert result.observation_summaries == ("observed ok",)

    def test_observe_wrong_kind_raises(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="act")
        with pytest.raises(ValueError, match="observe called with commitment_kind"):
            iface.observe(commitment, _ok_reality_fn)

    def test_observe_error_handling(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="observe")
        result = iface.observe(commitment, _fail_reality_fn)
        assert result.success is False
        assert "observation failed" in result.external_result_summary
        assert "reality failure" in result.external_result_summary


class TestDefaultRealityInterfaceAct:
    def test_act_success(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="act")
        result = iface.act(commitment, _ok_reality_fn)
        assert result.success is True
        assert result.external_result_summary == "observed ok"

    def test_act_wrong_kind_raises(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="observe")
        with pytest.raises(ValueError, match="act called with commitment_kind"):
            iface.act(commitment, _ok_reality_fn)

    def test_act_error_handling(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="act")
        result = iface.act(commitment, _fail_reality_fn)
        assert result.success is False
        assert "action failed" in result.external_result_summary


class TestDefaultRealityInterfaceToolContact:
    def test_tool_contact_success(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="reader", description="reads", risk="read"))
        iface = DefaultRealityInterface(registry=registry)
        commitment = _make_commitment(kind="tool_contact", action_summary="reader")
        result = iface.tool_contact(commitment, _ok_reality_fn)
        assert result.success is True
        assert result.observation_summaries == ("observed ok",)

    def test_tool_contact_unknown_tool_fails(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="tool_contact", action_summary="nonexistent")
        result = iface.tool_contact(commitment, _ok_reality_fn)
        assert result.success is False
        assert "unknown tool" in result.external_result_summary

    def test_tool_contact_wrong_kind_raises(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="observe")
        with pytest.raises(ValueError, match="tool_contact called with commitment_kind"):
            iface.tool_contact(commitment, _ok_reality_fn)

    def test_tool_contact_error_handling(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="reader", description="reads", risk="read"))
        iface = DefaultRealityInterface(registry=registry)
        commitment = _make_commitment(kind="tool_contact", action_summary="reader")
        result = iface.tool_contact(commitment, _fail_reality_fn)
        assert result.success is False
        assert "tool contact failed" in result.external_result_summary

    def test_tool_contact_no_action_summary_succeeds(self):
        iface = DefaultRealityInterface()
        commitment = _make_commitment(kind="tool_contact", action_summary="")
        result = iface.tool_contact(commitment, _ok_reality_fn)
        assert result.success is True


class TestExecuteCommitment:
    def test_dispatches_observe(self):
        commitment = _make_commitment(kind="observe")
        result = execute_commitment(commitment, _ok_reality_fn)
        assert result.success is True
        assert result.observation_summaries == ("observed ok",)

    def test_dispatches_act(self):
        commitment = _make_commitment(kind="act")
        result = execute_commitment(commitment, _ok_reality_fn)
        assert result.success is True

    def test_dispatches_tool_contact(self):
        commitment = _make_commitment(kind="tool_contact")
        result = execute_commitment(commitment, _ok_reality_fn)
        assert result.success is True

    def test_unsupported_kind_raises(self):
        commitment = _make_commitment(kind="internal_commit")
        with pytest.raises(ValueError, match="unsupported commitment_kind"):
            execute_commitment(commitment, _ok_reality_fn)

    def test_uses_default_interface_when_none(self):
        commitment = _make_commitment(kind="observe")
        result = execute_commitment(commitment, _ok_reality_fn, interface=None)
        assert result.success is True

    def test_custom_interface(self):
        class CustomInterface:
            def observe(self, commitment, reality_fn):
                return CommitmentEvent(
                    event_id=commitment.event_id,
                    source_state_id=commitment.source_state_id,
                    commitment_kind="observe",
                    intent_summary="custom",
                    success=True,
                )

            def act(self, commitment, reality_fn):
                return commitment

            def tool_contact(self, commitment, reality_fn):
                return commitment

        commitment = _make_commitment(kind="observe")
        result = execute_commitment(commitment, _ok_reality_fn, interface=CustomInterface())
        assert result.intent_summary == "custom"


class TestRealityContactResult:
    def test_creation(self):
        r = RealityContactResult(
            commitment_event_id="evt_1",
            commitment_kind="observe",
            success=True,
            result_summary="ok",
        )
        assert r.commitment_event_id == "evt_1"
        assert r.commitment_kind == "observe"
        assert r.success is True
        assert r.result_summary == "ok"
        assert r.observation_summaries == ()
        assert r.risk_realized == 0.0
        assert r.cost == 0.0

    def test_to_dict(self):
        r = RealityContactResult(
            commitment_event_id="evt_1",
            commitment_kind="observe",
            success=True,
            result_summary="ok",
            observation_summaries=("a", "b"),
            risk_realized=0.3,
            cost=1.5,
        )
        d = r.to_dict()
        assert d["schema_version"] == REALITY_INTERFACE_SCHEMA_VERSION
        assert d["commitment_event_id"] == "evt_1"
        assert d["commitment_kind"] == "observe"
        assert d["success"] is True
        assert d["result_summary"] == "ok"
        assert d["observation_summaries"] == ["a", "b"]
        assert d["risk_realized"] == 0.3
        assert d["cost"] == 1.5

    def test_from_dict_roundtrip(self):
        r = RealityContactResult(
            commitment_event_id="evt_2",
            commitment_kind="act",
            success=False,
            result_summary="failed",
            observation_summaries=("x",),
            risk_realized=0.5,
            cost=2.0,
        )
        d = r.to_dict()
        restored = RealityContactResult.from_dict(d)
        assert restored.commitment_event_id == r.commitment_event_id
        assert restored.commitment_kind == r.commitment_kind
        assert restored.success == r.success
        assert restored.result_summary == r.result_summary
        assert restored.observation_summaries == r.observation_summaries
        assert restored.risk_realized == r.risk_realized
        assert restored.cost == r.cost

    def test_from_dict_missing_schema_raises(self):
        with pytest.raises(ValueError, match="schema_version"):
            RealityContactResult.from_dict({"commitment_event_id": "x"})


# ============================================================
# 2. CommitmentPolicy tests
# ============================================================


class TestCommitmentPolicyDecision:
    def test_creation(self):
        d = CommitmentPolicyDecision(
            allowed=True,
            reason="ok",
            requires_approval=False,
        )
        assert d.allowed is True
        assert d.reason == "ok"
        assert d.requires_approval is False

    def test_to_dict(self):
        d = CommitmentPolicyDecision(
            allowed=False,
            reason="unsafe",
            requires_approval=True,
        )
        result = d.to_dict()
        assert result["schema_version"] == COMMITMENT_POLICY_SCHEMA_VERSION
        assert result["allowed"] is False
        assert result["reason"] == "unsafe"
        assert result["requires_approval"] is True

    def test_from_dict_roundtrip(self):
        d = CommitmentPolicyDecision(
            allowed=True,
            reason="safe",
            requires_approval=False,
        )
        restored = CommitmentPolicyDecision.from_dict(d.to_dict())
        assert restored.allowed == d.allowed
        assert restored.reason == d.reason
        assert restored.requires_approval == d.requires_approval


class TestDefaultCommitmentPolicy:
    def setup_method(self):
        self.policy = DefaultCommitmentPolicy()

    def test_observe_allowed(self):
        decision = self.policy.evaluate("observe")
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_act_reversible_allowed(self):
        decision = self.policy.evaluate("act", reversibility="reversible")
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_act_partially_reversible_allowed(self):
        decision = self.policy.evaluate("act", reversibility="partially_reversible")
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_act_irreversible_requires_approval(self):
        decision = self.policy.evaluate("act", reversibility="irreversible")
        assert decision.allowed is False
        assert decision.requires_approval is True
        assert "irreversible" in decision.reason

    def test_act_no_reversibility_requires_approval(self):
        decision = self.policy.evaluate("act", reversibility=None)
        assert decision.allowed is False
        assert decision.requires_approval is True

    def test_tool_contact_allowed(self):
        decision = self.policy.evaluate("tool_contact")
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_internal_commit_allowed(self):
        decision = self.policy.evaluate("internal_commit")
        assert decision.allowed is True
        assert decision.requires_approval is False

    def test_unknown_kind_rejected(self):
        decision = self.policy.evaluate("unknown_kind")
        assert decision.allowed is False
        assert decision.requires_approval is True


class TestEvaluateCommitmentPolicy:
    def test_uses_default_policy_when_none(self):
        decision = evaluate_commitment_policy("observe")
        assert decision.allowed is True

    def test_uses_custom_policy(self):
        class AlwaysDeny:
            def evaluate(self, commitment_kind, reversibility=None):
                return CommitmentPolicyDecision(
                    allowed=False,
                    reason="denied",
                    requires_approval=True,
                )

        decision = evaluate_commitment_policy("observe", policy=AlwaysDeny())
        assert decision.allowed is False

    def test_act_irreversible_via_function(self):
        decision = evaluate_commitment_policy("act", reversibility="irreversible")
        assert decision.allowed is False
        assert decision.requires_approval is True


# ============================================================
# 3. RevisionPolicy tests
# ============================================================


def _make_delta(
    delta_id: str = "d1",
    target_kind: str = "entity_add",
    target_ref: str = "e1",
    before_summary: str = "",
    after_summary: str = "new entity",
    justification: str = "observed in reality",
) -> RevisionDelta:
    return RevisionDelta(
        delta_id=delta_id,
        target_kind=target_kind,
        target_ref=target_ref,
        before_summary=before_summary,
        after_summary=after_summary,
        justification=justification,
    )


class TestRevisionPolicyDecision:
    def test_creation(self):
        d = RevisionPolicyDecision(
            allowed=True,
            reason="ok",
            violated_rules=(),
        )
        assert d.allowed is True
        assert d.reason == "ok"
        assert d.violated_rules == ()

    def test_creation_with_violations(self):
        d = RevisionPolicyDecision(
            allowed=False,
            reason="violated",
            violated_rules=("rule1", "rule2"),
        )
        assert d.violated_rules == ("rule1", "rule2")

    def test_to_dict(self):
        d = RevisionPolicyDecision(
            allowed=False,
            reason="violated",
            violated_rules=("rule_a",),
        )
        result = d.to_dict()
        assert result["schema_version"] == REVISION_POLICY_SCHEMA_VERSION
        assert result["allowed"] is False
        assert result["violated_rules"] == ["rule_a"]

    def test_from_dict_roundtrip(self):
        d = RevisionPolicyDecision(
            allowed=True,
            reason="satisfied",
            violated_rules=(),
        )
        restored = RevisionPolicyDecision.from_dict(d.to_dict())
        assert restored.allowed == d.allowed
        assert restored.reason == d.reason
        assert restored.violated_rules == d.violated_rules


class TestDefaultRevisionPolicy:
    def setup_method(self):
        self.policy = DefaultRevisionPolicy()
        self.state = _make_state()

    def test_valid_revision_allowed(self):
        deltas = (_make_delta(),)
        decision = self.policy.evaluate(deltas, self.state, "confirmation")
        assert decision.allowed is True
        assert decision.violated_rules == ()

    def test_empty_justification_rejected(self):
        deltas = (_make_delta(justification="   "),)
        decision = self.policy.evaluate(deltas, self.state, "confirmation")
        assert decision.allowed is False
        assert any("empty_justification" in r for r in decision.violated_rules)

    def test_anchor_modification_rejected(self):
        state = _make_state(anchored_fact_summaries=("gravity exists",))
        deltas = (
            _make_delta(
                target_kind="anchor_add",
                after_summary="gravity exists",
            ),
        )
        decision = self.policy.evaluate(deltas, state, "confirmation")
        assert decision.allowed is False
        assert any("anchor_already_exists" in r for r in decision.violated_rules)

    def test_disallowed_revision_kind(self):
        deltas = (_make_delta(),)
        decision = self.policy.evaluate(deltas, self.state, "invalid_kind")
        assert decision.allowed is False
        assert any("revision_kind_not_allowed" in r for r in decision.violated_rules)

    def test_multiple_violations(self):
        state = _make_state(anchored_fact_summaries=("gravity exists",))
        deltas = (
            _make_delta(
                target_kind="anchor_add",
                after_summary="gravity exists",
                justification="   ",
            ),
        )
        decision = self.policy.evaluate(deltas, state, "invalid_kind")
        assert decision.allowed is False
        assert len(decision.violated_rules) >= 2

    def test_anchor_add_new_fact_allowed(self):
        deltas = (
            _make_delta(
                target_kind="anchor_add",
                after_summary="new fact not yet anchored",
            ),
        )
        decision = self.policy.evaluate(deltas, self.state, "confirmation")
        assert decision.allowed is True


class TestEvaluateRevisionPolicy:
    def test_uses_default_policy_when_none(self):
        state = _make_state()
        deltas = (_make_delta(),)
        decision = evaluate_revision_policy(deltas, state, "confirmation")
        assert decision.allowed is True

    def test_uses_custom_policy(self):
        class AlwaysDeny:
            def evaluate(self, deltas, state, revision_kind):
                return RevisionPolicyDecision(
                    allowed=False,
                    reason="custom deny",
                    violated_rules=("custom_rule",),
                )

        state = _make_state()
        deltas = (_make_delta(),)
        decision = evaluate_revision_policy(
            deltas, state, "confirmation", policy=AlwaysDeny()
        )
        assert decision.allowed is False


# ============================================================
# 4. Simulation tests
# ============================================================


class TestSimulationResult:
    def test_creation(self):
        state = _make_state()
        r = SimulationResult(
            simulated_state=state,
            confidence=0.8,
            assumptions=("a1", "a2"),
        )
        assert r.confidence == 0.8
        assert r.assumptions == ("a1", "a2")
        assert r.is_simulated is True

    def test_creation_is_simulated_default(self):
        state = _make_state()
        r = SimulationResult(
            simulated_state=state,
            confidence=0.5,
            assumptions=(),
        )
        assert r.is_simulated is True


class TestSimulateHypothesis:
    def test_hypothesis_promoted_to_active(self):
        state = _make_state()
        hyp = WorldHypothesis(
            hypothesis_id="h1",
            statement="the sky is blue",
            status="tentative",
            confidence=0.7,
        )
        result = simulate_hypothesis(state, hyp)
        found = result.simulated_state.find_hypothesis("h1")
        assert found is not None
        assert found.status == "active"

    def test_conflict_with_anchored_fact_reduces_confidence(self):
        state = _make_state(anchored_fact_summaries=("the sky",))
        hyp = WorldHypothesis(
            hypothesis_id="h2",
            statement="the sky is blue",
            status="tentative",
            confidence=0.9,
        )
        result = simulate_hypothesis(state, hyp)
        assert result.confidence == 0.1

    def test_no_conflict_preserves_confidence(self):
        state = _make_state()
        hyp = WorldHypothesis(
            hypothesis_id="h3",
            statement="the sky is green",
            confidence=0.6,
        )
        result = simulate_hypothesis(state, hyp)
        assert result.confidence == 0.6

    def test_existing_hypothesis_updated(self):
        hyp = WorldHypothesis(
            hypothesis_id="h4",
            statement="test",
            status="tentative",
            confidence=0.4,
        )
        state = add_hypothesis_to_world(_make_state(), hyp)
        new_hyp = WorldHypothesis(
            hypothesis_id="h4",
            statement="test",
            confidence=0.8,
        )
        result = simulate_hypothesis(state, new_hyp)
        found = result.simulated_state.find_hypothesis("h4")
        assert found.status == "active"
        assert found.confidence == 0.8

    def test_related_entities_updated(self):
        entity = WorldEntity(entity_id="e1", kind="thing", summary="a thing")
        state = add_entity(_make_state(), entity)
        hyp = WorldHypothesis(
            hypothesis_id="h5",
            statement="test",
            confidence=0.7,
            related_entity_ids=("e1",),
        )
        result = simulate_hypothesis(state, hyp)
        updated_entity = result.simulated_state.find_entity("e1")
        assert updated_entity is not None
        assert updated_entity.confidence == 0.7

    def test_assumptions_contain_statement(self):
        hyp = WorldHypothesis(
            hypothesis_id="h6",
            statement="gravity pulls down",
            confidence=0.5,
        )
        result = simulate_hypothesis(_make_state(), hyp)
        assert "gravity pulls down" in result.assumptions


class TestSimulateAction:
    def test_adds_expected_changes_as_hypotheses(self):
        state = _make_state()
        result = simulate_action(
            state,
            action_summary="open door",
            expected_changes=("door is open", "room is accessible"),
        )
        assert result.simulated_state.find_hypothesis("sim_action_0") is not None
        assert result.simulated_state.find_hypothesis("sim_action_1") is not None

    def test_hypotheses_are_tentative(self):
        state = _make_state()
        result = simulate_action(
            state,
            action_summary="open door",
            expected_changes=("door is open",),
        )
        h = result.simulated_state.find_hypothesis("sim_action_0")
        assert h.status == "tentative"
        assert h.confidence == 0.5

    def test_confidence_is_0_5(self):
        state = _make_state()
        result = simulate_action(
            state,
            action_summary="act",
            expected_changes=("change1",),
        )
        assert result.confidence == 0.5

    def test_assumptions_include_action_and_changes(self):
        state = _make_state()
        result = simulate_action(
            state,
            action_summary="open door",
            expected_changes=("door is open", "room accessible"),
        )
        assert "open door" in result.assumptions
        assert "door is open" in result.assumptions
        assert "room accessible" in result.assumptions

    def test_no_changes_still_produces_result(self):
        state = _make_state()
        result = simulate_action(state, action_summary="noop", expected_changes=())
        assert result.confidence == 0.5
        assert len(result.simulated_state.hypotheses) == 0


class TestMarkSimulated:
    def test_adds_is_simulated_provenance(self):
        state = _make_state()
        marked = mark_simulated(state)
        assert "is_simulated" in marked.provenance_refs

    def test_preserves_existing_provenance(self):
        state = _make_state(provenance_refs=("existing_ref",))
        marked = mark_simulated(state)
        assert "existing_ref" in marked.provenance_refs
        assert "is_simulated" in marked.provenance_refs


# ============================================================
# 5. HypothesisEngine tests
# ============================================================


class TestHypothesisCandidate:
    def test_creation(self):
        c = HypothesisCandidate(
            candidate_id="hc_1",
            statement="test statement",
            source_tension="tension A",
            source_conflict="",
            confidence=0.6,
            related_entity_ids=("e1",),
        )
        assert c.candidate_id == "hc_1"
        assert c.statement == "test statement"
        assert c.source_tension == "tension A"
        assert c.source_conflict == ""
        assert c.confidence == 0.6
        assert c.related_entity_ids == ("e1",)

    def test_default_confidence(self):
        c = HypothesisCandidate(
            candidate_id="hc_2",
            statement="test",
            source_tension="",
            source_conflict="",
        )
        assert c.confidence == 0.5


class TestGenerateFromTension:
    def test_generates_from_active_tensions(self):
        state = _make_state(active_tensions=("resource conflict", "goal ambiguity"))
        candidates = generate_from_tension(state)
        assert len(candidates) == 2
        assert all(c.source_tension != "" for c in candidates)
        assert all("resource conflict" in c.statement or "goal ambiguity" in c.statement for c in candidates)

    def test_no_tensions_produces_empty(self):
        state = _make_state()
        candidates = generate_from_tension(state)
        assert candidates == []

    def test_extracts_entity_ids_from_text(self):
        entity = WorldEntity(entity_id="server_A", kind="host", summary="a server")
        state = add_entity(_make_state(active_tensions=("server_A is overloaded",)), entity)
        candidates = generate_from_tension(state)
        assert len(candidates) == 1
        assert "server_A" in candidates[0].related_entity_ids

    def test_candidate_ids_prefixed(self):
        state = _make_state(active_tensions=("t1",))
        candidates = generate_from_tension(state)
        assert candidates[0].candidate_id.startswith("hc_t_")


class TestGenerateFromConflict:
    def test_generates_from_conflicting_hypotheses(self):
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="door is open",
            related_entity_ids=("door",),
            status="active",
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="door is closed",
            related_entity_ids=("door",),
            status="active",
        )
        state = add_hypothesis_to_world(
            add_hypothesis_to_world(_make_state(), h1), h2
        )
        candidates = generate_from_conflict(state)
        assert len(candidates) >= 1
        assert any(c.source_conflict != "" for c in candidates)

    def test_no_conflict_produces_empty(self):
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="a",
            related_entity_ids=("e1",),
            status="active",
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="b",
            related_entity_ids=("e2",),
            status="active",
        )
        state = add_hypothesis_to_world(
            add_hypothesis_to_world(_make_state(), h1), h2
        )
        candidates = generate_from_conflict(state)
        assert candidates == []

    def test_same_statement_no_conflict(self):
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="same",
            related_entity_ids=("e1",),
            status="active",
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="same",
            related_entity_ids=("e1",),
            status="active",
        )
        state = add_hypothesis_to_world(
            add_hypothesis_to_world(_make_state(), h1), h2
        )
        candidates = generate_from_conflict(state)
        assert candidates == []

    def test_candidate_ids_prefixed(self):
        h1 = WorldHypothesis(
            hypothesis_id="h1",
            statement="x",
            related_entity_ids=("e1",),
            status="active",
        )
        h2 = WorldHypothesis(
            hypothesis_id="h2",
            statement="y",
            related_entity_ids=("e1",),
            status="active",
        )
        state = add_hypothesis_to_world(
            add_hypothesis_to_world(_make_state(), h1), h2
        )
        candidates = generate_from_conflict(state)
        assert all(c.candidate_id.startswith("hc_c_") for c in candidates)


class TestRankHypotheses:
    def test_sorts_by_confidence_descending(self):
        candidates = [
            HypothesisCandidate(
                candidate_id="hc1",
                statement="low",
                source_tension="",
                source_conflict="",
                confidence=0.3,
            ),
            HypothesisCandidate(
                candidate_id="hc2",
                statement="high",
                source_tension="",
                source_conflict="",
                confidence=0.9,
            ),
            HypothesisCandidate(
                candidate_id="hc3",
                statement="mid",
                source_tension="",
                source_conflict="",
                confidence=0.6,
            ),
        ]
        state = _make_state()
        ranked = rank_hypotheses(candidates, state)
        assert ranked[0].candidate_id == "hc2"
        assert ranked[1].candidate_id == "hc3"
        assert ranked[2].candidate_id == "hc1"

    def test_boosts_by_relations(self):
        entity = WorldEntity(entity_id="e1", kind="thing", summary="a thing")
        rel = WorldRelation(
            relation_id="r1",
            subject_id="e1",
            predicate="relates",
            object_id="e2",
        )
        state = add_relation(add_entity(_make_state(), entity), rel)

        c_with_rel = HypothesisCandidate(
            candidate_id="hc_rel",
            statement="test",
            source_tension="",
            source_conflict="",
            confidence=0.5,
            related_entity_ids=("e1",),
        )
        c_without_rel = HypothesisCandidate(
            candidate_id="hc_no_rel",
            statement="test",
            source_tension="",
            source_conflict="",
            confidence=0.5,
            related_entity_ids=(),
        )
        ranked = rank_hypotheses([c_without_rel, c_with_rel], state)
        assert ranked[0].candidate_id == "hc_rel"
        assert ranked[0].confidence > ranked[1].confidence

    def test_penalizes_anchor_conflicts(self):
        state = _make_state(anchored_fact_summaries=("the sky",))

        c_conflict = HypothesisCandidate(
            candidate_id="hc_conflict",
            statement="the sky is not blue",
            source_tension="",
            source_conflict="",
            confidence=0.7,
        )
        c_safe = HypothesisCandidate(
            candidate_id="hc_safe",
            statement="the sky is blue",
            source_tension="",
            source_conflict="",
            confidence=0.7,
        )
        ranked = rank_hypotheses([c_conflict, c_safe], state)
        assert ranked[0].candidate_id == "hc_safe"
        assert ranked[0].confidence > ranked[1].confidence

    def test_confidence_clamped_to_0_1(self):
        c = HypothesisCandidate(
            candidate_id="hc_high",
            statement="test",
            source_tension="",
            source_conflict="",
            confidence=0.99,
            related_entity_ids=("e1",),
        )
        entity = WorldEntity(entity_id="e1", kind="thing", summary="a thing")
        rels = tuple(
            WorldRelation(
                relation_id=f"r{i}",
                subject_id="e1",
                predicate="rel",
                object_id=f"other_{i}",
            )
            for i in range(20)
        )
        state = WorldState(state_id="ws_0", entities=(entity,), relations=rels)
        ranked = rank_hypotheses([c], state)
        assert ranked[0].confidence <= 1.0

    def test_empty_candidates_returns_empty(self):
        state = _make_state()
        ranked = rank_hypotheses([], state)
        assert ranked == []
