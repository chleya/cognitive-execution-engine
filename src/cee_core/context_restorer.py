"""Context restoration module for runtime integration.

Retrieves relevant precedents, evidence, and failure examples at different
stages of the execution pipeline (planning, verification, reflection) and
injects them as context for improved decision-making.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .retrieval_types import RetrievalQuery
from .memory_index import MemoryIndex
from .retriever import Retriever, RetrievalResult
from .state import State


class ExecutionStage(Enum):
    """Different stages of execution where context is restored."""
    PLANNING = "planning"
    VERIFICATION = "verification"
    REFLECTION = "reflection"
    EXECUTION = "execution"


@dataclass
class RestoredContext:
    """Context restored for a specific execution stage."""

    stage: ExecutionStage
    precedents: List[RetrievalResult]
    evidence: List[RetrievalResult]
    failure_examples: List[RetrievalResult]
    formatted_context: str


class ContextRestorer:
    """Restores relevant context at different execution stages."""

    def __init__(
        self,
        retriever: Retriever,
        max_precedents: int = 5,
        max_evidence: int = 10,
        max_failures: int = 3
    ):
        """Initialize context restorer.
        
        Args:
            retriever: Retriever instance for searching memories and documents
            max_precedents: Maximum number of precedent memories to retrieve
            max_evidence: Maximum number of evidence chunks to retrieve
            max_failures: Maximum number of failure examples to retrieve
        """
        self.retriever = retriever
        self.max_precedents = max_precedents
        self.max_evidence = max_evidence
        self.max_failures = max_failures

    def restore_for_planning(
        self,
        task: str,
        state: State,
        domain_label: Optional[str] = None
    ) -> RestoredContext:
        """Restore context for the planning stage.
        
        Retrieves relevant precedents to help generate a better execution plan.
        
        Args:
            task: Current task description
            state: Current system state
            domain_label: Optional domain label for filtering
            
        Returns:
            RestoredContext with planning-relevant information
        """
        # Retrieve similar task precedents
        precedent_query = RetrievalQuery(
            query_text=task,
            domain_label=domain_label,
            limit=self.max_precedents,
            min_relevance=0.6,
            include_outcomes=["success", "partial_success"]
        )
        precedents = self.retriever.search_precedents(precedent_query)
        
        # Retrieve any evidence that might be relevant
        evidence_query = RetrievalQuery(
            query_text=task,
            domain_label=domain_label,
            limit=self.max_evidence,
            min_relevance=0.5
        )
        evidence = self.retriever.search(evidence_query, include_precedents=False)
        
        # No failure examples at planning stage
        failure_examples: List[RetrievalResult] = []
        
        # Format the context
        formatted_context = self._format_planning_context(task, precedents, evidence)
        
        return RestoredContext(
            stage=ExecutionStage.PLANNING,
            precedents=precedents,
            evidence=evidence,
            failure_examples=failure_examples,
            formatted_context=formatted_context
        )

    def restore_for_verification(
        self,
        plan: str,
        proposed_actions: str,
        state: State,
        domain_label: Optional[str] = None
    ) -> RestoredContext:
        """Restore context for the verification stage.
        
        Retrieves evidence and precedents to help verify the proposed plan.
        
        Args:
            plan: Generated execution plan
            proposed_actions: Proposed actions to execute
            state: Current system state
            domain_label: Optional domain label for filtering
            
        Returns:
            RestoredContext with verification-relevant information
        """
        query_text = f"{plan}\n{proposed_actions}"
        
        # Retrieve precedents with similar plans/actions
        precedent_query = RetrievalQuery(
            query_text=query_text,
            domain_label=domain_label,
            limit=self.max_precedents,
            min_relevance=0.55
        )
        precedents = self.retriever.search_precedents(precedent_query)
        
        # Retrieve relevant evidence
        evidence_query = RetrievalQuery(
            query_text=query_text,
            domain_label=domain_label,
            limit=self.max_evidence,
            min_relevance=0.5
        )
        evidence = self.retriever.search(evidence_query, include_precedents=False)
        
        # No failure examples at verification stage
        failure_examples: List[RetrievalResult] = []
        
        formatted_context = self._format_verification_context(plan, proposed_actions, precedents, evidence)
        
        return RestoredContext(
            stage=ExecutionStage.VERIFICATION,
            precedents=precedents,
            evidence=evidence,
            failure_examples=failure_examples,
            formatted_context=formatted_context
        )

    def restore_for_reflection(
        self,
        outcome: str,
        failure_mode: Optional[str],
        task: str,
        state: State,
        domain_label: Optional[str] = None
    ) -> RestoredContext:
        """Restore context for the reflection stage.
        
        Retrieves similar failures and success stories for learning.
        
        Args:
            outcome: Task outcome (success/failure/partial_success)
            failure_mode: Failure mode if outcome is failure
            task: Original task description
            state: System state after execution
            domain_label: Optional domain label for filtering
            
        Returns:
            RestoredContext with reflection-relevant information
        """
        query_text = f"{task}\nOutcome: {outcome}\nFailure: {failure_mode or 'none'}"
        
        # Retrieve similar precedents regardless of outcome
        precedent_query = RetrievalQuery(
            query_text=query_text,
            domain_label=domain_label,
            limit=self.max_precedents,
            min_relevance=0.5
        )
        precedents = self.retriever.search_precedents(precedent_query)
        
        # If failure, retrieve similar failures
        failure_examples: List[RetrievalResult] = []
        if outcome == "failure" and failure_mode:
            failure_query = RetrievalQuery(
                query_text=query_text,
                domain_label=domain_label,
                limit=self.max_failures,
                min_relevance=0.55,
                include_outcomes=["failure"]
            )
            failure_examples = self.retriever.search_precedents(failure_query)
        
        # Retrieve any relevant evidence for analysis
        evidence_query = RetrievalQuery(
            query_text=task,
            domain_label=domain_label,
            limit=self.max_evidence,
            min_relevance=0.45
        )
        evidence = self.retriever.search(evidence_query, include_precedents=False)
        
        formatted_context = self._format_reflection_context(task, outcome, failure_mode, precedents, failure_examples, evidence)
        
        return RestoredContext(
            stage=ExecutionStage.REFLECTION,
            precedents=precedents,
            evidence=evidence,
            failure_examples=failure_examples,
            formatted_context=formatted_context
        )

    def _format_planning_context(
        self,
        task: str,
        precedents: List[RetrievalResult],
        evidence: List[RetrievalResult]
    ) -> str:
        """Format context for planning stage."""
        parts = []
        parts.append("=== PLANNING CONTEXT ===")
        parts.append(f"Current Task: {task}")
        
        if precedents:
            parts.append("\n--- Relevant Precedents ---")
            for i, prec in enumerate(precedents, 1):
                parts.append(f"\n{i}. (Relevance: {prec.relevance_score:.2f})")
                parts.append(f"   {prec.content[:200]}...")
        
        if evidence:
            parts.append("\n--- Supporting Evidence ---")
            for i, ev in enumerate(evidence, 1):
                parts.append(f"\n{i}. (Relevance: {ev.relevance_score:.2f})")
                parts.append(f"   {ev.content[:150]}...")
        
        parts.append("\n--- Planning Guidance ---")
        parts.append("Generate an execution plan that:")
        parts.append("1. Leverages successful precedents where applicable")
        parts.append("2. Uses the provided evidence to validate assumptions")
        parts.append("3. Explicitly states any assumptions being made")
        parts.append("4. Identifies potential risks that may require verification")
        
        return "\n".join(parts)

    def _format_verification_context(
        self,
        plan: str,
        proposed_actions: str,
        precedents: List[RetrievalResult],
        evidence: List[RetrievalResult]
    ) -> str:
        """Format context for verification stage."""
        parts = []
        parts.append("=== VERIFICATION CONTEXT ===")
        parts.append(f"Plan: {plan[:200]}...")
        parts.append(f"Proposed Actions: {proposed_actions[:200]}...")
        
        if precedents:
            parts.append("\n--- Similar Historical Executions ---")
            for i, prec in enumerate(precedents, 1):
                parts.append(f"\n{i}. (Relevance: {prec.relevance_score:.2f})")
                parts.append(f"   {prec.content[:180]}...")
        
        if evidence:
            parts.append("\n--- Verifiable Evidence ---")
            for i, ev in enumerate(evidence, 1):
                parts.append(f"\n{i}. (Relevance: {ev.relevance_score:.2f})")
                parts.append(f"   {ev.content[:120]}...")
        
        parts.append("\n--- Verification Checklist ---")
        parts.append("Verify the proposed plan by:")
        parts.append("1. Checking against similar historical outcomes")
        parts.append("2. Validating assumptions against available evidence")
        parts.append("3. Identifying any missing evidence required")
        parts.append("4. Assessing if human review is warranted")
        
        return "\n".join(parts)

    def _format_reflection_context(
        self,
        task: str,
        outcome: str,
        failure_mode: Optional[str],
        precedents: List[RetrievalResult],
        failure_examples: List[RetrievalResult],
        evidence: List[RetrievalResult]
    ) -> str:
        """Format context for reflection stage."""
        parts = []
        parts.append("=== REFLECTION CONTEXT ===")
        parts.append(f"Task: {task}")
        parts.append(f"Outcome: {outcome}")
        if failure_mode:
            parts.append(f"Failure Mode: {failure_mode}")
        
        if precedents:
            parts.append("\n--- Comparative Precedents ---")
            for i, prec in enumerate(precedents, 1):
                parts.append(f"\n{i}. (Relevance: {prec.relevance_score:.2f})")
                parts.append(f"   {prec.content[:180]}...")
        
        if failure_examples:
            parts.append("\n--- Similar Failures ---")
            for i, fail in enumerate(failure_examples, 1):
                parts.append(f"\n{i}. (Relevance: {fail.relevance_score:.2f})")
                parts.append(f"   {fail.content[:150]}...")
        
        parts.append("\n--- Reflection Questions ---")
        parts.append("Analyze this execution by answering:")
        parts.append("1. What worked well and why?")
        parts.append("2. What went wrong and why?")
        parts.append("3. What could have been done differently?")
        parts.append("4. What should be remembered for future similar tasks?")
        parts.append("5. What new policies or rules would help?")
        
        return "\n".join(parts)
