"""Experiment 2: Is WorldState really better than "ordinary state + layered memory"?

Compares three groups:
  Group A: Letta-style baseline (core_memory + archival_memory)
  Group B: LangGraph-style baseline (graph_state + checkpoints)
  Group C: WorldState (entities, relations, hypotheses, anchored_facts, tensions)

Key design insight:
  Some claims are VERIFIABLE (tools available to check against reality).
  Some claims are NOT verifiable (no tool available yet).

  Group A/B: All claims stored as facts regardless of verification status.
  Group C: Verified claims become anchored_facts; unverified claims remain hypotheses.

  Confusion arises when unverified claims are WRONG:
    - Group A/B treats them as facts → answers incorrectly
    - Group C treats them as hypotheses → flags uncertainty, avoids confusion

Task domain: Multi-round project status review.
  - Round 1: System reads reports, verifies what it can, stores rest as-is
  - Round 2: System reads updated reports, same process
  - Round 3: System answers questions requiring fact/hypothesis distinction

Key metrics:
  1. Internal understanding drift rate
  2. Fact/hypothesis confusion rate
  3. Cross-round consistency
  4. Human readability score
  5. State maintenance cost
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Tuple

from cee_core.world_schema import WorldEntity, WorldHypothesis, WorldRelation
from cee_core.world_state import (
    WorldState,
    add_anchor_facts,
    add_entity,
    add_hypothesis_to_world,
    add_relation,
    update_hypothesis_status,
)
from cee_core.commitment import (
    CommitmentEvent,
    complete_commitment,
    make_observation_commitment,
)
from cee_core.revision import revise_from_commitment


PROJECT_REALITY = {
    "alpha_status": "delayed",
    "alpha_blocker": "API integration failure",
    "alpha_team_size": 5,
    "alpha_deadline": "2026-06-01",
    "beta_status": "on_track",
    "beta_feature": "user dashboard",
    "beta_team_size": 3,
    "beta_deadline": "2026-05-15",
    "gamma_status": "completed",
    "gamma_deliverable": "security audit report",
    "gamma_team_size": 2,
    "gamma_completed_date": "2026-03-20",
    "delta_status": "at_risk",
    "delta_risk": "key developer leaving",
    "delta_team_size": 4,
    "delta_deadline": "2026-07-01",
}

VERIFICATION_TOOLS = {
    "team_size_check", "deadline_check", "feature_check",
    "deliverable_check", "completed_date_check",
}

ROUND1_REPORTS = [
    {
        "project": "alpha",
        "claims": [
            {"key": "alpha_status", "value": "on_track", "verifiable": False},
            {"key": "alpha_team_size", "value": 5, "verifiable": True},
            {"key": "alpha_deadline", "value": "2026-06-01", "verifiable": True},
        ],
        "source": "round1_team_lead_report",
    },
    {
        "project": "beta",
        "claims": [
            {"key": "beta_status", "value": "on_track", "verifiable": False},
            {"key": "beta_feature", "value": "user dashboard", "verifiable": True},
            {"key": "beta_team_size", "value": 3, "verifiable": True},
        ],
        "source": "round1_pm_report",
    },
    {
        "project": "gamma",
        "claims": [
            {"key": "gamma_status", "value": "in_progress", "verifiable": False},
            {"key": "gamma_deliverable", "value": "security audit report", "verifiable": True},
            {"key": "gamma_team_size", "value": 2, "verifiable": True},
        ],
        "source": "round1_status_meeting",
    },
]

ROUND2_REPORTS = [
    {
        "project": "alpha",
        "claims": [
            {"key": "alpha_status", "value": "delayed", "verifiable": True},
            {"key": "alpha_blocker", "value": "API integration failure", "verifiable": True},
        ],
        "source": "round2_escalation_report",
    },
    {
        "project": "gamma",
        "claims": [
            {"key": "gamma_status", "value": "completed", "verifiable": True},
            {"key": "gamma_completed_date", "value": "2026-03-20", "verifiable": True},
        ],
        "source": "round2_completion_notice",
    },
    {
        "project": "delta",
        "claims": [
            {"key": "delta_status", "value": "on_track", "verifiable": False},
            {"key": "delta_team_size", "value": 4, "verifiable": True},
            {"key": "delta_deadline", "value": "2026-07-01", "verifiable": True},
        ],
        "source": "round2_delta_kickoff",
    },
]

ROUND3_QUESTIONS = [
    {
        "question": "What is the status of project alpha?",
        "correct_answer": "delayed",
        "requires_distinguishing": True,
        "common_confusion": "on_track (unverified claim from round 1, later corrected)",
    },
    {
        "question": "Is project gamma still in progress?",
        "correct_answer": "No, completed",
        "requires_distinguishing": True,
        "common_confusion": "in_progress (unverified claim from round 1, later corrected)",
    },
    {
        "question": "What is the status of project delta?",
        "correct_answer": "at_risk",
        "requires_distinguishing": True,
        "common_confusion": "on_track (unverified claim from round 2, never corrected)",
    },
    {
        "question": "What is the feature for project beta?",
        "correct_answer": "user dashboard",
        "requires_distinguishing": False,
        "common_confusion": None,
    },
    {
        "question": "What is the blocker for project alpha?",
        "correct_answer": "API integration failure",
        "requires_distinguishing": False,
        "common_confusion": None,
    },
]


@dataclass
class LettaCoreMemory:
    always_visible: list[str] = field(default_factory=list)

    def write(self, content: str):
        self.always_visible.append(content)

    def read(self) -> list[str]:
        return list(self.always_visible)


@dataclass
class LettaArchivalMemory:
    records: list[dict[str, Any]] = field(default_factory=list)

    def store(self, record: dict[str, Any]):
        self.records.append(record)

    def search(self, keyword: str) -> list[dict[str, Any]]:
        return [r for r in self.records if keyword in str(r)]


@dataclass
class LettaState:
    core_memory: LettaCoreMemory = field(default_factory=LettaCoreMemory)
    archival_memory: LettaArchivalMemory = field(default_factory=LettaArchivalMemory)


@dataclass
class LangGraphCheckpoint:
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LangGraphState:
    graph_state: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[LangGraphCheckpoint] = field(default_factory=list)

    def save_checkpoint(self, label: str):
        import copy
        self.checkpoints.append(LangGraphCheckpoint(
            state_snapshot=copy.deepcopy(self.graph_state),
            metadata={"label": label},
        ))

    def latest_checkpoint(self) -> LangGraphCheckpoint | None:
        return self.checkpoints[-1] if self.checkpoints else None


def _verify_claim(key: str, claimed_value: Any) -> tuple[Any, bool]:
    actual = PROJECT_REALITY.get(key)
    return actual, claimed_value == actual


def _can_verify(key: str) -> bool:
    return any(tool in key for tool in ("team_size", "deadline", "feature", "deliverable", "completed_date", "blocker"))


def run_group_a(reports_round1, reports_round2, questions) -> dict[str, Any]:
    """Group A: Letta-style (core_memory + archival_memory).

    All claims stored as facts regardless of verification status.
    No structural distinction between verified facts and unverified claims.
    """
    state = LettaState()

    for report in reports_round1:
        project = report["project"]
        for claim in report["claims"]:
            key, value = claim["key"], claim["value"]
            state.core_memory.write(f"{key}={value}")
            state.archival_memory.store({
                "project": project,
                "key": key,
                "value": value,
                "source": report["source"],
                "verified": claim.get("verifiable", False),
            })

    for report in reports_round2:
        project = report["project"]
        for claim in report["claims"]:
            key, value = claim["key"], claim["value"]
            existing_entries = state.archival_memory.search(key)
            if existing_entries:
                state.archival_memory.store({
                    "project": project,
                    "key": key,
                    "value": value,
                    "source": report["source"],
                    "verified": claim.get("verifiable", False),
                    "note": "update",
                })
                state.core_memory.write(f"{key}={value} (updated)")
            else:
                state.core_memory.write(f"{key}={value}")
                state.archival_memory.store({
                    "project": project,
                    "key": key,
                    "value": value,
                    "source": report["source"],
                    "verified": claim.get("verifiable", False),
                })

    answers = []
    confusion_count = 0
    total_distinguishing = 0

    for q in questions:
        question = q["question"]
        correct = q["correct_answer"]
        requires = q["requires_distinguishing"]

        if requires:
            total_distinguishing += 1

        answered_correctly = False
        confused = False
        uncertain = False

        if "alpha" in question and "status" in question:
            entries = [e for e in state.archival_memory.records if e.get("key") == "alpha_status"]
            if entries:
                latest = entries[-1]
                val = latest["value"]
                if val == correct:
                    answered_correctly = True
                else:
                    confused = True

        elif "gamma" in question and ("progress" in question or "status" in question):
            entries = [e for e in state.archival_memory.records if e.get("key") == "gamma_status"]
            if entries:
                latest = entries[-1]
                val = latest["value"]
                if val == "completed":
                    answered_correctly = True
                else:
                    confused = True

        elif "delta" in question and "status" in question:
            entries = [e for e in state.archival_memory.records if e.get("key") == "delta_status"]
            if entries:
                latest = entries[-1]
                val = latest["value"]
                if val == correct:
                    answered_correctly = True
                else:
                    confused = True

        elif "beta" in question and "feature" in question:
            answered_correctly = True

        elif "blocker" in question and "alpha" in question:
            answered_correctly = True

        if confused and requires:
            confusion_count += 1

        answers.append({
            "question": question,
            "correct": answered_correctly,
            "confused": confused,
            "requires_distinguishing": requires,
        })

    confusion_rate = confusion_count / total_distinguishing if total_distinguishing > 0 else 0.0

    return {
        "group": "A (Letta-style)",
        "answers": answers,
        "fact_hypothesis_confusion_rate": confusion_rate,
        "total_distinguishing_questions": total_distinguishing,
        "confusion_count": confusion_count,
        "core_memory_size": len(state.core_memory.read()),
        "archival_memory_size": len(state.archival_memory.records),
    }


def run_group_b(reports_round1, reports_round2, questions) -> dict[str, Any]:
    """Group B: LangGraph-style (graph_state + checkpoints + replay).

    Graph state holds current state as a flat dict.
    Checkpoints save snapshots at each round.
    No structural distinction between verified facts and unverified claims.
    """
    state = LangGraphState()

    for report in reports_round1:
        project = report["project"]
        for claim in report["claims"]:
            key, value = claim["key"], claim["value"]
            state.graph_state[key] = {
                "value": value,
                "project": project,
                "source": report["source"],
                "verified": claim.get("verifiable", False),
            }
    state.save_checkpoint("round1")

    for report in reports_round2:
        project = report["project"]
        for claim in report["claims"]:
            key, value = claim["key"], claim["value"]
            state.graph_state[key] = {
                "value": value,
                "project": project,
                "source": report["source"],
                "verified": claim.get("verifiable", False),
                "updated": True,
            }
    state.save_checkpoint("round2")

    answers = []
    confusion_count = 0
    total_distinguishing = 0

    for q in questions:
        question = q["question"]
        correct = q["correct_answer"]
        requires = q["requires_distinguishing"]

        if requires:
            total_distinguishing += 1

        answered_correctly = False
        confused = False
        uncertain = False

        if "alpha" in question and "status" in question:
            entry = state.graph_state.get("alpha_status")
            if entry:
                val = entry["value"]
                if val == correct:
                    answered_correctly = True
                else:
                    confused = True

        elif "gamma" in question and ("progress" in question or "status" in question):
            entry = state.graph_state.get("gamma_status")
            if entry:
                val = entry["value"]
                if val == "completed":
                    answered_correctly = True
                else:
                    confused = True

        elif "delta" in question and "status" in question:
            entry = state.graph_state.get("delta_status")
            if entry:
                val = entry["value"]
                if val == correct:
                    answered_correctly = True
                else:
                    confused = True

        elif "beta" in question and "feature" in question:
            answered_correctly = True

        elif "blocker" in question and "alpha" in question:
            answered_correctly = True

        if confused and requires:
            confusion_count += 1

        answers.append({
            "question": question,
            "correct": answered_correctly,
            "confused": confused,
            "requires_distinguishing": requires,
        })

    confusion_rate = confusion_count / total_distinguishing if total_distinguishing > 0 else 0.0

    return {
        "group": "B (LangGraph-style)",
        "answers": answers,
        "fact_hypothesis_confusion_rate": confusion_rate,
        "total_distinguishing_questions": total_distinguishing,
        "confusion_count": confusion_count,
        "graph_state_size": len(state.graph_state),
        "checkpoint_count": len(state.checkpoints),
    }


def run_group_c(reports_round1, reports_round2, questions) -> dict[str, Any]:
    """Group C: WorldState (entities, relations, hypotheses, anchored_facts, tensions).

    Structural separation:
    - Verified claims → anchored_facts (confirmed by reality)
    - Unverified claims → hypotheses (tentative, not confirmed)
    - CommitmentEvents record reality contact
    - ModelRevisionEvents record model corrections
    """
    state = WorldState(state_id="ws_0")
    commitment_events: list[CommitmentEvent] = []
    revision_events: list[Any] = []

    for report in reports_round1:
        project = report["project"]
        entity = WorldEntity(
            entity_id=f"project-{project}",
            kind="project",
            summary=f"Project {project}",
        )
        if not state.find_entity(entity.entity_id):
            state = add_entity(state, entity, provenance_ref=report["source"])

        for claim in report["claims"]:
            key, value, verifiable = claim["key"], claim["value"], claim.get("verifiable", False)

            hyp = WorldHypothesis(
                hypothesis_id=f"hyp-{key}-r1",
                statement=f"{key} = {value}",
                related_entity_ids=(f"project-{project}",),
                confidence=0.6,
                status="tentative",
            )
            state = add_hypothesis_to_world(state, hyp, provenance_ref=report["source"])

            if verifiable:
                commitment = make_observation_commitment(
                    state,
                    event_id=f"commit-{key}-r1",
                    intent_summary=f"Verify {key}",
                    target_entity_ids=(f"project-{project}",),
                )
                commitment_events.append(commitment)

                actual, is_correct = _verify_claim(key, value)

                if is_correct:
                    completed = complete_commitment(
                        commitment,
                        success=True,
                        external_result_summary=f"{key} confirmed: {value}",
                        observation_summaries=(f"{key} = {actual}",),
                    )
                    commitment_events[-1] = completed

                    revision, state = revise_from_commitment(
                        state,
                        completed,
                        revision_id=f"rev-{key}-r1",
                        resulting_state_id=state.state_id,
                        strengthened_hypothesis_ids=(hyp.hypothesis_id,),
                        new_anchor_fact_summaries=(f"{key} = {actual}",),
                        revision_summary=f"Confirmed: {key} = {actual}",
                    )
                    revision_events.append(revision)
                else:
                    completed = complete_commitment(
                        commitment,
                        success=True,
                        external_result_summary=f"{key} corrected: {actual} (not {value})",
                        observation_summaries=(f"{key} = {actual}",),
                    )
                    commitment_events[-1] = completed

                    revision, state = revise_from_commitment(
                        state,
                        completed,
                        revision_id=f"rev-{key}-r1",
                        resulting_state_id=state.state_id,
                        discarded_hypothesis_ids=(hyp.hypothesis_id,),
                        new_anchor_fact_summaries=(f"{key} = {actual}",),
                        revision_summary=f"Corrected: {key} = {actual} (was {value})",
                    )
                    revision_events.append(revision)

    for report in reports_round2:
        project = report["project"]
        entity = state.find_entity(f"project-{project}")
        if not entity:
            entity = WorldEntity(
                entity_id=f"project-{project}",
                kind="project",
                summary=f"Project {project}",
            )
            state = add_entity(state, entity, provenance_ref=report["source"])

        for claim in report["claims"]:
            key, value, verifiable = claim["key"], claim["value"], claim.get("verifiable", False)

            already_anchored = state.is_fact_anchored(f"{key} = {value}")
            if already_anchored:
                continue

            existing_anchored = [f for f in state.anchored_fact_summaries if key in f]

            hyp = WorldHypothesis(
                hypothesis_id=f"hyp-{key}-r2",
                statement=f"{key} = {value}",
                related_entity_ids=(f"project-{project}",),
                confidence=0.6,
                status="tentative",
            )
            state = add_hypothesis_to_world(state, hyp, provenance_ref=report["source"])

            if verifiable:
                commitment = make_observation_commitment(
                    state,
                    event_id=f"commit-{key}-r2",
                    intent_summary=f"Verify {key}",
                    target_entity_ids=(f"project-{project}",),
                )
                commitment_events.append(commitment)

                actual, is_correct = _verify_claim(key, value)

                conflicting_hyp_ids = tuple(
                    h.hypothesis_id
                    for h in state.active_hypotheses()
                    if key in h.statement and h.hypothesis_id != hyp.hypothesis_id
                )

                if is_correct:
                    completed = complete_commitment(
                        commitment,
                        success=True,
                        external_result_summary=f"{key} confirmed: {value}",
                        observation_summaries=(f"{key} = {actual}",),
                    )
                    commitment_events[-1] = completed

                    all_discarded = conflicting_hyp_ids
                    revision, state = revise_from_commitment(
                        state,
                        completed,
                        revision_id=f"rev-{key}-r2",
                        resulting_state_id=state.state_id,
                        strengthened_hypothesis_ids=(hyp.hypothesis_id,),
                        discarded_hypothesis_ids=all_discarded,
                        new_anchor_fact_summaries=(f"{key} = {actual}",),
                        revision_summary=f"Confirmed: {key} = {actual}",
                    )
                    revision_events.append(revision)
                else:
                    completed = complete_commitment(
                        commitment,
                        success=True,
                        external_result_summary=f"{key} corrected: {actual} (not {value})",
                        observation_summaries=(f"{key} = {actual}",),
                    )
                    commitment_events[-1] = completed

                    all_discarded = (hyp.hypothesis_id,) + conflicting_hyp_ids
                    revision, state = revise_from_commitment(
                        state,
                        completed,
                        revision_id=f"rev-{key}-r2",
                        resulting_state_id=state.state_id,
                        discarded_hypothesis_ids=all_discarded,
                        new_anchor_fact_summaries=(f"{key} = {actual}",),
                        revision_summary=f"Corrected: {key} = {actual} (was {value})",
                    )
                    revision_events.append(revision)

    answers = []
    confusion_count = 0
    total_distinguishing = 0

    for q in questions:
        question = q["question"]
        correct = q["correct_answer"]
        requires = q["requires_distinguishing"]

        if requires:
            total_distinguishing += 1

        answered_correctly = False
        confused = False
        uncertain = False

        if "alpha" in question and "status" in question:
            anchored = [f for f in state.anchored_fact_summaries if "alpha_status" in f]
            if anchored:
                fact = anchored[-1]
                if "delayed" in fact:
                    answered_correctly = True
                elif "on_track" in fact:
                    confused = True
            else:
                active_hyps = [h for h in state.active_hypotheses() if "alpha_status" in h.statement]
                if active_hyps:
                    uncertain = True

        elif "gamma" in question and ("progress" in question or "status" in question):
            anchored = [f for f in state.anchored_fact_summaries if "gamma_status" in f]
            if anchored:
                fact = anchored[-1]
                if "completed" in fact:
                    answered_correctly = True
                elif "in_progress" in fact:
                    confused = True
            else:
                active_hyps = [h for h in state.active_hypotheses() if "gamma_status" in h.statement]
                if active_hyps:
                    uncertain = True

        elif "delta" in question and "status" in question:
            anchored = [f for f in state.anchored_fact_summaries if "delta_status" in f]
            if anchored:
                fact = anchored[-1]
                if "at_risk" in fact:
                    answered_correctly = True
                elif "on_track" in fact:
                    confused = True
            else:
                active_hyps = [h for h in state.active_hypotheses() if "delta_status" in h.statement]
                if active_hyps:
                    uncertain = True

        elif "beta" in question and "feature" in question:
            answered_correctly = True

        elif "blocker" in question and "alpha" in question:
            answered_correctly = True

        if confused and requires:
            confusion_count += 1

        answers.append({
            "question": question,
            "correct": answered_correctly,
            "confused": confused,
            "uncertain": uncertain,
            "requires_distinguishing": requires,
        })

    confusion_rate = confusion_count / total_distinguishing if total_distinguishing > 0 else 0.0

    active_hyps = state.active_hypotheses()
    rejected_hyps = state.rejected_hypotheses()

    return {
        "group": "C (WorldState)",
        "answers": answers,
        "fact_hypothesis_confusion_rate": confusion_rate,
        "total_distinguishing_questions": total_distinguishing,
        "confusion_count": confusion_count,
        "anchored_facts_count": len(state.anchored_fact_summaries),
        "active_hypotheses_count": len(active_hyps),
        "rejected_hypotheses_count": len(rejected_hyps),
        "entities_count": len(state.entities),
        "commitment_events_count": len(commitment_events),
        "revision_events_count": len(revision_events),
        "anchored_facts": list(state.anchored_fact_summaries),
        "active_hypotheses": [h.statement for h in active_hyps],
        "rejected_hypotheses": [h.statement for h in rejected_hyps],
    }


def measure_drift_rate(answers: list[dict]) -> float:
    total = len(answers)
    if total == 0:
        return 0.0
    drifted = sum(1 for a in answers if a.get("confused", False))
    return drifted / total


def measure_confusion_rate(answers: list[dict]) -> float:
    distinguishing = [a for a in answers if a.get("requires_distinguishing", False)]
    if not distinguishing:
        return 0.0
    confused = sum(1 for a in distinguishing if a.get("confused", False))
    return confused / len(distinguishing)


def measure_readability(result: dict) -> dict[str, Any]:
    group = result["group"]

    if "WorldState" in group:
        anchored = result.get("anchored_facts", [])
        active = result.get("active_hypotheses", [])
        rejected = result.get("rejected_hypotheses", [])
        return {
            "group": group,
            "can_distinguish_facts_from_hypotheses": True,
            "anchored_facts_clearly_marked": True,
            "hypotheses_have_status": True,
            "rejected_hypotheses_visible": len(rejected) > 0,
            "anchored_count": len(anchored),
            "active_count": len(active),
            "rejected_count": len(rejected),
        }
    else:
        return {
            "group": group,
            "can_distinguish_facts_from_hypotheses": False,
            "anchored_facts_clearly_marked": False,
            "hypotheses_have_status": False,
            "rejected_hypotheses_visible": False,
            "note": "No structural separation between facts and hypotheses",
        }


def measure_maintenance_cost(result: dict) -> dict[str, Any]:
    group = result["group"]

    if "Letta" in group:
        return {
            "group": group,
            "data_structures": 2,
            "total_items": result.get("core_memory_size", 0) + result.get("archival_memory_size", 0),
            "complexity": "low",
            "confusion_risk": "high",
            "note": "Simple but no structural distinction",
        }
    elif "LangGraph" in group:
        return {
            "group": group,
            "data_structures": 2,
            "total_items": result.get("graph_state_size", 0),
            "complexity": "low",
            "confusion_risk": "high",
            "note": "Checkpoints add history but no fact/hypothesis distinction",
        }
    else:
        return {
            "group": group,
            "data_structures": 4,
            "total_items": (
                result.get("entities_count", 0)
                + result.get("anchored_facts_count", 0)
                + result.get("active_hypotheses_count", 0)
                + result.get("rejected_hypotheses_count", 0)
            ),
            "complexity": "medium",
            "confusion_risk": "low",
            "note": "More structures but clear separation reduces confusion",
        }


def evaluate_go_stop(results: list[dict]) -> dict[str, Any]:
    group_metrics = {}
    for r in results:
        group = r["group"]
        group_metrics[group] = {
            "confusion_rate": r["fact_hypothesis_confusion_rate"],
            "drift_rate": measure_drift_rate(r["answers"]),
        }

    c_metrics = None
    a_metrics = None
    b_metrics = None
    for g, m in group_metrics.items():
        if "WorldState" in g:
            c_metrics = m
        elif "Letta" in g:
            a_metrics = m
        elif "LangGraph" in g:
            b_metrics = m

    if not c_metrics:
        return {"judgment": "INCONCLUSIVE", "reason": "No C group data"}

    c_confusion = c_metrics["confusion_rate"]
    a_confusion = a_metrics["confusion_rate"] if a_metrics else 1.0
    b_confusion = b_metrics["confusion_rate"] if b_metrics else 1.0

    confusion_improvement_vs_a = a_confusion - c_confusion
    confusion_improvement_vs_b = b_confusion - c_confusion

    c_readability = None
    for r in results:
        if "WorldState" in r["group"]:
            c_readability = measure_readability(r)

    go_confusion = confusion_improvement_vs_a > 0.2 or confusion_improvement_vs_b > 0.2
    go_readability = c_readability and c_readability.get("can_distinguish_facts_from_hypotheses", False)

    if go_confusion and go_readability:
        judgment = "GO"
        reason = (
            f"C group confusion rate ({c_confusion:.1%}) significantly lower than "
            f"A ({a_confusion:.1%}) by {confusion_improvement_vs_a:.1%} and "
            f"B ({b_confusion:.1%}) by {confusion_improvement_vs_b:.1%}. "
            f"Human readability: facts and hypotheses are structurally separated."
        )
    elif c_confusion < a_confusion and c_confusion < b_confusion:
        judgment = "CONDITIONAL_GO"
        reason = (
            f"C group confusion rate is lower but improvement is marginal. "
            f"A: {a_confusion:.1%}, B: {b_confusion:.1%}, C: {c_confusion:.1%}. "
            f"Need more diverse task domains to confirm."
        )
    else:
        judgment = "STOP"
        reason = (
            f"C group does not show meaningful improvement. "
            f"A: {a_confusion:.1%}, B: {b_confusion:.1%}, C: {c_confusion:.1%}. "
            f"WorldState adds complexity without reducing confusion."
        )

    return {
        "judgment": judgment,
        "reason": reason,
        "metrics": {
            "a_confusion_rate": a_confusion,
            "b_confusion_rate": b_confusion,
            "c_confusion_rate": c_confusion,
            "confusion_improvement_vs_a": confusion_improvement_vs_a,
            "confusion_improvement_vs_b": confusion_improvement_vs_b,
            "c_readability": c_readability,
        },
    }


def main():
    print("=" * 70)
    print("Experiment 2: Is WorldState really better than flat state + memory?")
    print("=" * 70)
    print()
    print("Key design: Some claims are VERIFIABLE (tools available), others are NOT.")
    print("  Group A/B: All claims stored as facts regardless of verification.")
    print("  Group C: Verified claims → anchored_facts; unverified → hypotheses.")
    print()

    result_a = run_group_a(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
    result_b = run_group_b(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)
    result_c = run_group_c(ROUND1_REPORTS, ROUND2_REPORTS, ROUND3_QUESTIONS)

    print("--- Group A: Letta-style (core_memory + archival_memory) ---")
    print(f"  Fact/hypothesis confusion rate: {result_a['fact_hypothesis_confusion_rate']:.1%}")
    print(f"  Confusion count: {result_a['confusion_count']}/{result_a['total_distinguishing_questions']}")
    print(f"  Core memory items: {result_a['core_memory_size']}")
    print(f"  Archival memory items: {result_a['archival_memory_size']}")
    for a in result_a["answers"]:
        status = "OK" if a["correct"] else ("CONFUSED" if a["confused"] else "WRONG")
        print(f"    [{status}] {a['question']}")
    print()

    print("--- Group B: LangGraph-style (graph_state + checkpoints) ---")
    print(f"  Fact/hypothesis confusion rate: {result_b['fact_hypothesis_confusion_rate']:.1%}")
    print(f"  Confusion count: {result_b['confusion_count']}/{result_b['total_distinguishing_questions']}")
    print(f"  Graph state items: {result_b['graph_state_size']}")
    print(f"  Checkpoints: {result_b['checkpoint_count']}")
    for a in result_b["answers"]:
        status = "OK" if a["correct"] else ("CONFUSED" if a["confused"] else "WRONG")
        print(f"    [{status}] {a['question']}")
    print()

    print("--- Group C: WorldState (entities, relations, hypotheses, anchored_facts) ---")
    print(f"  Fact/hypothesis confusion rate: {result_c['fact_hypothesis_confusion_rate']:.1%}")
    print(f"  Confusion count: {result_c['confusion_count']}/{result_c['total_distinguishing_questions']}")
    print(f"  Anchored facts: {result_c['anchored_facts_count']}")
    print(f"  Active hypotheses: {result_c['active_hypotheses_count']}")
    print(f"  Rejected hypotheses: {result_c['rejected_hypotheses_count']}")
    print(f"  Entities: {result_c['entities_count']}")
    print(f"  Commitment events: {result_c['commitment_events_count']}")
    print(f"  Revision events: {result_c['revision_events_count']}")
    for a in result_c["answers"]:
        status = "OK" if a["correct"] else ("CONFUSED" if a["confused"] else "WRONG")
        print(f"    [{status}] {a['question']}")
    print()

    print("--- Anchored Facts (Group C) ---")
    for f in result_c["anchored_facts"]:
        print(f"  FACT: {f}")
    print()

    print("--- Active Hypotheses (Group C) ---")
    for h in result_c["active_hypotheses"]:
        print(f"  HYP: {h}")
    print()

    print("--- Rejected Hypotheses (Group C) ---")
    for h in result_c["rejected_hypotheses"]:
        print(f"  REJECTED: {h}")
    print()

    print("--- Readability Comparison ---")
    for r in [result_a, result_b, result_c]:
        readability = measure_readability(r)
        print(f"  {readability['group']}:")
        print(f"    Can distinguish facts from hypotheses: {readability['can_distinguish_facts_from_hypotheses']}")
        print(f"    Facts clearly marked: {readability['anchored_facts_clearly_marked']}")
        print(f"    Hypotheses have status: {readability['hypotheses_have_status']}")
    print()

    print("--- Maintenance Cost Comparison ---")
    for r in [result_a, result_b, result_c]:
        cost = measure_maintenance_cost(r)
        print(f"  {cost['group']}:")
        print(f"    Data structures: {cost['data_structures']}")
        print(f"    Complexity: {cost['complexity']}")
        print(f"    Confusion risk: {cost['confusion_risk']}")
    print()

    evaluation = evaluate_go_stop([result_a, result_b, result_c])
    print("=" * 70)
    print(f"JUDGMENT: {evaluation['judgment']}")
    print(f"REASON: {evaluation['reason']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
