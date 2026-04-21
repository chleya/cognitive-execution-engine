"""Tests for Experiment 2: WorldState vs flat state + layered memory."""

import pytest

from experiments.experiment2_worldstate_vs_memory import (
    ROUND1_REPORTS,
    ROUND2_REPORTS,
    ROUND3_QUESTIONS,
    PROJECT_REALITY,
    LettaCoreMemory,
    LettaArchivalMemory,
    LettaState,
    LangGraphState,
    measure_confusion_rate,
    measure_drift_rate,
    measure_maintenance_cost,
    measure_readability,
    run_group_a,
    run_group_b,
    run_group_c,
    evaluate_go_stop,
)


class TestLettaState:
    def test_core_memory(self):
        cm = LettaCoreMemory()
        cm.write("alpha_status=on_track")
        cm.write("beta_status=on_track")
        assert len(cm.read()) == 2
        assert "alpha_status=on_track" in cm.read()

    def test_archival_memory(self):
        am = LettaArchivalMemory()
        am.store({"key": "alpha_status", "value": "on_track"})
        am.store({"key": "beta_status", "value": "on_track"})
        results = am.search("alpha")
        assert len(results) == 1


class TestLangGraphState:
    def test_checkpoint(self):
        gs = LangGraphState()
        gs.graph_state["alpha_status"] = {"value": "on_track"}
        gs.save_checkpoint("round1")
        assert len(gs.checkpoints) == 1
        cp = gs.latest_checkpoint()
        assert cp.state_snapshot["alpha_status"]["value"] == "on_track"


class TestGroupA:
    def test_run_returns_results(self):
        result = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["group"] == "A (Letta-style)"
        assert "fact_hypothesis_confusion_rate" in result
        assert len(result["answers"]) == len(ROUND3_QUESTIONS)

    def test_delta_status_confusion(self):
        result = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        delta_answer = [a for a in result["answers"] if "delta" in a["question"] and "status" in a["question"]][0]
        assert delta_answer["confused"] is True

    def test_alpha_status_correct_after_update(self):
        result = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        alpha_answer = [a for a in result["answers"] if "alpha" in a["question"] and "status" in a["question"]][0]
        assert alpha_answer["correct"] is True

    def test_gamma_status_correct_after_update(self):
        result = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        gamma_answer = [a for a in result["answers"] if "gamma" in a["question"]][0]
        assert gamma_answer["correct"] is True


class TestGroupB:
    def test_run_returns_results(self):
        result = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["group"] == "B (LangGraph-style)"
        assert "fact_hypothesis_confusion_rate" in result

    def test_delta_status_confusion(self):
        result = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        delta_answer = [a for a in result["answers"] if "delta" in a["question"] and "status" in a["question"]][0]
        assert delta_answer["confused"] is True


class TestGroupC:
    def test_run_returns_results(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["group"] == "C (WorldState)"
        assert "fact_hypothesis_confusion_rate" in result
        assert result["anchored_facts_count"] > 0

    def test_no_confusion(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["fact_hypothesis_confusion_rate"] == 0.0

    def test_has_anchored_facts(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert any("alpha_status" in f for f in result["anchored_facts"])

    def test_has_rejected_hypotheses(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["rejected_hypotheses_count"] > 0

    def test_commitment_events_tracked(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["commitment_events_count"] > 0

    def test_revision_events_tracked(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        assert result["revision_events_count"] > 0

    def test_delta_status_remains_hypothesis(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        delta_hyps = [h for h in result["active_hypotheses"] if "delta_status" in h]
        assert len(delta_hyps) > 0

    def test_alpha_status_is_anchored_fact(self):
        result = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        alpha_facts = [f for f in result["anchored_facts"] if "alpha_status" in f]
        assert len(alpha_facts) > 0
        assert "delayed" in alpha_facts[-1]


class TestMetrics:
    def test_confusion_rate_zero(self):
        answers = [
            {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
        ]
        assert measure_confusion_rate(answers) == 0.0

    def test_confusion_rate_full(self):
        answers = [
            {"question": "Q1", "correct": False, "confused": True, "requires_distinguishing": True},
        ]
        assert measure_confusion_rate(answers) == 1.0

    def test_drift_rate(self):
        answers = [
            {"question": "Q1", "correct": True, "confused": False},
            {"question": "Q2", "correct": False, "confused": True},
        ]
        assert measure_drift_rate(answers) == 0.5

    def test_readability_worldstate(self):
        result = {
            "group": "C (WorldState)",
            "anchored_facts": ["fact1"],
            "active_hypotheses": ["hyp1"],
            "rejected_hypotheses": ["hyp2"],
        }
        r = measure_readability(result)
        assert r["can_distinguish_facts_from_hypotheses"] is True

    def test_readability_letta(self):
        result = {"group": "A (Letta-style)"}
        r = measure_readability(result)
        assert r["can_distinguish_facts_from_hypotheses"] is False

    def test_maintenance_cost_worldstate(self):
        result = {
            "group": "C (WorldState)",
            "entities_count": 3,
            "anchored_facts_count": 5,
            "active_hypotheses_count": 2,
            "rejected_hypotheses_count": 1,
        }
        c = measure_maintenance_cost(result)
        assert c["confusion_risk"] == "low"

    def test_maintenance_cost_letta(self):
        result = {
            "group": "A (Letta-style)",
            "core_memory_size": 5,
            "archival_memory_size": 10,
        }
        c = measure_maintenance_cost(result)
        assert c["confusion_risk"] == "high"


class TestGoStopEvaluation:
    def test_go_when_c_improves(self):
        results = [
            {"group": "A (Letta-style)", "fact_hypothesis_confusion_rate": 0.33, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": False, "confused": True, "requires_distinguishing": True},
            ]},
            {"group": "B (LangGraph-style)", "fact_hypothesis_confusion_rate": 0.33, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": False, "confused": True, "requires_distinguishing": True},
            ]},
            {"group": "C (WorldState)", "fact_hypothesis_confusion_rate": 0.0, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": True, "confused": False, "requires_distinguishing": True},
            ], "anchored_facts": ["fact1"], "active_hypotheses": ["hyp1"], "rejected_hypotheses": ["hyp2"]},
        ]
        evaluation = evaluate_go_stop(results)
        assert evaluation["judgment"] == "GO"

    def test_stop_when_no_improvement(self):
        results = [
            {"group": "A (Letta-style)", "fact_hypothesis_confusion_rate": 0.33, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": False, "confused": True, "requires_distinguishing": True},
            ]},
            {"group": "B (LangGraph-style)", "fact_hypothesis_confusion_rate": 0.33, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": False, "confused": True, "requires_distinguishing": True},
            ]},
            {"group": "C (WorldState)", "fact_hypothesis_confusion_rate": 0.33, "answers": [
                {"question": "Q1", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q2", "correct": True, "confused": False, "requires_distinguishing": True},
                {"question": "Q3", "correct": False, "confused": True, "requires_distinguishing": True},
            ], "anchored_facts": [], "active_hypotheses": [], "rejected_hypotheses": []},
        ]
        evaluation = evaluate_go_stop(results)
        assert evaluation["judgment"] == "STOP"


class TestFullExperiment:
    def test_all_groups_run(self):
        result_a = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_c = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)

        assert result_a["fact_hypothesis_confusion_rate"] > result_c["fact_hypothesis_confusion_rate"]
        assert result_b["fact_hypothesis_confusion_rate"] > result_c["fact_hypothesis_confusion_rate"]

    def test_go_judgment(self):
        result_a = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_c = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)

        evaluation = evaluate_go_stop([result_a, result_b, result_c])
        assert evaluation["judgment"] in ("GO", "CONDITIONAL_GO")

    def test_delta_confusion_in_ab_not_c(self):
        result_a = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
        result_c = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)

        delta_a = [a for a in result_a["answers"] if "delta" in a["question"] and "status" in a["question"]][0]
        delta_b = [a for a in result_b["answers"] if "delta" in a["question"] and "status" in a["question"]][0]
        delta_c = [a for a in result_c["answers"] if "delta" in a["question"] and "status" in a["question"]][0]

        assert delta_a["confused"] is True
        assert delta_b["confused"] is True
        assert delta_c["confused"] is False
