"""Deterministic runtime orchestration for Stage 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from .approval import ApprovalGate, ApprovalGateResult
from .audit_policy import CompilerAuditPolicy
from .deliberation import ReasoningChain, ReasoningStep, deliberate_chain, deliberate_next_action
from .domain_context import DomainContext
from .domain_policy import evaluate_patch_policy_in_domain
from .event_log import EventLog
from .events import DeliberationEvent, Event, StateTransitionEvent
from .llm_task_adapter import (
    LLMTaskCompiler,
    ProviderBackedTaskCompiler,
    compile_task_with_llm_adapter,
)
from .planner import PlanExecutionResult, PlanSpec, plan_from_task
from .state import State
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
    replayed_state: State
    approval_gate_result: ApprovalGateResult | None = None
    reasoning_chain: ReasoningChain | None = None

    @property
    def allowed_transitions(self) -> tuple[StateTransitionEvent, ...]:
        return self.plan_result.allowed

    @property
    def blocked_transitions(self) -> tuple[StateTransitionEvent, ...]:
        return self.plan_result.blocked

    @property
    def approval_required_transitions(self) -> tuple[StateTransitionEvent, ...]:
        return self.plan_result.requires_approval

    @property
    def denied_transitions(self) -> tuple[StateTransitionEvent, ...]:
        return self.plan_result.denied

    @property
    def approved_transitions(self) -> tuple[StateTransitionEvent, ...]:
        if self.approval_gate_result is None:
            return ()
        return self.approval_gate_result.approved_transitions

    @property
    def rejected_transitions(self) -> tuple[StateTransitionEvent, ...]:
        if self.approval_gate_result is None:
            return ()
        return self.approval_gate_result.rejected_transitions

    @property
    def redirect_proposed(self) -> bool:
        return (
            self.reasoning_step.chosen_action == "propose_redirect"
            and len(self.plan.candidate_patches) == 0
        )


def _apply_approval_gate(
    plan_result: PlanExecutionResult,
    event_log: EventLog,
    approval_gate: ApprovalGate | None,
) -> ApprovalGateResult | None:
    if approval_gate is None:
        return None

    requires_approval = plan_result.requires_approval
    if not requires_approval:
        return None

    gate_result = approval_gate.resolve(requires_approval)

    for decision in gate_result.decisions:
        event_log.append(decision.to_event())

    for event in gate_result.approved_transitions:
        event_log.append(event)

    return gate_result


def _execute_plan_in_domain(
    plan: PlanSpec,
    domain_context: DomainContext,
    *,
    event_log: EventLog,
    current_state: State | None = None,
    tool_runner: InMemoryReadOnlyToolRunner | None = None,
    promote_tool_observations_to_belief_keys: dict[str, str] | None = None,
) -> PlanExecutionResult:
    """Execute a plan with domain overlay applied to patch transitions."""

    if plan.proposed_tool_calls:
        if tool_runner is None:
            raise ValueError("tool_runner is required when plan has proposed_tool_calls")
        return execute_plan_with_read_only_tools(
            plan,
            tool_runner,
            event_log=event_log,
            promote_to_belief_keys=promote_tool_observations_to_belief_keys,
            domain_context=domain_context,
        ).plan_result

    events: list[StateTransitionEvent] = []

    for patch in plan.candidate_patches:
        decision = evaluate_patch_policy_in_domain(
            patch, domain_context, current_state=current_state,
        )
        event = StateTransitionEvent(
            patch=patch,
            policy_decision=decision,
            actor=plan.actor,
            reason=f"plan:{plan.plan_id}:{plan.objective}",
        )
        event_log.append(event)
        events.append(event)

    return PlanExecutionResult(plan=plan, events=tuple(events), tool_call_events=())


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
    """Run the deterministic pipeline using multi-step reasoning chain.

    Each step in the chain is recorded as a DeliberationEvent in the
    audit trail. The final step's chosen_action drives planning.
    """

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
        current_state=log.replay_state(),
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)
    replayed_state = log.replay_state()

    return RunResult(
        task=task,
        reasoning_step=final_step,
        reasoning_chain=chain,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        replayed_state=replayed_state,
        approval_gate_result=gate_result,
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
    """Run the deterministic pipeline in an explicit domain context.
    
    Args:
        raw_input: The raw task input string
        domain_context: The domain context for policy evaluation
        event_log: Optional event log for recording events
        tool_runner: Optional tool runner for executing read-only tools
        promote_tool_observations_to_belief_keys: Keys for promoting tool observations to beliefs
        approval_gate: Optional approval gate for high-risk transitions
        memory_store: Optional memory store for precedent retrieval
        router: Optional uncertainty router for routing decisions
        
    Returns:
        RunResult containing the full execution trace and results
    """

    log = event_log or EventLog()
    task = compile_task(
        raw_input,
        event_log=log,
        domain_name=domain_context.domain_name,
    )
    tool_registry = tool_runner.registry if tool_runner is not None else None
    
    # Precedent Memory Retrieval (if memory_store provided)
    precedent_context: List[RetrievalResult] = []
    if memory_store is not None:
        retriever = Retriever(memory_store=memory_store)
        query = RetrievalQuery(
            query_text=raw_input,
            domain_label=domain_context.domain_name,
            limit=5,
        )
        precedents = retriever.search_precedents(query)
        precedent_context = precedents.results
        if precedent_context:
            log.append(DeliberationEvent(
                reasoning_step=ReasoningStep(
                    observation=f"Retrieved {len(precedent_context)} precedent memories",
                    reasoning=f"Found similar past tasks that may inform current execution",
                    alternatives=[f"Precedent: {p.content[:100]}" for p in precedent_context[:3]],
                    chosen_action="execute_plan",
                ),
            ))
    
    reasoning_step = deliberate_next_action(task, tool_registry=tool_registry)
    log.append(DeliberationEvent(reasoning_step=reasoning_step))
    
    plan = plan_from_task(
        task,
        tool_registry=tool_registry,
        reasoning_step=reasoning_step,
    )
    
    # Uncertainty Routing (if router provided)
    routing_decision: Optional[RoutingDecision] = None
    if router is not None:
        signals = RoutingSignals(
            evidence_coverage=0.7 if not precedent_context else 0.9,
            precedent_similarity=0.5,
            tool_risk_level=task.risk_level.value,
            historical_success_rate=0.8,
            model_self_confidence=0.75,
        )
        routing_result = router.route(signals)
        routing_decision = routing_result.decision
        
        # Record routing decision to event log
        log.append(DeliberationEvent(
            reasoning_step=ReasoningStep(
                observation=f"Uncertainty routing: {routing_decision.decision.value}",
                reasoning=routing_decision.reasoning,
                alternatives=[],
                chosen_action=routing_decision.decision.value,
                confidence=routing_decision.confidence,
            ),
        ))
        
        # Adjust approval strategy based on routing decision
        if routing_decision.decision.value == "needs_human_review":
            # Force approval for high-uncertainty tasks
            approval_gate = approval_gate or ApprovalGate()
    
    plan_result = _execute_plan_in_domain(
        plan,
        domain_context,
        event_log=log,
        current_state=log.replay_state(),
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)
    replayed_state = log.replay_state()

    return RunResult(
        task=task,
        reasoning_step=reasoning_step,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        replayed_state=replayed_state,
        approval_gate_result=gate_result,
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
        current_state=log.replay_state(),
        tool_runner=tool_runner,
        promote_tool_observations_to_belief_keys=promote_tool_observations_to_belief_keys,
    )
    gate_result = _apply_approval_gate(plan_result, log, approval_gate)
    replayed_state = log.replay_state()

    return RunResult(
        task=task,
        reasoning_step=reasoning_step,
        plan=plan,
        plan_result=plan_result,
        event_log=log,
        replayed_state=replayed_state,
        approval_gate_result=gate_result,
    )
