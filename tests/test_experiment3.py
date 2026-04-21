"""Tests for Experiment 3: Full-Stack vs Stacked Solution."""

import pytest

from experiments.experiment3_full_stack_vs_stacked import (
    COMPLIANCE_REALITY,
    VERIFICATION_TOOLS,
    ROUND1_CLAIMS,
    ROUND2_CONDITIONAL,
    ROUND3_QUESTIONS,
    StackedState,
    LangGraphState,
    LangGraphCheckpoint,
    LettaCoreMemory,
    LettaArchivalMemory,
    OpenAIToolCall,
    _verify_rule,
    _get_correct_status,
    _get_rule_status_in_state,
    run_group_a,
    run_group_b,
    measure_success_rate,
    measure_error_attribution,
    measure_repeated_error_rate,
    measure_development_complexity,
    measure_understanding_cost,
    measure_debug_time,
    evaluate_go_stop,
)


class TestComplianceReality:
    def test_all_rules_present(self):
        expected = {"rule_1", "rule_2", "rule_3", "rule_4", "rule_5", "rule_6", "rule_7", "rule_8"}
        assert set(COMPLIANCE_REALITY.keys()) == expected

    def test_conditional_rules_have_depends_on(self):
        for rule_id, rule in COMPLIANCE_REALITY.items():
            if "conditional" in rule.get("category", ""):
                assert "depends_on" in rule, f"{rule_id} is conditional but missing depends_on"
                assert "should_check" in rule, f"{rule_id} is conditional but missing should_check"

    def test_verification_tools_subset_of_rules(self):
        assert VERIFICATION_TOOLS.issubset(set(COMPLIANCE_REALITY.keys()))

    def test_round1_claims_cover_independent_rules(self):
        claimed_ids = {c["rule_id"] for c in ROUND1_CLAIMS}
        for rule_id, rule in COMPLIANCE_REALITY.items():
            if "depends_on" not in rule:
                assert rule_id in claimed_ids, f"Independent rule {rule_id} not in ROUND1_CLAIMS"

    def test_round2_covers_conditional_rules(self):
        cond_ids = {c["rule_id"] for c in ROUND2_CONDITIONAL}
        for rule_id, rule in COMPLIANCE_REALITY.items():
            if "depends_on" in rule:
                assert rule_id in cond_ids, f"Conditional rule {rule_id} not in ROUND2_CONDITIONAL"


class TestHelperFunctions:
    def test_verify_rule_returns_actual_status(self):
        assert _verify_rule("rule_1") == "pass"
        assert _verify_rule("rule_2") == "fail"

    def test_get_correct_status_independent(self):
        assert _get_correct_status("rule_1") == "pass"
        assert _get_correct_status("rule_2") == "fail"

    def test_get_correct_status_conditional_should_check(self):
        assert _get_correct_status("rule_5") == "pass"
        assert _get_correct_status("rule_7") == "fail"

    def test_get_correct_status_conditional_should_not_check(self):
        assert _get_correct_status("rule_3") == "not_applicable"


class TestStackedState:
    def test_langgraph_checkpoint(self):
        gs = LangGraphState()
        gs.graph_state["rule_1"] = {"status": "pass", "verified": True}
        gs.save_checkpoint("round1")
        assert len(gs.checkpoints) == 1
        cp = gs.latest_checkpoint()
        assert cp.state_snapshot["rule_1"]["status"] == "pass"

    def test_letta_core_memory(self):
        cm = LettaCoreMemory()
        cm.write("rule_1: pass")
        cm.write("rule_2: pass")
        assert len(cm.read()) == 2
        assert "rule_1: pass" in cm.read()

    def test_letta_archival_memory(self):
        am = LettaArchivalMemory()
        am.store({"rule_id": "rule_1", "status": "pass"})
        am.store({"rule_id": "rule_2", "status": "pass"})
        results = am.search("rule_1")
        assert len(results) == 1

    def test_openai_tool_call(self):
        tc = OpenAIToolCall(tool_name="verify_rule", arguments={"rule_id": "rule_1"}, result="pass")
        assert tc.result == "pass"

    def test_stacked_state_composition(self):
        ss = StackedState()
        assert isinstance(ss.langgraph, LangGraphState)
        assert isinstance(ss.letta_core, LettaCoreMemory)
        assert isinstance(ss.letta_archival, LettaArchivalMemory)
        assert isinstance(ss.tool_calls, list)


class TestGroupA:
    def test_run_returns_results(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["group"] == "A (Stacked: LangGraph+Letta+OpenAI)"
        assert "success_rate" in result
        assert len(result["answers"]) == len(ROUND3_QUESTIONS)

    def test_verifiable_rules_correct(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_1"]["matches_reality"] is True
        assert result["rule_results"]["rule_4"]["matches_reality"] is True

    def test_unverifiable_rules_wrong(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_2"]["matches_reality"] is False
        assert result["rule_results"]["rule_6"]["matches_reality"] is False
        assert result["rule_results"]["rule_8"]["matches_reality"] is False

    def test_rule7_skipped_wrong(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_7"]["status"] == "skipped"
        assert result["rule_results"]["rule_7"]["matches_reality"] is False

    def test_rule3_checked_wrong(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_3"]["status"] == "fail"
        assert result["rule_results"]["rule_3"]["matches_reality"] is False

    def test_no_error_attribution(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["can_attribute_errors"] is False
        assert result["attribution_accuracy"] == 0.0

    def test_repeated_errors(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["repeated_error_rate"] > 0.0

    def test_has_checkpoints(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["checkpoint_count"] == 2

    def test_has_tool_calls(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["tool_call_count"] > 0

    def test_rule5_correct(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_5"]["matches_reality"] is True


class TestGroupB:
    def test_run_returns_results(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert "Full-Stack" in result["group"]
        assert "success_rate" in result
        assert len(result["answers"]) == len(ROUND3_QUESTIONS)

    def test_verifiable_rules_correct(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_1"]["matches_reality"] is True
        assert result["rule_results"]["rule_4"]["matches_reality"] is True

    def test_unverifiable_rules_as_hypotheses(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_2"]["verified"] is False
        assert result["rule_results"]["rule_6"]["verified"] is False
        assert result["rule_results"]["rule_8"]["verified"] is False

    def test_rule7_checked_despite_uncertainty(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_7"]["status"] == "fail"
        assert result["rule_results"]["rule_7"]["matches_reality"] is True

    def test_rule5_correct(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["rule_results"]["rule_5"]["matches_reality"] is True

    def test_error_attribution(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["can_attribute_errors"] is True
        assert result["attribution_accuracy"] > 0.0

    def test_commitment_events_tracked(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["commitment_events_count"] > 0

    def test_revision_events_tracked(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["revision_events_count"] > 0

    def test_has_anchored_facts(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["anchored_facts_count"] > 0
        assert any("rule_1" in f for f in result["anchored_facts"])

    def test_unverifiable_wrong_claims_remain_hypotheses(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        unverifiable_wrong = [
            c["rule_id"] for c in ROUND1_CLAIMS
            if not c["verifiable"] and c["claimed_status"] != COMPLIANCE_REALITY[c["rule_id"]]["actual_status"]
        ]
        active = result["active_hypotheses"]
        for rule_id in unverifiable_wrong:
            found = any(rule_id in h for h in active)
            assert found, f"Unverifiable wrong claim for {rule_id} should remain as active hypothesis"

    def test_has_active_hypotheses_for_unverifiable(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        unverifiable_rules = [c["rule_id"] for c in ROUND1_CLAIMS if not c["verifiable"]]
        active = result["active_hypotheses"]
        found = any(any(r in h for r in unverifiable_rules) for h in active)
        assert found

    def test_has_tensions_for_uncertain_dependencies(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["tension_count"] > 0

    def test_has_dependency_relations(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert len(result["dependency_relations"]) == len(ROUND2_CONDITIONAL)

    def test_has_tracing_mechanism(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["has_tracing_mechanism"] is True

    def test_no_repeated_errors(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["repeated_error_rate"] == 0.0

    def test_uncertain_count_positive(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result["uncertain_count"] > 0


class TestMetrics:
    def test_success_rate_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        sr = measure_success_rate(result)
        assert sr["success_rate"] < 0.5
        assert sr["correct_count"] == 3

    def test_success_rate_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        sr = measure_success_rate(result)
        assert sr["success_rate"] > result["success_rate"] - 0.01
        assert sr["adjusted_success_rate"] > sr["success_rate"]

    def test_error_attribution_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        attr = measure_error_attribution(result)
        assert attr["can_attribute_errors"] is False
        assert attr["attribution_accuracy"] == 0.0

    def test_error_attribution_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        attr = measure_error_attribution(result)
        assert attr["can_attribute_errors"] is True
        assert attr["attribution_accuracy"] > 0.0

    def test_repeated_error_rate_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        rep = measure_repeated_error_rate(result)
        assert rep["repeated_error_rate"] > 0.0

    def test_repeated_error_rate_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        rep = measure_repeated_error_rate(result)
        assert rep["repeated_error_rate"] == 0.0

    def test_development_complexity_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        comp = measure_development_complexity(result)
        assert comp["data_structures"] > 0
        assert comp["functions"] > 0
        assert comp["total_complexity"] > 0

    def test_development_complexity_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        comp = measure_development_complexity(result)
        assert comp["data_structures"] > 0
        assert comp["functions"] > 0

    def test_understanding_cost_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        uc = measure_understanding_cost(result)
        assert uc["effective_cost"] == "high"
        assert uc["can_distinguish_facts_from_hypotheses"] is False

    def test_understanding_cost_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        uc = measure_understanding_cost(result)
        assert uc["effective_cost"] == "low"
        assert uc["can_distinguish_facts_from_hypotheses"] is True

    def test_debug_time_group_a(self):
        result = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        debug = measure_debug_time(result)
        assert debug["has_tracing_mechanism"] is False
        assert debug["debug_steps"] > 5

    def test_debug_time_group_b(self):
        result = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        debug = measure_debug_time(result)
        assert debug["has_tracing_mechanism"] is True
        assert debug["debug_steps"] <= 5


class TestGoStopEvaluation:
    def test_go_when_b_improves(self):
        results = [
            {
                "group": "A (Stacked: LangGraph+Letta+OpenAI)",
                "success_rate": 0.375,
                "correct_count": 3,
                "wrong_count": 5,
                "uncertain_count": 0,
                "total_rules": 8,
                "attribution_accuracy": 0.0,
                "repeated_error_rate": 1.0,
                "repeated_errors": 2,
                "data_structures": 6,
                "functions": 4,
                "understanding_items": 30,
                "debug_steps": 30,
                "can_attribute_errors": False,
                "has_tracing_mechanism": False,
                "answers": [
                    {"question": "Q1", "correct": True, "tests_attribution": False},
                    {"question": "Q2", "correct": False, "tests_attribution": True, "can_attribute_error": False},
                ],
            },
            {
                "group": "B (Full-Stack: WorldState+Commitment+Revision+Reality+Policy)",
                "success_rate": 0.5,
                "correct_count": 4,
                "wrong_count": 1,
                "uncertain_count": 3,
                "total_rules": 8,
                "attribution_accuracy": 1.0,
                "repeated_error_rate": 0.0,
                "repeated_errors": 0,
                "data_structures": 7,
                "functions": 8,
                "understanding_items": 20,
                "debug_steps": 2,
                "can_attribute_errors": True,
                "has_tracing_mechanism": True,
                "answers": [
                    {"question": "Q1", "correct": True, "tests_attribution": False},
                    {"question": "Q2", "correct": True, "tests_attribution": True, "can_attribute_error": True},
                ],
            },
        ]
        evaluation = evaluate_go_stop(results)
        assert evaluation["judgment"] in ("GO", "CONDITIONAL_GO")
        assert evaluation["metrics_b_better"] >= 2

    def test_stop_when_no_improvement(self):
        results = [
            {
                "group": "A (Stacked: LangGraph+Letta+OpenAI)",
                "success_rate": 0.5,
                "correct_count": 4,
                "wrong_count": 4,
                "uncertain_count": 0,
                "total_rules": 8,
                "attribution_accuracy": 0.0,
                "repeated_error_rate": 0.5,
                "repeated_errors": 1,
                "data_structures": 6,
                "functions": 4,
                "understanding_items": 20,
                "debug_steps": 20,
                "can_attribute_errors": False,
                "has_tracing_mechanism": False,
                "answers": [
                    {"question": "Q1", "correct": True, "tests_attribution": False},
                    {"question": "Q2", "correct": False, "tests_attribution": True, "can_attribute_error": False},
                ],
            },
            {
                "group": "B (Full-Stack: WorldState+Commitment+Revision+Reality+Policy)",
                "success_rate": 0.5,
                "correct_count": 4,
                "wrong_count": 4,
                "uncertain_count": 0,
                "total_rules": 8,
                "attribution_accuracy": 0.0,
                "repeated_error_rate": 0.5,
                "repeated_errors": 1,
                "data_structures": 7,
                "functions": 8,
                "understanding_items": 20,
                "debug_steps": 20,
                "can_attribute_errors": False,
                "has_tracing_mechanism": False,
                "answers": [
                    {"question": "Q1", "correct": True, "tests_attribution": False},
                    {"question": "Q2", "correct": False, "tests_attribution": True, "can_attribute_error": False},
                ],
            },
        ]
        evaluation = evaluate_go_stop(results)
        assert evaluation["judgment"] == "STOP"


class TestFullExperiment:
    def test_all_groups_run(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result_a["total_rules"] == result_b["total_rules"]
        assert len(result_a["answers"]) == len(result_b["answers"])

    def test_b_better_success_rate(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        sr_a = measure_success_rate(result_a)
        sr_b = measure_success_rate(result_b)
        assert sr_b["adjusted_success_rate"] > sr_a["adjusted_success_rate"]

    def test_b_better_attribution(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        attr_a = measure_error_attribution(result_a)
        attr_b = measure_error_attribution(result_b)
        assert attr_b["attribution_accuracy"] > attr_a["attribution_accuracy"]

    def test_b_fewer_repeated_errors(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        rep_a = measure_repeated_error_rate(result_a)
        rep_b = measure_repeated_error_rate(result_b)
        assert rep_b["repeated_error_rate"] <= rep_a["repeated_error_rate"]

    def test_b_faster_debug(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        debug_a = measure_debug_time(result_a)
        debug_b = measure_debug_time(result_b)
        assert debug_b["debug_steps"] < debug_a["debug_steps"]

    def test_go_judgment(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        evaluation = evaluate_go_stop([result_a, result_b])
        assert evaluation["judgment"] in ("GO", "CONDITIONAL_GO")

    def test_rule7_cascade_difference(self):
        result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
        assert result_a["rule_results"]["rule_7"]["matches_reality"] is False
        assert result_b["rule_results"]["rule_7"]["matches_reality"] is True
