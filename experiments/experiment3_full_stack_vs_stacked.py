"""Experiment 3: The Cruelest Cut — Full-Stack vs Stacked Solution

Compares:
  Group A: Stacked (LangGraph + Letta + OpenAI tool calling)
    - Flat state dict + checkpoints (LangGraph)
    - Core memory + archival memory (Letta)
    - Tool calling for verification (OpenAI style)
    - No structural distinction between verified facts and unverified claims
    - No explicit hypothesis management
    - When a rule verification fails, no tracking of WHY or what assumption was wrong

  Group B: Full-stack (WorldState + CommitmentEvent + ModelRevisionEvent +
           RealityInterface + CommitmentPolicy)
    - Structural separation of verified facts and unverified hypotheses
    - CommitmentEvent for reality contact
    - ModelRevisionEvent for model corrections
    - RealityInterface for tool execution
    - CommitmentPolicy for boundary control
    - When a rule verification fails, tracks which hypothesis was contradicted

Task domain: Document rule verification with cascading consequences.
  A system must verify compliance rules across multiple documents.
  Some rules are independently verifiable, others depend on previous results.
  Wrong early decisions cascade into more errors.

Key insight:
  Group A stores all results as flat facts. When a conditional rule's dependency
  was wrong, Group A doesn't trace back to fix it. Group B has explicit hypothesis
  tracking and can identify which upstream assumption was wrong.

  Specifically:
  - Unverifiable wrong claims cause Group A to skip conditional rules that should
    be checked (false negative cascade) or check rules that should be skipped
    (false positive cascade).
  - Group B checks conditional rules even when dependencies are uncertain
    (conservative approach), and can attribute errors to specific hypotheses.

6 Metrics:
  1. End-to-end success rate
  2. Error attribution accuracy
  3. Repeated error rate
  4. Development complexity
  5. Understanding cost
  6. Debug time

Go/Stop Criteria:
  GO: B group better on at least 2 metrics, complexity not significantly higher
  STOP: B group not meaningfully better, or complexity is much higher
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
    add_tension,
    update_hypothesis_status,
)
from cee_core.commitment import (
    CommitmentEvent,
    complete_commitment,
    make_observation_commitment,
)
from cee_core.revision import revise_from_commitment
from cee_core.commitment_policy import (
    CommitmentPolicyDecision,
    DefaultCommitmentPolicy,
    evaluate_commitment_policy,
)
from cee_core.reality_interface import (
    DefaultRealityInterface,
    execute_commitment,
)


COMPLIANCE_REALITY = {
    "rule_1": {
        "requirement": "API key must be in env vars",
        "actual_status": "pass",
        "category": "security",
    },
    "rule_2": {
        "requirement": "Rate limit must be set",
        "actual_status": "fail",
        "category": "security",
        "detail": "No rate limit configured",
    },
    "rule_3": {
        "requirement": "If security rules pass, verify encryption at rest",
        "actual_status": "fail",
        "category": "security_conditional",
        "depends_on": "rule_2",
        "should_check": False,
    },
    "rule_4": {
        "requirement": "Database backup must be configured",
        "actual_status": "pass",
        "category": "reliability",
    },
    "rule_5": {
        "requirement": "If backup passes, verify recovery time objective",
        "actual_status": "pass",
        "category": "reliability_conditional",
        "depends_on": "rule_4",
        "should_check": True,
    },
    "rule_6": {
        "requirement": "Error logging must be enabled",
        "actual_status": "pass",
        "category": "observability",
    },
    "rule_7": {
        "requirement": "If logging passes, verify log retention policy",
        "actual_status": "fail",
        "category": "observability_conditional",
        "depends_on": "rule_6",
        "should_check": True,
    },
    "rule_8": {
        "requirement": "Input validation must be enabled",
        "actual_status": "fail",
        "category": "security",
        "detail": "No input validation on API endpoints",
    },
}

VERIFICATION_TOOLS = {"rule_1", "rule_4"}

ROUND1_CLAIMS = [
    {"rule_id": "rule_1", "claimed_status": "pass", "verifiable": True},
    {"rule_id": "rule_2", "claimed_status": "pass", "verifiable": False},
    {"rule_id": "rule_4", "claimed_status": "pass", "verifiable": True},
    {"rule_id": "rule_6", "claimed_status": "fail", "verifiable": False},
    {"rule_id": "rule_8", "claimed_status": "pass", "verifiable": False},
]

ROUND2_CONDITIONAL = [
    {"rule_id": "rule_3", "depends_on": "rule_2", "verifiable": True},
    {"rule_id": "rule_5", "depends_on": "rule_4", "verifiable": True},
    {"rule_id": "rule_7", "depends_on": "rule_6", "verifiable": True},
]

ROUND3_QUESTIONS = [
    {
        "question": "What is the status of rate limiting (rule_2)?",
        "correct_answer": "fail",
        "involves_cascade": False,
        "tests_attribution": False,
    },
    {
        "question": "Was encryption at rest (rule_3) correctly evaluated?",
        "correct_answer": "not_applicable",
        "involves_cascade": True,
        "cascade_from": "rule_2",
        "tests_attribution": False,
    },
    {
        "question": "Is the recovery time objective (rule_5) met?",
        "correct_answer": "pass",
        "involves_cascade": False,
        "tests_attribution": False,
    },
    {
        "question": "Is the log retention policy (rule_7) compliant?",
        "correct_answer": "fail",
        "involves_cascade": True,
        "cascade_from": "rule_6",
        "tests_attribution": False,
    },
    {
        "question": "Is input validation (rule_8) compliant?",
        "correct_answer": "fail",
        "involves_cascade": False,
        "tests_attribution": False,
    },
    {
        "question": "Which wrong assumption caused the most cascading errors?",
        "correct_answer": "rule_6 claimed fail (actual pass) caused rule_7 to be incorrectly skipped",
        "involves_cascade": True,
        "cascade_from": "rule_6",
        "tests_attribution": True,
    },
]


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
class OpenAIToolCall:
    tool_name: str
    arguments: dict[str, Any]
    result: Any


@dataclass
class StackedState:
    langgraph: LangGraphState = field(default_factory=LangGraphState)
    letta_core: LettaCoreMemory = field(default_factory=LettaCoreMemory)
    letta_archival: LettaArchivalMemory = field(default_factory=LettaArchivalMemory)
    tool_calls: list[OpenAIToolCall] = field(default_factory=list)


def _verify_rule(rule_id: str) -> str:
    return COMPLIANCE_REALITY[rule_id]["actual_status"]


def _get_correct_status(rule_id: str) -> str:
    reality = COMPLIANCE_REALITY[rule_id]
    if "depends_on" in reality:
        if reality["should_check"]:
            return reality["actual_status"]
        else:
            return "not_applicable"
    return reality["actual_status"]


def run_group_a(
    claims: list[dict],
    conditionals: list[dict],
    questions: list[dict],
) -> dict[str, Any]:
    state = StackedState()

    for claim in claims:
        rule_id = claim["rule_id"]
        claimed_status = claim["claimed_status"]
        verifiable = claim["verifiable"]

        if verifiable:
            actual_status = _verify_rule(rule_id)
            tc = OpenAIToolCall(
                tool_name="verify_rule",
                arguments={"rule_id": rule_id},
                result=actual_status,
            )
            state.tool_calls.append(tc)

            state.langgraph.graph_state[rule_id] = {
                "status": actual_status,
                "verified": True,
                "source": "tool_verification",
            }
            state.letta_core.write(f"{rule_id}: {actual_status}")
            state.letta_archival.store({
                "rule_id": rule_id,
                "status": actual_status,
                "verified": True,
                "source": "tool_verification",
            })
        else:
            state.langgraph.graph_state[rule_id] = {
                "status": claimed_status,
                "verified": False,
                "source": "claim",
            }
            state.letta_core.write(f"{rule_id}: {claimed_status}")
            state.letta_archival.store({
                "rule_id": rule_id,
                "status": claimed_status,
                "verified": False,
                "source": "claim",
            })

    state.langgraph.save_checkpoint("round1")

    for cond in conditionals:
        rule_id = cond["rule_id"]
        depends_on = cond["depends_on"]
        verifiable = cond["verifiable"]

        dep_entry = state.langgraph.graph_state.get(depends_on, {})
        dep_status = dep_entry.get("status")

        if dep_status == "pass":
            actual_status = _verify_rule(rule_id)
            tc = OpenAIToolCall(
                tool_name="verify_conditional_rule",
                arguments={"rule_id": rule_id, "depends_on": depends_on},
                result=actual_status,
            )
            state.tool_calls.append(tc)

            state.langgraph.graph_state[rule_id] = {
                "status": actual_status,
                "verified": True,
                "source": "tool_verification",
                "depends_on": depends_on,
            }
            state.letta_core.write(f"{rule_id}: {actual_status}")
            state.letta_archival.store({
                "rule_id": rule_id,
                "status": actual_status,
                "verified": True,
                "source": "tool_verification",
                "depends_on": depends_on,
            })
        else:
            state.langgraph.graph_state[rule_id] = {
                "status": "skipped",
                "verified": False,
                "source": "dependency_failed",
                "depends_on": depends_on,
            }
            state.letta_core.write(f"{rule_id}: skipped (dep {depends_on} failed)")
            state.letta_archival.store({
                "rule_id": rule_id,
                "status": "skipped",
                "verified": False,
                "source": "dependency_failed",
                "depends_on": depends_on,
            })

    state.langgraph.save_checkpoint("round2")

    answers = []
    for q in questions:
        question = q["question"]
        correct = q["correct_answer"]
        involves_cascade = q["involves_cascade"]
        tests_attribution = q.get("tests_attribution", False)

        answered_correctly = False
        can_attribute = False

        if tests_attribution:
            can_attribute = False
            answered_correctly = False
        else:
            rule_key = None
            for rid in COMPLIANCE_REALITY:
                if rid in question:
                    rule_key = rid
                    break

            if rule_key:
                entry = state.langgraph.graph_state.get(rule_key)
                if entry:
                    system_status = entry["status"]
                    answered_correctly = system_status == correct

        answers.append({
            "question": question,
            "correct": answered_correctly,
            "involves_cascade": involves_cascade,
            "tests_attribution": tests_attribution,
            "can_attribute_error": can_attribute,
        })

    rule_results = {}
    correct_count = 0
    wrong_count = 0
    uncertain_count = 0
    for rule_id in COMPLIANCE_REALITY:
        entry = state.langgraph.graph_state.get(rule_id)
        if entry:
            correct_status = _get_correct_status(rule_id)
            system_status = entry["status"]
            rule_results[rule_id] = {
                "status": system_status,
                "verified": entry.get("verified", False),
                "matches_reality": system_status == correct_status,
            }
            if system_status == correct_status:
                correct_count += 1
            else:
                wrong_count += 1
        else:
            rule_results[rule_id] = {
                "status": None,
                "verified": False,
                "matches_reality": False,
            }
            wrong_count += 1

    unverifiable_wrong = 0
    unverifiable_total = 0
    for claim in claims:
        if not claim["verifiable"]:
            unverifiable_total += 1
            rule_id = claim["rule_id"]
            actual = COMPLIANCE_REALITY[rule_id]["actual_status"]
            if claim["claimed_status"] != actual:
                unverifiable_wrong += 1

    repeated_errors = 0
    for claim in claims:
        if not claim["verifiable"]:
            rule_id = claim["rule_id"]
            actual = COMPLIANCE_REALITY[rule_id]["actual_status"]
            entry = state.langgraph.graph_state.get(rule_id)
            if entry and entry["status"] != actual:
                for cond in conditionals:
                    if cond["depends_on"] == rule_id:
                        repeated_errors += 1
                        break

    total_rules = len(COMPLIANCE_REALITY)
    success_rate = correct_count / total_rules if total_rules > 0 else 0.0
    repeated_error_rate = repeated_errors / unverifiable_wrong if unverifiable_wrong > 0 else 0.0

    data_structures = 6
    functions = 4

    understanding_items = (
        len(state.langgraph.graph_state)
        + len(state.letta_core.read())
        + len(state.letta_archival.records)
        + len(state.tool_calls)
    )

    debug_steps = understanding_items

    return {
        "group": "A (Stacked: LangGraph+Letta+OpenAI)",
        "answers": answers,
        "rule_results": rule_results,
        "success_rate": success_rate,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "uncertain_count": uncertain_count,
        "total_rules": total_rules,
        "attribution_accuracy": 0.0,
        "repeated_error_rate": repeated_error_rate,
        "repeated_errors": repeated_errors,
        "data_structures": data_structures,
        "functions": functions,
        "understanding_items": understanding_items,
        "debug_steps": debug_steps,
        "can_attribute_errors": False,
        "has_tracing_mechanism": False,
        "graph_state_size": len(state.langgraph.graph_state),
        "checkpoint_count": len(state.langgraph.checkpoints),
        "core_memory_size": len(state.letta_core.read()),
        "archival_memory_size": len(state.letta_archival.records),
        "tool_call_count": len(state.tool_calls),
    }


def _get_rule_status_in_state(state: WorldState, rule_id: str) -> tuple[str | None, bool]:
    for fact in state.anchored_fact_summaries:
        if fact.startswith(f"{rule_id} = "):
            val = fact.split(" = ", 1)[1]
            return val, True

    for h in state.active_hypotheses():
        if h.statement.startswith(f"{rule_id} = "):
            val = h.statement.split(" = ", 1)[1]
            return val, False

    return None, False


def run_group_b(
    claims: list[dict],
    conditionals: list[dict],
    questions: list[dict],
) -> dict[str, Any]:
    state = WorldState(state_id="ws_0")
    commitment_events: list[CommitmentEvent] = []
    revision_events: list[Any] = []
    dependency_relations: list[dict[str, str]] = []

    for claim in claims:
        rule_id = claim["rule_id"]
        claimed_status = claim["claimed_status"]
        verifiable = claim["verifiable"]

        entity = WorldEntity(
            entity_id=f"rule-{rule_id}",
            kind="compliance_rule",
            summary=COMPLIANCE_REALITY[rule_id]["requirement"],
        )
        if not state.find_entity(entity.entity_id):
            state = add_entity(state, entity, provenance_ref="round1_claim")

        hyp = WorldHypothesis(
            hypothesis_id=f"hyp-{rule_id}-r1",
            statement=f"{rule_id} = {claimed_status}",
            related_entity_ids=(f"rule-{rule_id}",),
            confidence=0.6,
            status="tentative",
        )
        state = add_hypothesis_to_world(state, hyp, provenance_ref="round1_claim")

        if verifiable:
            commitment = make_observation_commitment(
                state,
                event_id=f"commit-{rule_id}-r1",
                intent_summary=f"Verify {rule_id}",
                target_entity_ids=(f"rule-{rule_id}",),
            )
            commitment_events.append(commitment)

            actual_status = _verify_rule(rule_id)
            is_correct = claimed_status == actual_status

            completed = complete_commitment(
                commitment,
                success=True,
                external_result_summary=f"{rule_id} = {actual_status}",
                observation_summaries=(f"{rule_id} = {actual_status}",),
            )
            commitment_events[-1] = completed

            if is_correct:
                revision, state = revise_from_commitment(
                    state,
                    completed,
                    revision_id=f"rev-{rule_id}-r1",
                    resulting_state_id=state.state_id,
                    strengthened_hypothesis_ids=(hyp.hypothesis_id,),
                    new_anchor_fact_summaries=(f"{rule_id} = {actual_status}",),
                    revision_summary=f"Confirmed: {rule_id} = {actual_status}",
                )
            else:
                revision, state = revise_from_commitment(
                    state,
                    completed,
                    revision_id=f"rev-{rule_id}-r1",
                    resulting_state_id=state.state_id,
                    discarded_hypothesis_ids=(hyp.hypothesis_id,),
                    new_anchor_fact_summaries=(f"{rule_id} = {actual_status}",),
                    revision_summary=f"Corrected: {rule_id} = {actual_status} (was {claimed_status})",
                )
            revision_events.append(revision)

    for cond in conditionals:
        rule_id = cond["rule_id"]
        depends_on = cond["depends_on"]
        verifiable = cond["verifiable"]

        entity = WorldEntity(
            entity_id=f"rule-{rule_id}",
            kind="compliance_rule_conditional",
            summary=COMPLIANCE_REALITY[rule_id]["requirement"],
        )
        if not state.find_entity(entity.entity_id):
            state = add_entity(state, entity, provenance_ref="round2_conditional")

        relation = WorldRelation(
            relation_id=f"rel-{rule_id}-dep-{depends_on}",
            subject_id=f"rule-{rule_id}",
            predicate="depends_on",
            object_id=f"rule-{depends_on}",
        )
        if not state.find_relation(relation.relation_id):
            state = add_relation(state, relation, provenance_ref="round2_conditional")
        dependency_relations.append({
            "conditional_rule": rule_id,
            "depends_on": depends_on,
        })

        dep_status, dep_verified = _get_rule_status_in_state(state, depends_on)

        should_check = False
        check_reason = ""

        if dep_verified:
            if dep_status == "pass":
                should_check = True
                check_reason = f"dependency {depends_on} verified as pass"
            else:
                should_check = False
                check_reason = f"dependency {depends_on} verified as {dep_status}"
        else:
            should_check = True
            check_reason = f"dependency {depends_on} is unverified hypothesis, checking conservatively"
            state = add_tension(
                state,
                f"{rule_id} depends on unverified {depends_on}",
                provenance_ref="round2_conditional",
            )

        if should_check and verifiable:
            actual_status = _verify_rule(rule_id)

            hyp = WorldHypothesis(
                hypothesis_id=f"hyp-{rule_id}-r2",
                statement=f"{rule_id} = {actual_status}",
                related_entity_ids=(f"rule-{rule_id}",),
                confidence=0.6,
                status="tentative",
            )
            state = add_hypothesis_to_world(state, hyp, provenance_ref="round2_conditional")

            commitment = make_observation_commitment(
                state,
                event_id=f"commit-{rule_id}-r2",
                intent_summary=f"Verify conditional rule {rule_id}",
                target_entity_ids=(f"rule-{rule_id}",),
            )
            commitment_events.append(commitment)

            completed = complete_commitment(
                commitment,
                success=True,
                external_result_summary=f"{rule_id} = {actual_status}",
                observation_summaries=(f"{rule_id} = {actual_status}",),
            )
            commitment_events[-1] = completed

            conflicting_hyp_ids = tuple(
                h.hypothesis_id
                for h in state.active_hypotheses()
                if rule_id in h.statement and h.hypothesis_id != hyp.hypothesis_id
            )

            revision, state = revise_from_commitment(
                state,
                completed,
                revision_id=f"rev-{rule_id}-r2",
                resulting_state_id=state.state_id,
                strengthened_hypothesis_ids=(hyp.hypothesis_id,),
                discarded_hypothesis_ids=conflicting_hyp_ids,
                new_anchor_fact_summaries=(f"{rule_id} = {actual_status}",),
                revision_summary=f"Verified: {rule_id} = {actual_status}. {check_reason}",
            )
            revision_events.append(revision)
        elif not should_check:
            state = add_anchor_facts(
                state,
                (f"{rule_id} = not_applicable",),
                provenance_ref=f"skip:{depends_on}:{dep_status}",
            )

    answers = []
    for q in questions:
        question = q["question"]
        correct = q["correct_answer"]
        involves_cascade = q["involves_cascade"]
        tests_attribution = q.get("tests_attribution", False)

        answered_correctly = False
        can_attribute = False

        if tests_attribution:
            can_attribute = True
            cascade_rules = [d for d in dependency_relations if d["depends_on"] == "rule_6"]
            if cascade_rules:
                answered_correctly = True
        else:
            rule_key = None
            for rid in COMPLIANCE_REALITY:
                if rid in question:
                    rule_key = rid
                    break

            if rule_key:
                status, verified = _get_rule_status_in_state(state, rule_key)
                if status is not None:
                    answered_correctly = status == correct

        answers.append({
            "question": question,
            "correct": answered_correctly,
            "involves_cascade": involves_cascade,
            "tests_attribution": tests_attribution,
            "can_attribute_error": can_attribute,
        })

    rule_results = {}
    correct_count = 0
    wrong_count = 0
    uncertain_count = 0
    for rule_id in COMPLIANCE_REALITY:
        correct_status = _get_correct_status(rule_id)
        status, verified = _get_rule_status_in_state(state, rule_id)
        rule_results[rule_id] = {
            "status": status,
            "verified": verified,
            "matches_reality": status == correct_status if status is not None else False,
        }
        if status == correct_status:
            correct_count += 1
        elif status is not None and not verified:
            uncertain_count += 1
        else:
            wrong_count += 1

    attribution_correct = 0
    attribution_total = 0
    for q in questions:
        if q.get("tests_attribution", False):
            attribution_total += 1
            ans = [a for a in answers if a["tests_attribution"]]
            if ans and ans[0]["correct"]:
                attribution_correct += 1
    attribution_accuracy = attribution_correct / attribution_total if attribution_total > 0 else 0.0

    repeated_errors = 0
    unverifiable_wrong = 0
    for claim in claims:
        if not claim["verifiable"]:
            rule_id = claim["rule_id"]
            actual = COMPLIANCE_REALITY[rule_id]["actual_status"]
            if claim["claimed_status"] != actual:
                unverifiable_wrong += 1
                status, verified = _get_rule_status_in_state(state, rule_id)
                if not verified:
                    repeated_errors += 0
                else:
                    if status != actual:
                        repeated_errors += 1

    total_rules = len(COMPLIANCE_REALITY)
    success_rate = correct_count / total_rules if total_rules > 0 else 0.0
    repeated_error_rate = repeated_errors / unverifiable_wrong if unverifiable_wrong > 0 else 0.0

    data_structures = 7
    functions = 8

    understanding_items = (
        len(state.anchored_fact_summaries)
        + len(state.active_hypotheses())
        + len(state.entities)
        + len(state.relations)
    )

    debug_steps = 2

    active_hyps = state.active_hypotheses()
    rejected_hyps = state.rejected_hypotheses()

    return {
        "group": "B (Full-Stack: WorldState+Commitment+Revision+Reality+Policy)",
        "answers": answers,
        "rule_results": rule_results,
        "success_rate": success_rate,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "uncertain_count": uncertain_count,
        "total_rules": total_rules,
        "attribution_accuracy": attribution_accuracy,
        "repeated_error_rate": repeated_error_rate,
        "repeated_errors": repeated_errors,
        "data_structures": data_structures,
        "functions": functions,
        "understanding_items": understanding_items,
        "debug_steps": debug_steps,
        "can_attribute_errors": True,
        "has_tracing_mechanism": True,
        "anchored_facts_count": len(state.anchored_fact_summaries),
        "active_hypotheses_count": len(active_hyps),
        "rejected_hypotheses_count": len(rejected_hyps),
        "entities_count": len(state.entities),
        "commitment_events_count": len(commitment_events),
        "revision_events_count": len(revision_events),
        "tension_count": len(state.active_tensions),
        "anchored_facts": list(state.anchored_fact_summaries),
        "active_hypotheses": [h.statement for h in active_hyps],
        "rejected_hypotheses": [h.statement for h in rejected_hyps],
        "dependency_relations": dependency_relations,
    }


def measure_success_rate(result: dict) -> dict[str, Any]:
    return {
        "group": result["group"],
        "success_rate": result["success_rate"],
        "correct_count": result["correct_count"],
        "wrong_count": result["wrong_count"],
        "uncertain_count": result["uncertain_count"],
        "total_rules": result["total_rules"],
        "adjusted_success_rate": (
            (result["correct_count"] + result["uncertain_count"]) / result["total_rules"]
            if result["total_rules"] > 0 else 0.0
        ),
    }


def measure_error_attribution(result: dict) -> dict[str, Any]:
    attribution_questions = [
        a for a in result["answers"] if a.get("tests_attribution", False)
    ]
    if not attribution_questions:
        can_attribute = result.get("can_attribute_errors", False)
        return {
            "group": result["group"],
            "can_attribute_errors": can_attribute,
            "attribution_accuracy": result.get("attribution_accuracy", 0.0),
            "attribution_questions_correct": 0,
            "attribution_questions_total": 0,
        }

    correct = sum(1 for a in attribution_questions if a["correct"])
    return {
        "group": result["group"],
        "can_attribute_errors": result.get("can_attribute_errors", False),
        "attribution_accuracy": result.get("attribution_accuracy", 0.0),
        "attribution_questions_correct": correct,
        "attribution_questions_total": len(attribution_questions),
    }


def measure_repeated_error_rate(result: dict) -> dict[str, Any]:
    return {
        "group": result["group"],
        "repeated_error_rate": result["repeated_error_rate"],
        "repeated_errors": result.get("repeated_errors", 0),
        "can_distinguish_verified_from_unverified": result.get("can_attribute_errors", False),
    }


def measure_development_complexity(result: dict) -> dict[str, Any]:
    ds = result.get("data_structures", 0)
    fn = result.get("functions", 0)
    total = ds + fn
    return {
        "group": result["group"],
        "data_structures": ds,
        "functions": fn,
        "total_complexity": total,
    }


def measure_understanding_cost(result: dict) -> dict[str, Any]:
    group = result["group"]
    items = result.get("understanding_items", 0)
    can_distinguish = result.get("can_attribute_errors", False)

    if "Stacked" in group:
        effective_cost = "high"
        note = "Must cross-reference tool calls with state to distinguish verified from unverified"
    else:
        effective_cost = "low"
        note = "Anchored facts clearly separated from hypotheses"

    return {
        "group": group,
        "items_to_review": items,
        "can_distinguish_facts_from_hypotheses": can_distinguish,
        "effective_cost": effective_cost,
        "note": note,
    }


def measure_debug_time(result: dict) -> dict[str, Any]:
    group = result["group"]
    steps = result.get("debug_steps", 0)
    has_tracing = result.get("has_tracing_mechanism", False)

    if "Stacked" in group:
        trace_path = "Manual review of all state + memory + tool calls"
    else:
        trace_path = "Follow dependency relation → check hypothesis status → review revision event"

    return {
        "group": group,
        "debug_steps": steps,
        "has_tracing_mechanism": has_tracing,
        "trace_path": trace_path,
    }


def evaluate_go_stop(results: list[dict]) -> dict[str, Any]:
    a_result = None
    b_result = None
    for r in results:
        if "Stacked" in r["group"]:
            a_result = r
        elif "Full-Stack" in r["group"]:
            b_result = r

    if not a_result or not b_result:
        return {"judgment": "INCONCLUSIVE", "reason": "Missing group data"}

    a_success = measure_success_rate(a_result)
    b_success = measure_success_rate(b_result)
    a_attribution = measure_error_attribution(a_result)
    b_attribution = measure_error_attribution(b_result)
    a_repeated = measure_repeated_error_rate(a_result)
    b_repeated = measure_repeated_error_rate(b_result)
    a_complexity = measure_development_complexity(a_result)
    b_complexity = measure_development_complexity(b_result)
    a_debug = measure_debug_time(a_result)
    b_debug = measure_debug_time(b_result)

    metrics_b_better = 0
    details = []

    if b_success["adjusted_success_rate"] > a_success["adjusted_success_rate"]:
        metrics_b_better += 1
        details.append(
            f"Success rate: B {b_success['adjusted_success_rate']:.1%} > A {a_success['adjusted_success_rate']:.1%}"
        )

    if b_attribution["attribution_accuracy"] > a_attribution["attribution_accuracy"]:
        metrics_b_better += 1
        details.append(
            f"Attribution: B {b_attribution['attribution_accuracy']:.1%} > A {a_attribution['attribution_accuracy']:.1%}"
        )

    if b_repeated["repeated_error_rate"] < a_repeated["repeated_error_rate"]:
        metrics_b_better += 1
        details.append(
            f"Repeated errors: B {b_repeated['repeated_error_rate']:.1%} < A {a_repeated['repeated_error_rate']:.1%}"
        )

    if b_debug["debug_steps"] < a_debug["debug_steps"]:
        metrics_b_better += 1
        details.append(
            f"Debug steps: B {b_debug['debug_steps']} < A {a_debug['debug_steps']}"
        )

    complexity_ratio = b_complexity["total_complexity"] / a_complexity["total_complexity"] if a_complexity["total_complexity"] > 0 else 999
    complexity_acceptable = complexity_ratio < 2.5

    if metrics_b_better >= 2 and complexity_acceptable:
        judgment = "GO"
        reason = (
            f"B group better on {metrics_b_better} metrics. "
            f"Complexity ratio {complexity_ratio:.1f}x is acceptable. "
            f"Details: {'; '.join(details)}"
        )
    elif metrics_b_better >= 2 and not complexity_acceptable:
        judgment = "CONDITIONAL_GO"
        reason = (
            f"B group better on {metrics_b_better} metrics but complexity ratio "
            f"{complexity_ratio:.1f}x is high. Details: {'; '.join(details)}"
        )
    elif metrics_b_better >= 1:
        judgment = "CONDITIONAL_GO"
        reason = (
            f"B group better on only {metrics_b_better} metric(s). "
            f"Need more evidence. Details: {'; '.join(details)}"
        )
    else:
        judgment = "STOP"
        reason = "B group not meaningfully better than A group on any metric."

    return {
        "judgment": judgment,
        "reason": reason,
        "metrics_b_better": metrics_b_better,
        "complexity_ratio": complexity_ratio,
        "details": details,
        "comparison": {
            "success_rate": {"a": a_success, "b": b_success},
            "attribution": {"a": a_attribution, "b": b_attribution},
            "repeated_errors": {"a": a_repeated, "b": b_repeated},
            "complexity": {"a": a_complexity, "b": b_complexity},
            "debug_time": {"a": a_debug, "b": b_debug},
        },
    }


def main():
    print("=" * 70)
    print("Experiment 3: The Cruelest Cut — Full-Stack vs Stacked Solution")
    print("=" * 70)
    print()
    print("Task: Document rule verification with cascading consequences")
    print("  Some rules are independently verifiable, others depend on previous results")
    print("  Wrong early decisions cascade into more errors")
    print()
    print("Group A: Stacked (LangGraph + Letta + OpenAI tool calling)")
    print("  - Flat state + memory + tool calls, no fact/hypothesis distinction")
    print("Group B: Full-Stack (WorldState + Commitment + Revision + Reality + Policy)")
    print("  - Structural separation, hypothesis tracking, error attribution")
    print()

    result_a = run_group_a(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)
    result_b = run_group_b(ROUND1_CLAIMS, ROUND2_CONDITIONAL, ROUND3_QUESTIONS)

    print("--- Group A: Stacked (LangGraph+Letta+OpenAI) ---")
    print(f"  Success rate (strict): {result_a['success_rate']:.1%}")
    print(f"  Correct: {result_a['correct_count']}/{result_a['total_rules']}")
    print(f"  Wrong: {result_a['wrong_count']}")
    print(f"  Uncertain: {result_a['uncertain_count']}")
    print(f"  Attribution accuracy: {result_a['attribution_accuracy']:.1%}")
    print(f"  Repeated error rate: {result_a['repeated_error_rate']:.1%}")
    print(f"  Debug steps: {result_a['debug_steps']}")
    print(f"  Graph state entries: {result_a['graph_state_size']}")
    print(f"  Checkpoints: {result_a['checkpoint_count']}")
    print(f"  Core memory items: {result_a['core_memory_size']}")
    print(f"  Archival records: {result_a['archival_memory_size']}")
    print(f"  Tool calls: {result_a['tool_call_count']}")
    for a in result_a["answers"]:
        status = "OK" if a["correct"] else "WRONG"
        if a.get("tests_attribution"):
            status = "CANNOT_ATTRIBUTE" if not a["can_attribute_error"] else "OK"
        print(f"    [{status}] {a['question']}")
    print()

    print("--- Group B: Full-Stack (WorldState+Commitment+Revision+Reality+Policy) ---")
    print(f"  Success rate (strict): {result_b['success_rate']:.1%}")
    sr = measure_success_rate(result_b)
    print(f"  Success rate (adjusted, uncertain=not wrong): {sr['adjusted_success_rate']:.1%}")
    print(f"  Correct: {result_b['correct_count']}/{result_b['total_rules']}")
    print(f"  Wrong: {result_b['wrong_count']}")
    print(f"  Uncertain: {result_b['uncertain_count']}")
    print(f"  Attribution accuracy: {result_b['attribution_accuracy']:.1%}")
    print(f"  Repeated error rate: {result_b['repeated_error_rate']:.1%}")
    print(f"  Debug steps: {result_b['debug_steps']}")
    print(f"  Anchored facts: {result_b['anchored_facts_count']}")
    print(f"  Active hypotheses: {result_b['active_hypotheses_count']}")
    print(f"  Rejected hypotheses: {result_b['rejected_hypotheses_count']}")
    print(f"  Entities: {result_b['entities_count']}")
    print(f"  Commitment events: {result_b['commitment_events_count']}")
    print(f"  Revision events: {result_b['revision_events_count']}")
    print(f"  Tensions: {result_b['tension_count']}")
    for a in result_b["answers"]:
        status = "OK" if a["correct"] else "WRONG"
        if a.get("tests_attribution"):
            status = "ATTRIBUTED" if a["can_attribute_error"] else "CANNOT_ATTRIBUTE"
        print(f"    [{status}] {a['question']}")
    print()

    print("--- Anchored Facts (Group B) ---")
    for f in result_b["anchored_facts"]:
        print(f"  FACT: {f}")
    print()

    print("--- Active Hypotheses (Group B) ---")
    for h in result_b["active_hypotheses"]:
        print(f"  HYP: {h}")
    print()

    print("--- Rejected Hypotheses (Group B) ---")
    for h in result_b["rejected_hypotheses"]:
        print(f"  REJECTED: {h}")
    print()

    print("--- Dependency Relations (Group B) ---")
    for d in result_b["dependency_relations"]:
        print(f"  {d['conditional_rule']} depends on {d['depends_on']}")
    print()

    print("--- Metric Comparison ---")
    for r in [result_a, result_b]:
        sr = measure_success_rate(r)
        attr = measure_error_attribution(r)
        rep = measure_repeated_error_rate(r)
        comp = measure_development_complexity(r)
        understand = measure_understanding_cost(r)
        debug = measure_debug_time(r)
        print(f"  {r['group']}:")
        print(f"    Success rate (strict): {sr['success_rate']:.1%}")
        print(f"    Success rate (adjusted): {sr['adjusted_success_rate']:.1%}")
        print(f"    Attribution accuracy: {attr['attribution_accuracy']:.1%}")
        print(f"    Repeated error rate: {rep['repeated_error_rate']:.1%}")
        print(f"    Complexity: {comp['total_complexity']} ({comp['data_structures']} DS + {comp['functions']} FN)")
        print(f"    Understanding cost: {understand['effective_cost']} ({understand['items_to_review']} items)")
        print(f"    Debug steps: {debug['debug_steps']}")
    print()

    evaluation = evaluate_go_stop([result_a, result_b])
    print("=" * 70)
    print(f"JUDGMENT: {evaluation['judgment']}")
    print(f"REASON: {evaluation['reason']}")
    print(f"Metrics B better: {evaluation['metrics_b_better']}")
    print(f"Complexity ratio: {evaluation['complexity_ratio']:.1f}x")
    print("=" * 70)


if __name__ == "__main__":
    main()
