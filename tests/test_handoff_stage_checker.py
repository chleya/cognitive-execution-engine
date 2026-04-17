from cee_core import assess_handoff_stage_gates, load_handoff_state


def test_assess_handoff_stage_gates_marks_current_repo_ready():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")

    results = assess_handoff_stage_gates(payload)

    assert len(results) == 7
    assert all(result.status == "ready" for result in results)


def test_assess_handoff_stage_gates_blocks_missing_focused_check():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["required_checks"] = ["python -m pytest -q"]  # type: ignore[index]

    results = assess_handoff_stage_gates(payload)

    focused_verify = next(result for result in results if result.stage == "focused_verify")
    assert focused_verify.status == "blocked"
    assert "focused verification command is missing" in focused_verify.reasons


def test_assess_handoff_stage_gates_blocks_diagnose_only_edits():
    payload = load_handoff_state("F:\\cognitive-execution-engine\\handoff_state.json")
    payload["execution_mode"] = "diagnose_only"

    results = assess_handoff_stage_gates(payload)

    edit_if_needed = next(result for result in results if result.stage == "edit_if_needed")
    assert edit_if_needed.status == "blocked"
    assert "execution_mode diagnose_only does not allow edits" in edit_if_needed.reasons
