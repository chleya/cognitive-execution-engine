"""Tests for Experiment 1: Fact Verification validation framework."""

import pytest

from cee_core.world_state import (
    WorldState,
    add_hypothesis_to_world,
    update_hypothesis_status,
    add_anchor_facts,
)
from cee_core.world_schema import WorldHypothesis

from experiments.experiment1_fact_verification import (
    REALITY,
    CLAIMS_ROUND_1,
    CLAIMS_ROUND_2,
    run_group_a_round1,
    run_group_a_round2,
    run_group_c,
    run_group_c_with_memory,
    measure_repeated_errors,
    judge_experiment,
)


class TestGroupARound1:
    def test_group_a_round1_returns_correct_count(self):
        results, _ = run_group_a_round1(CLAIMS_ROUND_1)
        assert len(results) == len(CLAIMS_ROUND_1)

    def test_group_a_round1_identifies_wrong_claims(self):
        results, _ = run_group_a_round1(CLAIMS_ROUND_1)
        wrong = [r for r in results if not r["is_correct"]]
        assert len(wrong) == 3

    def test_group_a_round1_verification_matches_reality(self):
        results, _ = run_group_a_round1(CLAIMS_ROUND_1)
        for r in results:
            assert r["verified"] == (r["claimed"] == r["actual"])

    def test_group_a_round1_stores_actual_values_in_beliefs(self):
        _, beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        for topic, _, _ in CLAIMS_ROUND_1:
            assert beliefs[f"actual_{topic}"] == REALITY[topic]


class TestGroupARound2:
    def test_group_a_round2_accepts_all_claims(self):
        _, beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        r2_results, _ = run_group_a_round2(CLAIMS_ROUND_2, beliefs)
        for r in r2_results:
            assert r["accepted"] is True

    def test_group_a_round2_accepts_all_wrong_claims(self):
        _, beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        r2_results, _ = run_group_a_round2(CLAIMS_ROUND_2, beliefs)
        accepted_wrong = [r for r in r2_results if r.get("accepted_wrong_claim")]
        assert len(accepted_wrong) == 5

    def test_group_a_round2_does_not_use_memory(self):
        _, beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        r2_results, _ = run_group_a_round2(CLAIMS_ROUND_2, beliefs)
        for r in r2_results:
            assert "used_anchored_fact" not in r


class TestGroupCRound1:
    def test_group_c_round1_returns_correct_count(self):
        results, _ = run_group_c(CLAIMS_ROUND_1)
        assert len(results) == len(CLAIMS_ROUND_1)

    def test_group_c_round1_creates_hypotheses(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        assert len(state.hypotheses) == len(CLAIMS_ROUND_1)

    def test_group_c_round1_creates_anchored_facts(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        assert len(state.anchored_fact_summaries) == len(CLAIMS_ROUND_1)

    def test_group_c_round1_wrong_hypotheses_rejected_after_verification(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        wrong_claims = [c for c in CLAIMS_ROUND_1 if not c[2]]
        rejected = state.rejected_hypotheses()
        assert len(rejected) == len(wrong_claims)

    def test_group_c_round1_confirms_correct_hypotheses(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        correct_claims = [c for c in CLAIMS_ROUND_1 if c[2]]
        confirmed_ids = {h.hypothesis_id for h in state.hypotheses if h.status == "active"}
        for topic, _, _ in correct_claims:
            assert f"hyp-{topic}" in confirmed_ids


class TestGroupCRound2WithMemory:
    def test_group_c_round2_uses_anchored_facts_for_repeated_claims(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        r2_results, _ = run_group_c_with_memory(CLAIMS_ROUND_2, state)
        used_memory = [r for r in r2_results if r.get("used_anchored_fact")]
        repeated_topics = {c[0] for c in CLAIMS_ROUND_2 if c[0] in {r[0] for r in CLAIMS_ROUND_1}}
        assert len(used_memory) == len(repeated_topics)

    def test_group_c_round2_reduces_repeated_errors_vs_group_a(self):
        a_r1, a_beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        a_r2, _ = run_group_a_round2(CLAIMS_ROUND_2, a_beliefs)
        c_r1, c_state = run_group_c(CLAIMS_ROUND_1)
        c_r2, _ = run_group_c_with_memory(CLAIMS_ROUND_2, c_state)

        a_repeated = sum(1 for r in a_r2 if r.get("accepted_wrong_claim"))
        c_repeated = sum(1 for r in c_r2 if r.get("accepted_wrong_claim"))
        assert c_repeated < a_repeated

    def test_group_c_round2_anchored_facts_have_correct_provenance(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        _, state = run_group_c_with_memory(CLAIMS_ROUND_2, state)
        for s in state.anchored_fact_summaries:
            assert isinstance(s, str)
            assert " = " in s

    def test_group_c_round2_rejects_known_wrong_claims(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        r2_results, _ = run_group_c_with_memory(CLAIMS_ROUND_2, state)
        for r in r2_results:
            if r.get("used_anchored_fact"):
                assert r["accepted"] is False

    def test_group_c_round2_accepts_new_wrong_claims_without_anchored_fact(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        r2_results, _ = run_group_c_with_memory(CLAIMS_ROUND_2, state)
        new_wrong = [r for r in r2_results if not r.get("used_anchored_fact") and not r["is_correct"]]
        for r in new_wrong:
            assert r["accepted"] is True


class TestAnchoredFactsCreation:
    def test_anchored_facts_contain_correct_values(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        for s in state.anchored_fact_summaries:
            topic_part = s.split(" = ")[0]
            value_part = int(s.split(" = ")[1])
            assert REALITY[topic_part] == value_part

    def test_anchored_facts_cover_all_topics(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        anchored_topics = set()
        for s in state.anchored_fact_summaries:
            topic = s.split(" = ")[0]
            anchored_topics.add(topic)
        for topic, _, _ in CLAIMS_ROUND_1:
            assert topic in anchored_topics


class TestRejectedHypothesesTracking:
    def test_rejected_hypotheses_have_zero_confidence(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        rejected = state.rejected_hypotheses()
        for h in rejected:
            assert h.confidence == 0.0

    def test_rejected_hypotheses_statements_match_claims(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        rejected = state.rejected_hypotheses()
        wrong_claims = [c for c in CLAIMS_ROUND_1 if not c[2]]
        rejected_statements = {h.statement for h in rejected}
        for topic, value, _ in wrong_claims:
            assert f"{topic} = {value}" in rejected_statements


class TestExplainability:
    def test_can_identify_which_hypothesis_was_rejected(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        rejected = state.rejected_hypotheses()
        for h in rejected:
            assert h.hypothesis_id
            assert h.statement
            assert h.status == "rejected"

    def test_can_trace_fact_to_provenance(self):
        _, state = run_group_c(CLAIMS_ROUND_1)
        assert len(state.anchored_fact_summaries) > 0
        for s in state.anchored_fact_summaries:
            assert " = " in s


class TestGoStopJudgment:
    def test_judge_returns_go_when_c_eliminates_all_repeated(self):
        verdict = judge_experiment(a_repeated=3, c_repeated=0)
        assert "GO" in verdict

    def test_judge_returns_go_when_reduction_above_20_percent(self):
        verdict = judge_experiment(a_repeated=5, c_repeated=3)
        assert "GO" in verdict

    def test_judge_returns_stop_when_no_significant_reduction(self):
        verdict = judge_experiment(a_repeated=5, c_repeated=5)
        assert "STOP" in verdict

    def test_judge_returns_stop_when_reduction_below_20_percent(self):
        verdict = judge_experiment(a_repeated=10, c_repeated=9)
        assert "STOP" in verdict

    def test_full_experiment_judgment(self):
        a_r1, a_beliefs = run_group_a_round1(CLAIMS_ROUND_1)
        a_r2, _ = run_group_a_round2(CLAIMS_ROUND_2, a_beliefs)
        c_r1, c_state = run_group_c(CLAIMS_ROUND_1)
        c_r2, _ = run_group_c_with_memory(CLAIMS_ROUND_2, c_state)

        a_repeated, _ = measure_repeated_errors(a_r1, a_r2)
        c_repeated, _ = measure_repeated_errors(c_r1, c_r2)
        verdict = judge_experiment(a_repeated, c_repeated)
        assert "GO" in verdict


class TestMeasureRepeatedErrors:
    def test_measure_repeated_errors_finds_overlap(self):
        r1 = [
            {"topic": "a", "is_correct": False, "verified": False},
            {"topic": "b", "is_correct": True, "verified": True},
        ]
        r2 = [
            {"topic": "a", "is_correct": False, "accepted_wrong_claim": True},
            {"topic": "c", "is_correct": False, "accepted_wrong_claim": True},
        ]
        repeated, total_r1 = measure_repeated_errors(r1, r2)
        assert repeated == 1
        assert total_r1 == 1

    def test_measure_repeated_errors_no_overlap(self):
        r1 = [
            {"topic": "a", "is_correct": False, "verified": False},
        ]
        r2 = [
            {"topic": "b", "is_correct": False, "accepted_wrong_claim": True},
        ]
        repeated, total_r1 = measure_repeated_errors(r1, r2)
        assert repeated == 0
        assert total_r1 == 1
