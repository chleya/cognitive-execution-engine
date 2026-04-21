"""Experiment 1: Does Reality Feedback Actually Reduce Repeated Errors?

Compares two groups:
  Group A: Plain tool-calling baseline (no hypothesis/fact distinction)
  Group C: Hypothesis + AnchoredFact + commitment_kind structure

Round 1: Both groups verify claims against REALITY (simulated tool call).
Round 2: REALITY is no longer accessible. The system must rely on memory.
  - Group A: Stores flat results but doesn't consult them → accepts wrong claims
  - Group C: Checks anchored_facts → correctly rejects previously-seen wrong claims

The key metric: how many wrong claims does each group accept as correct in round 2?
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cee_core.world_state import (
    WorldState,
    add_hypothesis_to_world,
    update_hypothesis_status,
    add_anchor_facts,
)
from cee_core.world_schema import WorldHypothesis

REALITY: dict[str, int] = {
    "python_release_year": 1991,
    "linux_release_year": 1991,
    "rust_release_year": 2015,
    "go_release_year": 2009,
    "swift_release_year": 2014,
    "kotlin_release_year": 2011,
    "typescript_release_year": 2012,
    "java_release_year": 1995,
}

Claim = tuple[str, int, bool]

CLAIMS_ROUND_1: list[Claim] = [
    ("python_release_year", 1991, True),
    ("linux_release_year", 1994, False),
    ("rust_release_year", 2013, False),
    ("go_release_year", 2009, True),
    ("swift_release_year", 2016, False),
]

CLAIMS_ROUND_2: list[Claim] = [
    ("linux_release_year", 1994, False),
    ("rust_release_year", 2013, False),
    ("swift_release_year", 2016, False),
    ("kotlin_release_year", 2016, False),
    ("typescript_release_year", 2014, False),
]


def run_group_a_round1(claims: list[Claim], beliefs: dict | None = None) -> tuple[list[dict], dict]:
    """Group A Round 1: verify claims against REALITY, store flat results."""
    if beliefs is None:
        beliefs = {}

    results = []
    for topic, claimed_value, is_correct in claims:
        actual_value = REALITY[topic]
        verified = claimed_value == actual_value

        beliefs[f"verified_{topic}"] = verified
        beliefs[f"actual_{topic}"] = actual_value

        results.append({
            "topic": topic,
            "claimed": claimed_value,
            "actual": actual_value,
            "is_correct": is_correct,
            "verified": verified,
        })

    return results, beliefs


def run_group_a_round2(claims: list[Claim], beliefs: dict) -> tuple[list[dict], dict]:
    """Group A Round 2: NO reality access. Accepts claims at face value.

    Simulates a plain tool-calling system that stores results but never
    consults past verification when evaluating new claims.
    """
    results = []
    for topic, claimed_value, is_correct in claims:
        accepted = True

        results.append({
            "topic": topic,
            "claimed": claimed_value,
            "actual": REALITY[topic],
            "is_correct": is_correct,
            "accepted": accepted,
            "accepted_wrong_claim": accepted and not is_correct,
        })

    return results, beliefs


def run_group_c(claims: list[Claim], state: WorldState | None = None) -> tuple[list[dict], WorldState]:
    """Group C Round 1: form hypotheses, verify against REALITY, anchor facts."""
    if state is None:
        state = WorldState(state_id="ws_0")

    results = []
    for topic, claimed_value, is_correct in claims:
        hyp = WorldHypothesis(
            hypothesis_id=f"hyp-{topic}",
            statement=f"{topic} = {claimed_value}",
            confidence=0.6,
            status="tentative",
        )
        state = add_hypothesis_to_world(state, hyp)

        actual_value = REALITY[topic]
        verified = claimed_value == actual_value
        fact_summary = f"{topic} = {actual_value}"

        if verified:
            state = update_hypothesis_status(
                state, hyp.hypothesis_id, "active", 1.0,
                provenance_ref="reality_verification",
            )
            state = add_anchor_facts(
                state, (fact_summary,),
                provenance_ref="reality_verification",
            )
        else:
            state = update_hypothesis_status(
                state, hyp.hypothesis_id, "rejected", 0.0,
                provenance_ref="reality_verification",
            )
            state = add_anchor_facts(
                state, (fact_summary,),
                provenance_ref="reality_verification",
            )

        results.append({
            "topic": topic,
            "claimed": claimed_value,
            "actual": actual_value,
            "is_correct": is_correct,
            "verified": verified,
        })

    return results, state


def run_group_c_with_memory(claims: list[Claim], state: WorldState) -> tuple[list[dict], WorldState]:
    """Group C Round 2: NO reality access. Checks anchored_facts instead.

    When an anchored fact exists for a topic, the system uses it to
    correctly reject wrong claims without re-verifying against reality.
    """
    results = []
    for topic, claimed_value, is_correct in claims:
        known_fact_summary = None
        for s in state.anchored_fact_summaries:
            if topic in s:
                known_fact_summary = s
                break

        if known_fact_summary:
            known_value = int(known_fact_summary.split(" = ")[1])
            accepted = claimed_value == known_value

            results.append({
                "topic": topic,
                "claimed": claimed_value,
                "actual": REALITY[topic],
                "is_correct": is_correct,
                "accepted": accepted,
                "accepted_wrong_claim": accepted and not is_correct,
                "used_anchored_fact": True,
            })
        else:
            accepted = True

            hyp = WorldHypothesis(
                hypothesis_id=f"hyp-{topic}-r2",
                statement=f"{topic} = {claimed_value}",
                confidence=0.6,
                status="tentative",
            )
            state = add_hypothesis_to_world(state, hyp)

            results.append({
                "topic": topic,
                "claimed": claimed_value,
                "actual": REALITY[topic],
                "is_correct": is_correct,
                "accepted": accepted,
                "accepted_wrong_claim": accepted and not is_correct,
                "used_anchored_fact": False,
            })

    return results, state


def measure_repeated_errors(round1_results: list[dict], round2_results: list[dict]) -> tuple[int, int]:
    """Count how many errors from round 1 are repeated in round 2.

    A 'repeated error' is a topic that was wrong in round 1 and the
    system still accepts the wrong claim in round 2.
    """
    round1_errors = {r["topic"] for r in round1_results if not r["is_correct"]}
    round2_accepted_wrong = {r["topic"] for r in round2_results if r.get("accepted_wrong_claim")}
    repeated = round1_errors & round2_accepted_wrong
    return len(repeated), len(round1_errors)


def judge_experiment(a_repeated: int, c_repeated: int) -> str:
    if c_repeated == 0 and a_repeated > 0:
        return "GO: C group eliminates all repeated errors"
    if c_repeated < a_repeated and (a_repeated - c_repeated) / max(a_repeated, 1) >= 0.2:
        return "GO: C group reduces repeated errors by >=20%"
    return "STOP: C group does not significantly reduce repeated errors"


def main() -> None:
    print("=" * 70)
    print("  Experiment 1: Does Reality Feedback Actually Reduce Repeated Errors?")
    print("=" * 70)

    a_r1_results, a_beliefs = run_group_a_round1(CLAIMS_ROUND_1)
    a_r2_results, _ = run_group_a_round2(CLAIMS_ROUND_2, a_beliefs)

    c_r1_results, c_state = run_group_c(CLAIMS_ROUND_1)
    c_r2_results, c_state = run_group_c_with_memory(CLAIMS_ROUND_2, c_state)

    a_r1_wrong = sum(1 for r in a_r1_results if not r["is_correct"])
    a_r2_accepted_wrong = sum(1 for r in a_r2_results if r.get("accepted_wrong_claim"))
    a_repeated_count, _ = measure_repeated_errors(a_r1_results, a_r2_results)

    c_r1_wrong = sum(1 for r in c_r1_results if not r["is_correct"])
    c_r2_accepted_wrong = sum(1 for r in c_r2_results if r.get("accepted_wrong_claim"))
    c_repeated_count, _ = measure_repeated_errors(c_r1_results, c_r2_results)
    c_used_memory = sum(1 for r in c_r2_results if r.get("used_anchored_fact"))

    print(f"\n  Round 1 (initial verification against REALITY):")
    print(f"    Group A wrong claims: {a_r1_wrong}")
    print(f"    Group C wrong claims: {c_r1_wrong}")

    print(f"\n  Round 2 (NO reality access, must rely on memory):")
    print(f"    Group A accepted wrong claims: {a_r2_accepted_wrong}")
    print(f"    Group C accepted wrong claims: {c_r2_accepted_wrong}")
    print(f"    Group A repeated errors: {a_repeated_count}")
    print(f"    Group C repeated errors: {c_repeated_count}")
    print(f"    Group C used anchored_facts: {c_used_memory}")

    if a_repeated_count > 0:
        reduction = (a_repeated_count - c_repeated_count) / a_repeated_count * 100
        print(f"\n  Repeated error reduction: {reduction:.1f}%")

    verdict = judge_experiment(a_repeated_count, c_repeated_count)
    print(f"\n  Judgment:")
    print(f"    -> {verdict}")

    print(f"\n  Explainability:")
    rejected = c_state.rejected_hypotheses()
    anchored = c_state.anchored_fact_summaries
    print(f"    Total hypotheses: {len(c_state.hypotheses)}")
    print(f"    Rejected hypotheses: {len(rejected)}")
    print(f"    Anchored facts: {len(anchored)}")

    for h in rejected:
        print(f"    Rejected: {h.statement} (status={h.status}, confidence={h.confidence})")
    for s in anchored:
        print(f"    Anchored: {s}")

    print()


if __name__ == "__main__":
    main()
