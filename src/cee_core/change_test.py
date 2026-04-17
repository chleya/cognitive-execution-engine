"""Change Test automation per PRINCIPLE_BASELINE.

Every meaningful change to CEE should answer five questions. This module
makes those questions executable: a change proposal must pass the change
test before it can be considered aligned with CEE principles.

Usage:
    proposal = ChangeProposal(
        description="Add memory evidence gate",
        authority_restored="Memory promotion now requires evidence gate",
        typed_contract_explicit="confidence_gate covers memory section",
        audit_replay_improved="memory patches without evidence are escalated",
        model_freedom_constrained="direct model-written memory blocked",
        boundary_still_forbidden="memory patches without provenance remain blocked",
    )
    result = evaluate_change_test(proposal)
    assert result.passed
"""

from __future__ import annotations

from dataclasses import dataclass


_MIN_ANSWER_LENGTH = 10


@dataclass(frozen=True)
class ChangeProposal:
    description: str
    authority_restored: str
    typed_contract_explicit: str
    audit_replay_improved: str
    model_freedom_constrained: str
    boundary_still_forbidden: str


@dataclass(frozen=True)
class ChangeTestResult:
    passed: bool
    authority_score: bool
    contract_score: bool
    audit_score: bool
    freedom_score: bool
    boundary_score: bool
    failures: tuple[str, ...]

    @property
    def score(self) -> int:
        return sum([
            self.authority_score,
            self.contract_score,
            self.audit_score,
            self.freedom_score,
            self.boundary_score,
        ])


def _check_answer(answer: str, question_name: str) -> str | None:
    if not answer or not answer.strip():
        return f"{question_name}: answer is empty"
    if len(answer.strip()) < _MIN_ANSWER_LENGTH:
        return f"{question_name}: answer too short (min {_MIN_ANSWER_LENGTH} chars)"
    return None


def evaluate_change_test(proposal: ChangeProposal) -> ChangeTestResult:
    failures: list[str] = []

    if not proposal.description or not proposal.description.strip():
        failures.append("description: change description is empty")

    authority_fail = _check_answer(proposal.authority_restored, "authority_restored")
    contract_fail = _check_answer(proposal.typed_contract_explicit, "typed_contract_explicit")
    audit_fail = _check_answer(proposal.audit_replay_improved, "audit_replay_improved")
    freedom_fail = _check_answer(proposal.model_freedom_constrained, "model_freedom_constrained")
    boundary_fail = _check_answer(proposal.boundary_still_forbidden, "boundary_still_forbidden")

    for f in [authority_fail, contract_fail, audit_fail, freedom_fail, boundary_fail]:
        if f is not None:
            failures.append(f)

    authority_score = authority_fail is None
    contract_score = contract_fail is None
    audit_score = audit_fail is None
    freedom_score = freedom_fail is None
    boundary_score = boundary_fail is None

    return ChangeTestResult(
        passed=len(failures) == 0,
        authority_score=authority_score,
        contract_score=contract_score,
        audit_score=audit_score,
        freedom_score=freedom_score,
        boundary_score=boundary_score,
        failures=tuple(failures),
    )
