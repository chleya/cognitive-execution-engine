"""Common sense cognition through physics-inspired formulas.

Common sense is what the system knows without needing evidence. In physics,
this maps to conservation laws (what doesn't change), ground states
(default configurations), and thermodynamic principles (how uncertainty
evolves).

Five principles:

1. Conservation Law (守恒律):
   Certain beliefs are invariant across all domains and sessions.
   They are conserved quantities. If a belief has survived N independent
   verifications, its conservation strength is N. Conservation law:
   d(invariant_belief)/dt = 0 unless contradicted by direct evidence.

2. Ground State (基态):
   The ground state is the minimum-energy default configuration.
   Beliefs in the ground state require zero evidence (they are axioms).
   All other beliefs are excitations above the ground state.
   E(belief) = -log(confidence) measures excitation energy.
   Ground state: E = 0 (confidence = 1.0, axiomatic).

3. Second Law (熵增律):
   Without new evidence injection, belief entropy only increases.
   S = -sum(p * log(p)) over belief confidence distribution.
   dS/dt >= 0 when no new observations arrive.
   This means: stale beliefs become less certain over time.

4. Equipartition (能均分):
   When evidence is absent, uncertainty distributes equally across
   all unknown dimensions. If there are N unknown sections, each
   gets prior confidence 1/N. This prevents overconfidence in
   unexplored areas.

5. Uncertainty Principle (测不准):
   There is a fundamental limit on simultaneously knowing a belief's
   precision and the rate of evidence change. Delta_precision *
   Delta_evidence_rate >= h/2, where h is the system's evidence
   quantum. A belief can be precise (high confidence) or responsive
   (quickly updated) but not both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .state import State


@dataclass(frozen=True)
class ConservationLawResult:
    """Result of checking conservation law for invariant beliefs."""

    invariant_count: int
    total_beliefs: int
    conservation_strength: float
    violated: tuple[str, ...]
    evidence: str


def check_conservation_law(
    current_state: State,
    previous_state: State | None = None,
    min_verifications: int = 2,
) -> ConservationLawResult:
    """Check that invariant beliefs are conserved across state transitions.

    A belief is invariant if it has evidence_count >= min_verifications.
    Conservation law: invariant beliefs must not disappear or lose
    confidence between state transitions.

    d(invariant_belief)/dt = 0 unless contradicted by direct evidence.
    """

    current_beliefs = current_state.beliefs
    invariants: dict[str, dict[str, object]] = {}
    violated: list[str] = []

    for key, value in current_beliefs.items():
        if isinstance(value, dict):
            evidence_count = value.get("evidence_count")
            if isinstance(evidence_count, (int, float)) and int(evidence_count) >= min_verifications:
                invariants[key] = value

    if previous_state is not None:
        prev_beliefs = previous_state.beliefs
        prev_invariants: dict[str, dict[str, object]] = {}
        for key, value in prev_beliefs.items():
            if isinstance(value, dict):
                evidence_count = value.get("evidence_count")
                if isinstance(evidence_count, (int, float)) and int(evidence_count) >= min_verifications:
                    prev_invariants[key] = value

        for key in prev_invariants:
            if key not in current_beliefs:
                violated.append(f"{key}: invariant belief disappeared")
                continue
            curr_value = current_beliefs[key]
            if isinstance(curr_value, dict):
                prev_conf = prev_invariants[key].get("confidence", 0)
                curr_conf = curr_value.get("confidence", 0)
                if isinstance(prev_conf, (int, float)) and isinstance(curr_conf, (int, float)):
                    if float(curr_conf) < float(prev_conf) - 0.01:
                        violated.append(
                            f"{key}: confidence dropped from "
                            f"{float(prev_conf):.2f} to {float(curr_conf):.2f}"
                        )

    total = len(current_beliefs)
    strength = len(invariants) / total if total > 0 else 0.0

    return ConservationLawResult(
        invariant_count=len(invariants),
        total_beliefs=total,
        conservation_strength=strength,
        violated=tuple(violated),
        evidence=(
            f"invariants={len(invariants)}/{total}, "
            f"strength={strength:.2f}, "
            f"violations={len(violated)}"
        ),
    )


@dataclass(frozen=True)
class GroundStateResult:
    """Result of computing the ground state energy of beliefs.

    Ground state: E = 0 (confidence = 1.0, axiomatic).
    Excitation: E = -log(confidence).
    Lower energy = more stable = closer to common sense.
    """

    total_energy: float
    ground_state_count: int
    excited_count: int
    average_energy: float
    evidence: str


def compute_ground_state(
    state: State,
    ground_confidence: float = 0.95,
) -> GroundStateResult:
    """Compute the ground state energy of the belief system.

    E(belief) = -log2(confidence)
    Ground state: E = 0 (confidence = 1.0)
    A belief is in the ground state if confidence >= ground_confidence.

    Common sense = ground state beliefs. They require zero external
    energy (no approval) because they are axiomatic.
    """

    beliefs = state.beliefs
    total_energy = 0.0
    ground_count = 0
    excited_count = 0

    for _key, value in beliefs.items():
        if isinstance(value, dict):
            conf = value.get("confidence")
            if isinstance(conf, (int, float)) and float(conf) > 0:
                energy = -math.log2(float(conf))
                total_energy += energy
                if float(conf) >= ground_confidence:
                    ground_count += 1
                else:
                    excited_count += 1

    count = ground_count + excited_count
    average = total_energy / count if count > 0 else 0.0

    return GroundStateResult(
        total_energy=round(total_energy, 4),
        ground_state_count=ground_count,
        excited_count=excited_count,
        average_energy=round(average, 4),
        evidence=(
            f"E_total={total_energy:.2f}, "
            f"ground={ground_count}, excited={excited_count}, "
            f"E_avg={average:.2f}"
        ),
    )


@dataclass(frozen=True)
class EntropyResult:
    """Result of computing belief entropy.

    S = -sum(p * log2(p)) where p = belief confidence.
    Second law: dS/dt >= 0 without new evidence.
    Stale beliefs become less certain over time.
    """

    entropy: float
    max_entropy: float
    normalized_entropy: float
    increasing: bool | None
    evidence: str


def compute_belief_entropy(
    current_state: State,
    previous_state: State | None = None,
) -> EntropyResult:
    """Compute the entropy of the belief distribution.

    S = -sum(p_i * log2(p_i)) for each belief confidence p_i.
    Maximum entropy = log2(N) when all beliefs have equal confidence.

    If previous state is provided, checks whether entropy is increasing
    (second law: without new evidence, entropy only increases).
    """

    beliefs = current_state.beliefs
    confidences: list[float] = []

    for _key, value in beliefs.items():
        if isinstance(value, dict):
            conf = value.get("confidence")
            if isinstance(conf, (int, float)) and 0 < float(conf) <= 1:
                confidences.append(float(conf))

    if not confidences:
        return EntropyResult(
            entropy=0.0,
            max_entropy=0.0,
            normalized_entropy=0.0,
            increasing=None,
            evidence="no beliefs with confidence values",
        )

    entropy = -sum(p * math.log2(p) for p in confidences if p > 0)
    max_entropy = math.log2(len(confidences)) if len(confidences) > 1 else 1.0
    normalized = entropy / max_entropy if max_entropy > 0 else 0.0

    increasing = None
    if previous_state is not None:
        prev_result = compute_belief_entropy(previous_state)
        increasing = entropy >= prev_result.entropy - 1e-10

    return EntropyResult(
        entropy=round(entropy, 4),
        max_entropy=round(max_entropy, 4),
        normalized_entropy=round(normalized, 4),
        increasing=increasing,
        evidence=(
            f"S={entropy:.4f}, "
            f"S_max={max_entropy:.4f}, "
            f"S_norm={normalized:.2f}"
        ),
    )


@dataclass(frozen=True)
class EquipartitionResult:
    """Result of checking equipartition of uncertainty.

    When evidence is absent, uncertainty distributes equally.
    Each unknown section gets prior confidence 1/N.
    Overconfidence in unexplored areas is detected.
    """

    known_sections: int
    unknown_sections: int
    total_sections: int
    max_prior_confidence: float
    overconfidence_detected: bool
    evidence: str


_KNOWN_STATE_SECTIONS = {"memory", "goals", "beliefs", "self_model", "domain_data", "tool_affordances"}


def check_equipartition(
    state: State,
    confidence_threshold: float = 0.5,
) -> EquipartitionResult:
    """Check that uncertainty is distributed according to equipartition.

    For sections without beliefs or with low-confidence beliefs, the
    prior confidence should be 1/N where N is the number of sections.
    Overconfidence in an unknown section violates equipartition.
    """

    known = 0
    unknown = 0
    max_prior = 0.0
    overconfidence = False

    for section in _KNOWN_STATE_SECTIONS:
        section_data = getattr(state, section, None)
        if section_data is None:
            unknown += 1
            continue

        if not section_data:
            unknown += 1
            continue

        if section == "beliefs":
            has_high_confidence = False
            for _key, value in section_data.items():
                if isinstance(value, dict):
                    conf = value.get("confidence")
                    if isinstance(conf, (int, float)) and float(conf) >= confidence_threshold:
                        has_high_confidence = True
                        break
            if has_high_confidence:
                known += 1
            else:
                unknown += 1
        else:
            known += 1

    total = known + unknown
    prior = 1.0 / total if total > 0 else 0.0

    for section in _KNOWN_STATE_SECTIONS:
        section_data = getattr(state, section, None)
        if section_data and not section_data:
            if prior > 0 and prior < confidence_threshold:
                overconfidence = True
                max_prior = max(max_prior, prior)
                break

    return EquipartitionResult(
        known_sections=known,
        unknown_sections=unknown,
        total_sections=total,
        max_prior_confidence=round(prior, 4),
        overconfidence_detected=overconfidence,
        evidence=(
            f"known={known}, unknown={unknown}, "
            f"prior=1/{total}={prior:.4f}"
        ),
    )


@dataclass(frozen=True)
class UncertaintyPrincipleResult:
    """Result of checking the uncertainty principle.

    Delta_precision * Delta_evidence_rate >= h/2
    A belief can be precise OR responsive, but not both.
    Precision = confidence (how certain we are).
    Evidence_rate = how quickly evidence changes (volatility).
    h = evidence quantum (minimum evidence unit).
    """

    belief_key: str
    precision: float
    evidence_rate: float
    product: float
    evidence_quantum: float
    principle_satisfied: bool
    evidence: str


def check_uncertainty_principle(
    state: State,
    belief_key: str,
    evidence_quantum: float = 0.1,
    previous_evidence_count: int | None = None,
) -> UncertaintyPrincipleResult | None:
    """Check the uncertainty principle for a specific belief.

    Delta_precision * Delta_evidence_rate >= h/2

    precision = 1 - confidence (uncertainty in belief value)
    evidence_rate = rate of evidence change
    h = evidence_quantum (minimum evidence unit)

    If previous_evidence_count is provided, evidence_rate is computed
    as the change in evidence count. Otherwise, evidence_rate is
    estimated from the reciprocal of evidence_count.
    """

    belief_value = state.beliefs.get(belief_key)
    if not isinstance(belief_value, dict):
        return None

    confidence = belief_value.get("confidence")
    if not isinstance(confidence, (int, float)):
        return None

    evidence_count = belief_value.get("evidence_count")
    if not isinstance(evidence_count, (int, float)):
        evidence_count = 1

    precision = 1.0 - float(confidence)

    if previous_evidence_count is not None:
        evidence_rate = abs(int(evidence_count) - previous_evidence_count)
    else:
        evidence_rate = 1.0 / max(int(evidence_count), 1)

    product = precision * evidence_rate
    threshold = evidence_quantum / 2.0
    satisfied = product >= threshold or precision < threshold

    return UncertaintyPrincipleResult(
        belief_key=belief_key,
        precision=round(precision, 4),
        evidence_rate=round(evidence_rate, 4),
        product=round(product, 6),
        evidence_quantum=evidence_quantum,
        principle_satisfied=satisfied,
        evidence=(
            f"delta_p={precision:.4f}, "
            f"delta_e={evidence_rate:.4f}, "
            f"product={product:.6f} >= h/2={threshold:.4f}: "
            f"{'satisfied' if satisfied else 'violated'}"
        ),
    )
