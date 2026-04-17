import pytest

from cee_core.change_test import (
    ChangeProposal,
    ChangeTestResult,
    evaluate_change_test,
)


def _valid_proposal() -> ChangeProposal:
    return ChangeProposal(
        description="Add memory evidence gate",
        authority_restored="Memory promotion now requires evidence gate per Authority Split",
        typed_contract_explicit="confidence_gate covers memory section with evidence check",
        audit_replay_improved="memory patches without evidence are escalated to requires_approval",
        model_freedom_constrained="direct model-written memory without evidence is blocked",
        boundary_still_forbidden="memory patches without provenance remain blocked after this change",
    )


def test_valid_proposal_passes():
    result = evaluate_change_test(_valid_proposal())
    assert result.passed is True
    assert result.score == 5


def test_empty_description_fails():
    proposal = ChangeProposal(
        description="",
        authority_restored="restores something meaningful",
        typed_contract_explicit="makes something more explicit",
        audit_replay_improved="improves audit in some way",
        model_freedom_constrained="constrains model in some way",
        boundary_still_forbidden="some boundary remains forbidden",
    )
    result = evaluate_change_test(proposal)
    assert result.passed is False
    assert "description" in result.failures[0]


def test_empty_answer_fails():
    proposal = ChangeProposal(
        description="some change",
        authority_restored="",
        typed_contract_explicit="makes something more explicit",
        audit_replay_improved="improves audit in some way",
        model_freedom_constrained="constrains model in some way",
        boundary_still_forbidden="some boundary remains forbidden",
    )
    result = evaluate_change_test(proposal)
    assert result.passed is False
    assert result.authority_score is False


def test_short_answer_fails():
    proposal = ChangeProposal(
        description="some change",
        authority_restored="yes",
        typed_contract_explicit="makes something more explicit",
        audit_replay_improved="improves audit in some way",
        model_freedom_constrained="constrains model in some way",
        boundary_still_forbidden="some boundary remains forbidden",
    )
    result = evaluate_change_test(proposal)
    assert result.passed is False
    assert "too short" in result.failures[0]


def test_partial_pass_reports_correct_score():
    proposal = ChangeProposal(
        description="some change",
        authority_restored="restores something meaningful here",
        typed_contract_explicit="",
        audit_replay_improved="improves audit in some meaningful way",
        model_freedom_constrained="",
        boundary_still_forbidden="some boundary remains forbidden here",
    )
    result = evaluate_change_test(proposal)
    assert result.passed is False
    assert result.score == 3
    assert result.authority_score is True
    assert result.contract_score is False
    assert result.freedom_score is False


def test_change_test_result_score_range():
    result = evaluate_change_test(_valid_proposal())
    assert 0 <= result.score <= 5
