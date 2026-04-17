"""Physics-inspired structural principles for CEE.

These are not metaphors. They are mathematical invariants that the CEE
system must satisfy, derived from structural analogies with fundamental
physics principles.

1. Symmetry -> Conservation (Noether's theorem analog):
   For every symmetry of the policy system, there is a conserved
   quantity. Domain substitution symmetry -> authority boundary
   conservation. Time translation symmetry -> replay determinism.

2. Least Action -> Optimal Path Selection:
   The system should evolve along paths that minimize accumulated
   policy resistance. Action = sum(policy_resistance * cognitive_cost)
   over the transition sequence.

3. Free Energy Minimization -> Uncertainty Reduction:
   The system should tend toward low-uncertainty states. High-uncertainty
   patches (low confidence, insufficient evidence) require external
   energy (human approval) to stabilize.

4. State-Policy Duality -> Lagrangian Structure:
   State and Policy are conjugate variables. The reducer is the
   equation of motion that deterministically evolves the system
   given the Lagrangian (which encodes dynamics and constraints).

Each principle maps to an executable invariant check.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain_policy import evaluate_patch_policy_in_domain
from .domain_context import DomainContext
from .event_log import EventLog
from .events import StateTransitionEvent
from .policy import PolicyDecision, evaluate_patch_policy
from .state import State, StatePatch


@dataclass(frozen=True)
class SymmetryCheckResult:
    """Result of checking a symmetry-conservation invariant."""

    symmetry_name: str
    conserved_quantity: str
    invariant_holds: bool
    evidence: str


def check_domain_substitution_symmetry(
    patch: StatePatch,
    domain_contexts: tuple[DomainContext, ...],
) -> SymmetryCheckResult:
    """Check domain substitution symmetry -> authority boundary conservation.

    If a patch is denied by base policy, it must be denied by ALL domain
    overlays. If a patch is allowed by base policy, a domain overlay may
    tighten it, but never loosen a deny. This is the Noether analog:
    domain substitution symmetry implies authority boundary conservation.

    Invariant: base_policy.deny => all_domains.deny
    """

    base_decision = evaluate_patch_policy(patch)

    if base_decision.verdict != "deny":
        return SymmetryCheckResult(
            symmetry_name="domain_substitution",
            conserved_quantity="authority_boundary",
            invariant_holds=True,
            evidence="base policy does not deny; no conservation requirement",
        )

    for ctx in domain_contexts:
        domain_decision = evaluate_patch_policy_in_domain(patch, ctx)
        if domain_decision.verdict != "deny":
            return SymmetryCheckResult(
                symmetry_name="domain_substitution",
                conserved_quantity="authority_boundary",
                invariant_holds=False,
                evidence=(
                    f"base policy denies but domain {ctx.domain_name} "
                    f"returns {domain_decision.verdict}: authority boundary not conserved"
                ),
            )

    return SymmetryCheckResult(
        symmetry_name="domain_substitution",
        conserved_quantity="authority_boundary",
        invariant_holds=True,
        evidence="base deny is conserved across all domain overlays",
    )


def check_replay_determinism_symmetry(
    event_log: EventLog,
) -> SymmetryCheckResult:
    """Check time translation symmetry -> replay determinism conservation.

    If the event log is replayed at any time, it must produce the same
    state. This is the Noether analog: time translation symmetry implies
    replay determinism conservation.

    Invariant: replay(events) == replay(events) (idempotent)
    """

    state_1 = event_log.replay_state()
    state_2 = event_log.replay_state()

    if state_1.snapshot() == state_2.snapshot():
        return SymmetryCheckResult(
            symmetry_name="time_translation",
            conserved_quantity="replay_determinism",
            invariant_holds=True,
            evidence="replay is idempotent: same events produce same state",
        )

    return SymmetryCheckResult(
        symmetry_name="time_translation",
        conserved_quantity="replay_determinism",
        invariant_holds=False,
        evidence="replay is not idempotent: same events produce different states",
    )


@dataclass(frozen=True)
class ActionCost:
    """Cost of a state transition through policy space.

    Analogy: in Lagrangian mechanics, action S = integral L dt.
    Here, action = sum of policy resistance over transitions.
    """

    allow_cost: float = 0.0
    requires_approval_cost: float = 1.0
    deny_cost: float = 10.0

    def cost_of(self, decision: PolicyDecision) -> float:
        if decision.verdict == "allow":
            return self.allow_cost
        if decision.verdict == "requires_approval":
            return self.requires_approval_cost
        return self.deny_cost


@dataclass(frozen=True)
class LeastActionResult:
    """Result of checking the least action principle."""

    total_action: float
    transition_count: int
    average_action: float
    optimal: bool
    evidence: str


def compute_action(
    events: tuple[StateTransitionEvent, ...],
    cost: ActionCost | None = None,
) -> LeastActionResult:
    """Compute the total action of a transition sequence.

    The least action principle says the system should evolve along
    paths that minimize accumulated policy resistance. A low total
    action means the transitions were mostly allowed (low resistance).
    A high total action means many transitions were blocked or
    required approval (high resistance).

    This is not a pass/fail check; it's a quantitative measure.
    A sequence is "optimal" if all transitions were allowed
    (total action = 0).
    """

    if cost is None:
        cost = ActionCost()

    total = sum(cost.cost_of(e.policy_decision) for e in events)
    count = len(events)
    average = total / count if count > 0 else 0.0

    return LeastActionResult(
        total_action=total,
        transition_count=count,
        average_action=average,
        optimal=total == 0.0,
        evidence=(
            f"total_action={total:.1f}, "
            f"avg_action={average:.2f}, "
            f"transitions={count}"
        ),
    )


@dataclass(frozen=True)
class FreeEnergyResult:
    """Result of checking free energy minimization.

    Analogy: F = E - TS
    - E (energy) = number of high-uncertainty beliefs
    - T (temperature) = escalation rate (fraction requiring approval)
    - S (entropy) = diversity of belief sources
    Lower free energy = more stable system state.
    """

    energy: float
    temperature: float
    entropy: float
    free_energy: float
    stable: bool
    evidence: str


def compute_free_energy(
    state: State,
    transition_events: tuple[StateTransitionEvent, ...],
) -> FreeEnergyResult:
    """Compute the free energy of a system state.

    F = E - T*S where:
    - E = count of low-confidence beliefs (high uncertainty = high energy)
    - T = escalation rate (requires_approval / total transitions)
    - S = number of distinct belief sources (diversity = entropy)

    A stable state has low free energy: few uncertain beliefs,
    low escalation rate, and high source diversity.
    """

    beliefs = state.beliefs
    low_confidence_count = 0
    source_set: set[str] = set()

    for _key, value in beliefs.items():
        if isinstance(value, dict):
            conf = value.get("confidence")
            if isinstance(conf, (int, float)) and float(conf) < 0.7:
                low_confidence_count += 1
            provenance = value.get("provenance")
            if isinstance(provenance, str):
                source_set.add(provenance)
            elif isinstance(provenance, (list, tuple)):
                for p in provenance:
                    if isinstance(p, str):
                        source_set.add(p)

    energy = float(low_confidence_count)

    total = len(transition_events)
    requires_approval = sum(
        1 for e in transition_events
        if e.policy_decision.verdict == "requires_approval"
    )
    temperature = requires_approval / total if total > 0 else 0.0

    entropy = float(len(source_set))

    free_energy = energy - temperature * entropy

    stable = free_energy <= 0.0

    return FreeEnergyResult(
        energy=energy,
        temperature=temperature,
        entropy=entropy,
        free_energy=free_energy,
        stable=stable,
        evidence=(
            f"F={free_energy:.2f} = E={energy:.0f} - "
            f"T={temperature:.2f} * S={entropy:.0f}"
        ),
    )


@dataclass(frozen=True)
class LagrangianCheckResult:
    """Result of checking the State-Policy duality (Lagrangian structure).

    In Lagrangian mechanics: L(q, q_dot, t) encodes dynamics.
    In CEE: L(state, patch, policy) encodes the transition dynamics.
    The reducer is the equation of motion: given state and policy,
    it deterministically produces the next state.

    Invariant: reduce(state, event) is deterministic and policy-mediated.
    """

    duality_holds: bool
    reducer_deterministic: bool
    policy_mediated: bool
    evidence: str


def check_state_policy_duality(
    event_log: EventLog,
) -> LagrangianCheckResult:
    """Check that State and Policy are conjugate variables.

    The reducer must be:
    1. Deterministic: same events always produce same state
    2. Policy-mediated: every transition carries a policy decision
    """

    state_1 = event_log.replay_state()
    state_2 = event_log.replay_state()
    deterministic = state_1.snapshot() == state_2.snapshot()

    transitions = event_log.transition_events()
    policy_mediated = all(
        isinstance(e.policy_decision, PolicyDecision)
        for e in transitions
    )

    duality_holds = deterministic and policy_mediated

    return LagrangianCheckResult(
        duality_holds=duality_holds,
        reducer_deterministic=deterministic,
        policy_mediated=policy_mediated,
        evidence=(
            f"deterministic={deterministic}, "
            f"policy_mediated={policy_mediated}, "
            f"transitions={len(transitions)}"
        ),
    )
