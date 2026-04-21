"""Deterministic runtime orchestration for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from .approval import ApprovalGate, ApprovalGateResult
from .audit_policy import CompilerAuditPolicy
from .commitment import CommitmentEvent
from .commitment_policy import CommitmentPolicyDecision
from .deliberation import ReasoningChain, ReasoningStep, deliberate_chain, deliberate_next_action
from .domain_context import DomainContext
from .event_log import EventLog
from .events import DeliberationEvent, Event
from .planner import (
    DeltaPolicyDecision,
    PlanExecutionResult,
    PlanSpec,
    evaluate_delta_policy_in_domain,
    plan_from_task,
    _build_commitment_from_delta,
    _build_revision_from_delta,
)
from .revision import ModelRevisionEvent
from .world_state import WorldState
from .llm_task_adapter import (
    LLMTaskCompiler,
    ProviderBackedTaskCompiler,
    compile_task_with_llm_adapter,
)
from .tasks import TaskSpec, compile_task
from .tool_observation_flow import execute_plan_with_read_only_tools
from .tool_runner import InMemoryReadOnlyToolRunner
from .uncertainty_router import (
    UncertaintyRouter,
    RoutingSignals,
    RoutingDecision,
    RoutingResult,
    RouterConfig,
)
from .memory_store import MemoryStore
from .retrieval_types import RetrievalQuery
from .retriever import Retriever, RetrievalResult


@dataclass(frozen=True)
class RunResult:
    """End-to-end result of the deterministic Stage 0 runtime."""

    task: TaskSpec
    reasoning_step: ReasoningStep
    plan: PlanSpec
    plan_result: PlanExecutionResult
    event_log: EventLog
    approval_gate_result: ApprovalGateResult | None = None
    reasoning_chain: ReasoningChain | None = None
    commitment_events: tuple[CommitmentEvent, ...] = ()
    revision_events: tuple[ModelRevisionEvent, ...] = ()
    world_state: WorldState | None = None

    @property
    def allowed_count(self) -> int:
        return self.plan_result.allowed_count

    @property
    def blocked_count(self) -> int:
        return self.plan_result.blocked_count

    @property
    def requires_approval_count(self) -> int:
        return self.plan_result.requires_approval_count

    @property
    def allowed_transitions(self) -> tuple[CommitmentEvent, ...]:
        return tuple(ce for ce, d in zip(self.commitment_events, self.plan_result.policy_decisions) if d.allowed and not d.requires_approval)

    @property
    def blocked_transitions(self) -> tuple[CommitmentEvent, ...]:
        return tuple(ce for ce, d in zip(self.commitment_events, self.plan_result.policy_decisions) if not d.allowed and not d.requires_approval)

    @property
    def approval_required_transitions(self) -> tuple[CommitmentEvent, ...]:
        return tuple(ce for ce, d in zip(self.commitment_events, self.plan_result.policy_decisions) if d.requires_approval)

    @property
    def denied_transitions(self) -> tuple[CommitmentEvent, ...]:
        return tuple(ce for ce, d in zip(self.commitment_events, self.plan_result.policy_decisions) if not d.allowed and not d.requires_approval)

    @property
    def redirect_proposed(self) -> bool:
        return (
            self.reasoning_step.chosen_action == "propose_redirect"
            and len(self.plan.candidate_deltas) == 0
        )


def _extract_beliefs_and_memory_from_world(
    ws: WorldState,
) -> tuple[dict, dict]:
    """Extract beliefs and memory dicts from WorldState."""
    import json

    beliefs: dict = {}
    memory: dict = {}

    for e in ws.entities:
        if e.kind == "belief_item":
            key = e.entity_id.replace("belief-", "")
            parts = e.summary.split(" = ", 1)
            if len(parts) == 2:
                try:
                    beliefs[key] = int(parts[1])
                except ValueError:
                    try:
                        beliefs[key] = float(parts[1])
                    except ValueError:
                        beliefs[key] = parts[1]
            else:
                beliefs[key] = e.summary
        elif e.kind == "belief_group":
            key = e.entity_id.replace("belief-", "")
            try:
                beliefs[key] = json.loads(e.summary)
            except (json.JSONDecodeError, ValueError):
                beliefs[key] = {}
        elif e.kind == "memory_entry":
            key = e.entity_id.replace("memory-", "")
            try:
                memory[key] = json.loads(e.summary)
            except (json.JSONDecodeError, ValueError):
                memory[key] = []

    beliefs["hypotheses"] = [h.to_dict() for h in ws.hypotheses]
    beliefs["anchored_facts"] = [
        {"fact_id": f"fact-{i}", "statement": s}
        for i, s in enumerate(ws.anchored_fact_summaries)
    ]

    return beliefs, memory


def _apply_approval_gate(
    plan_result: PlanExecutionResult,
    event_log: EventLog,
    approval_gate: ApprovalGate | None,
) -> ApprovalGateResult | None:
    if approval_gate is None:
        return None

    requires_approval_events = tuple(
        ce for ce, d in zip(plan_result.commitment_events, plan_result.policy_decisions)
        if d.requires_approval
    )
    if not requires_approval_events:
        return None

    gate_result = approval_gate.resolve(requires_approval_events)

    for decision in gate_result.decisions:
        event_log.append(decision.to_event())

    return gate_result


def _execute_plan_in_domain(
    plan: PlanSpec,
    domain_context: DomainContext,
    *,
    event_log: EventLog,
    current_world_state: WorldState | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
) -> PlanExecutionResult:
    """Execute a plan with domain overlay applied to delta policy decisions."""

    _prior_state_id = current_world_state.state_id if current_world_state else "ws_0"

    if plan.proposed_tool_calls:
        if tool_runner is None:
            raise ValueError("tool_runner is required when plan has proposed_tool_calls")
        tool_result = execute_plan_with_read_only_tools(
            plan,
            tool_runner,
            event_log=event_log,
            promote_to_belief_keys=promote_tool_observations_to_belief_keys,
            domain_context=domain_context,
        )
        return tool_result.plan_result

    commitment_events: list[CommitmentEvent] = []
    revision_events: list[ModelRevisionEvent] = []
    policy_decisions: list[DeltaPolicyDecision] = []

    prior_state_id = _prior_state_id

    current_beliefs: dict[str, object] | None = None
    current_memory: dict[str, object] | None = None
    if current_world_state is not None:
        current_beliefs, current_memory = _extract_beliefs_and_memory_from_world(current_world_state)

    for i, delta in enumerate(plan.candidate_deltas):
        decision = evaluate_delta_policy_in_domain(
            delta, domain_context,
            current_beliefs=current_beliefs,
            current_memory=current_memory,
        )
        policy_decisions.append(decision)

        ce = _build_commitment_from_delta(delta, decision, plan, i)
        commitment_events.append(ce)
        event_log.append(ce)

        if decision.allowed and not decision.requires_approval:
            resulting_state_id = f"ws_{i + 1}"
            rev = _build_revision_from_delta(delta, prior_state_id, resulting_state_id, ce, plan)
            revision_events.append(rev)
            event_log.append(rev)
            prior_state_id = resulting_state_id

    return PlanExecutionResult(
        plan=plan,
        commitment_events=tuple(commitment_events),
        revision_events=tuple(revision_events),
        policy_decisions=tuple(policy_decisions),
    )


def execute_task(raw_input: str, *, event_log: EventLog | None = None) -> RunResult:
    """Run the full deterministic Stage 0 pipeline."""

    return execute_task_in_domain(
        raw_input,
        DomainContext(domain_name="core"),
        event_log=event_log,
    )


def execute_task_with_chain(
    raw_input: str,
    domain_context: DomainContext,
    *,
    event_log: EventLog | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
    approval_gate: ApprovalGate | None = None,
    max_chain_steps: int = 5,
) -> RunResult:
    """Run the deterministic pipeline using multi-step reasoning chain."""

    log = event_log or EventLog()
    task = compile_task(
        raw_input,
        event_log=log,
        domain_name=domain_context.domain_name,
    )
    tool_registry = tool_runner.registry if tool_runner is not None else None
    chain = deliberate_chain(task, tool_registry=tool_registry, max_steps=max_chain_steps)

    for step in chain.steps:
        log.append(DeliberationEvent(reasoning_step=step))

    final_step = chain.steps[-1] if chain.steps else deliberate_next_action(task, tool_registry=tool_registry)
    plan = plan_from_task(
        task,
        tool_registry=tool_registry,
        reasoning_step=final_step,
    )
    plan_result = _execute_plan_in_domain(
        plan,
        domain_context,
        event_log=log,
        current_world_state=log.replay_world_state() if log.revision_events() else None,
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)

    world_state = None
    if plan_result.commitment_events or plan_result.revision_events:
        world_state = log.replay_world_state()

    return RunResult(
        task=task,
        reasoning_step=final_step,
        reasoning_chain=chain,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        approval_gate_result=gate_result,
        commitment_events=plan_result.commitment_events,
        revision_events=plan_result.revision_events,
        world_state=world_state,
    )


def execute_task_in_domain(
    raw_input: str,
    domain_context: DomainContext,
    *,
    event_log: EventLog | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
    approval_gate: ApprovalGate | None = None,
    memory_store: MemoryStore | None = None,
    router: UncertaintyRouter | None = None,
) -> RunResult:
    """Run the deterministic pipeline in an explicit domain context."""

    log = event_log or EventLog()
    task = compile_task(
        raw_input,
        event_log=log,
        domain_name=domain_context.domain_name,
    )
    tool_registry = tool_runner.registry if tool_runner is not None else None

    precedent_context: List[RetrievalResult] = []
    if memory_store is not None:
        from .memory_index import MemoryIndex
        memory_index = MemoryIndex(memory_store)
        memory_index.build_index_from_store()
        retriever = Retriever(memory_index=memory_index)
        query = RetrievalQuery(
            query_text=raw_input,
            domain_label=domain_context.domain_name,
            limit=5,
        )
        precedent_context = retriever.search_precedents(query)
        if precedent_context:
            log.append(DeliberationEvent(
                reasoning_step=ReasoningStep(
                    task_id=task.task_id,
                    summary=f"Retrieved {len(precedent_context)} precedent memories",
                    hypothesis=f"Found similar past tasks that may inform current execution",
                    missing_information=(),
                    candidate_actions=(),
                    chosen_action="execute_plan",
                    rationale=f"Using {len(precedent_context)} precedents for context",
                    stop_condition="retrieval_complete",
                ),
            ))

    reasoning_step = deliberate_next_action(task, tool_registry=tool_registry)
    log.append(DeliberationEvent(reasoning_step=reasoning_step))

    plan = plan_from_task(
        task,
        tool_registry=tool_registry,
        reasoning_step=reasoning_step,
    )

    routing_result: Optional[RoutingResult] = None
    if router is not None:
        risk_level_value = task.risk_level.value if hasattr(task.risk_level, 'value') else task.risk_level
        signals = RoutingSignals(
            evidence_coverage=0.7 if not precedent_context else 0.9,
            precedent_similarity=0.5,
            tool_risk_level=risk_level_value,
            historical_success_rate=0.8,
            model_self_confidence=0.75,
        )
        routing_result = router.route(signals)

        log.append(DeliberationEvent(
            reasoning_step=ReasoningStep(
                task_id=task.task_id,
                summary=f"Uncertainty routing decision: {routing_result.decision.value}",
                hypothesis=routing_result.reasoning,
                missing_information=(),
                candidate_actions=(),
                chosen_action="execute_plan",
                rationale=routing_result.reasoning,
                stop_condition="routing_complete",
            ),
        ))

        if routing_result.decision == RoutingDecision.NEEDS_HUMAN_REVIEW:
            approval_gate = approval_gate or ApprovalGate()

    plan_result = _execute_plan_in_domain(
        plan,
        domain_context,
        event_log=log,
        current_world_state=log.replay_world_state() if log.revision_events() else None,
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)

    world_state = None
    if plan_result.commitment_events or plan_result.revision_events:
        world_state = log.replay_world_state()

    return RunResult(
        task=task,
        reasoning_step=reasoning_step,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        approval_gate_result=gate_result,
        commitment_events=plan_result.commitment_events,
        revision_events=plan_result.revision_events,
        world_state=world_state,
    )


def execute_task_with_compiler(
    raw_input: str,
    compiler: LLMTaskCompiler,
    *,
    event_log: EventLog | None = None,
    audit_policy: CompilerAuditPolicy | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
    approval_gate: ApprovalGate | None = None,
) -> RunResult:
    """Run the deterministic pipeline with an injected task compiler."""

    return execute_task_with_compiler_in_domain(
        raw_input,
        compiler,
        DomainContext(domain_name="core"),
        event_log=event_log,
        audit_policy=audit_policy,
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
        approval_gate=approval_gate,
    )


def execute_task_with_compiler_in_domain(
    raw_input: str,
    compiler: LLMTaskCompiler,
    domain_context: DomainContext,
    *,
    event_log: EventLog | None = None,
    audit_policy: CompilerAuditPolicy | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
    approval_gate: ApprovalGate | None = None,
) -> RunResult:
    """Run the deterministic pipeline with an injected task compiler in domain."""

    log = event_log or EventLog()
    audit = audit_policy or CompilerAuditPolicy()
    active_compiler = compiler
    if isinstance(compiler, ProviderBackedTaskCompiler) and compiler.event_log is None:
        active_compiler = compiler.bind_event_log(log)
    log.append(
        Event(
            event_type="task.compiler.requested",
            payload=audit.raw_input_payload(raw_input),
            actor="llm_task_compiler_adapter",
        )
    )

    try:
        task = compile_task_with_llm_adapter(
            raw_input,
            active_compiler,
            domain_name=domain_context.domain_name,
            fallback_to_deterministic=False,
        )
    except Exception as exc:
        log.append(
            Event(
                event_type="task.compiler.rejected",
                payload={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                actor="llm_task_compiler_adapter",
            )
        )
        raise

    log.append(
        Event(
            event_type="task.compiler.succeeded",
            payload={
                "task_id": task.task_id,
                "domain_name": task.domain_name,
                "kind": task.kind,
                "risk_level": task.risk_level,
                "objective": task.objective,
            },
            actor="llm_task_compiler_adapter",
        )
    )
    tool_registry = tool_runner.registry if tool_runner is not None else None
    reasoning_step = deliberate_next_action(task, tool_registry=tool_registry)
    log.append(DeliberationEvent(reasoning_step=reasoning_step))
    plan = plan_from_task(
        task,
        tool_registry=tool_registry,
        reasoning_step=reasoning_step,
    )
    plan_result = _execute_plan_in_domain(
        plan,
        domain_context,
        event_log=log,
        current_world_state=log.replay_world_state() if log.revision_events() else None,
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)

    world_state = None
    if plan_result.commitment_events or plan_result.revision_events:
        world_state = log.replay_world_state()

    return RunResult(
        task=task,
        reasoning_step=reasoning_step,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        approval_gate_result=gate_result,
        commitment_events=plan_result.commitment_events,
        revision_events=plan_result.revision_events,
        world_state=world_state,
    )
