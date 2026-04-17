"""Evidence graph construction and analysis module.

Represents reasoning chains as structured graphs of evidence nodes and
relationships, enabling verification, auditability, and improved decision
quality. Evidence graphs make the reasoning process explicit and inspectable.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Set, Tuple
from dataclasses import dataclass
from uuid import uuid4

from .retrieval_types import (
    EvidenceNode,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNodeType,
    EvidenceEdgeType
)


@dataclass
class ReasoningStep:
    """A step in the reasoning process, to be converted into graph nodes/edges."""

    step_id: str
    step_type: Literal["observation", "hypothesis", "conclusion"]
    content: str
    source_ref: Optional[str] = None
    confidence: float = 1.0
    supports: Optional[List[str]] = None  # List of step IDs this supports
    contradicts: Optional[List[str]] = None  # List of step IDs this contradicts
    requires_evidence: Optional[List[str]] = None  # List of required evidence IDs


class EvidenceGraphBuilder:
    """Builder for constructing evidence graphs from reasoning processes."""

    def __init__(self):
        """Initialize empty builder."""
        self.nodes: Dict[str, EvidenceNode] = {}
        self.edges: List[EvidenceEdge] = []
        self.step_to_node_map: Dict[str, str] = {}  # reasoning step ID -> node ID

    def add_source_node(
        self,
        content: str,
        source_ref: Optional[str] = None,
        confidence: float = 1.0
    ) -> str:
        """Add a source evidence node (raw data, document excerpts, etc.).
        
        Args:
            content: Content of the source material
            source_ref: Reference to original source (document ID, URL, etc.)
            confidence: Confidence in the source authenticity
            
        Returns:
            ID of the created node
        """
        node = EvidenceNode(
            node_type="source",
            content=content,
            source_ref=source_ref,
            confidence=confidence
        )
        self.nodes[node.node_id] = node
        return node.node_id

    def add_step(self, step: ReasoningStep) -> str:
        """Add a reasoning step and create corresponding node and edges.
        
        Args:
            step: ReasoningStep object to add
            
        Returns:
            ID of the created node
        """
        # Create node for this step
        node_type: EvidenceNodeType = step.step_type  # type: ignore
        node = EvidenceNode(
            node_type=node_type,
            content=step.content,
            source_ref=step.source_ref,
            confidence=step.confidence
        )
        self.nodes[node.node_id] = node
        self.step_to_node_map[step.step_id] = node.node_id

        # Add support edges
        if step.supports:
            for target_step_id in step.supports:
                if target_step_id in self.step_to_node_map:
                    target_node_id = self.step_to_node_map[target_step_id]
                    edge = EvidenceEdge(
                        from_node_id=node.node_id,
                        to_node_id=target_node_id,
                        edge_type="supports",
                        confidence=step.confidence * 0.9  # Slight discount for derived support
                    )
                    self.edges.append(edge)

        # Add contradiction edges
        if step.contradicts:
            for target_step_id in step.contradicts:
                if target_step_id in self.step_to_node_map:
                    target_node_id = self.step_to_node_map[target_step_id]
                    edge = EvidenceEdge(
                        from_node_id=node.node_id,
                        to_node_id=target_node_id,
                        edge_type="contradicts",
                        confidence=step.confidence
                    )
                    self.edges.append(edge)

        # Add requires evidence edges
        if step.requires_evidence:
            for evidence_node_id in step.requires_evidence:
                if evidence_node_id in self.nodes:
                    edge = EvidenceEdge(
                        from_node_id=node.node_id,
                        to_node_id=evidence_node_id,
                        edge_type="requires_more_evidence",
                        confidence=step.confidence
                    )
                    self.edges.append(edge)

        return node.node_id

    def add_support_relation(
        self,
        from_node_id: str,
        to_node_id: str,
        confidence: float = 1.0
    ) -> Optional[str]:
        """Add a support relation between two existing nodes.
        
        Args:
            from_node_id: ID of the supporting node
            to_node_id: ID of the supported node
            confidence: Confidence in this relation
            
        Returns:
            Edge ID if created, None otherwise
        """
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            return None

        edge = EvidenceEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type="supports",
            confidence=confidence
        )
        self.edges.append(edge)
        return edge.edge_id

    def add_contradiction_relation(
        self,
        from_node_id: str,
        to_node_id: str,
        confidence: float = 1.0
    ) -> Optional[str]:
        """Add a contradiction relation between two existing nodes.
        
        Args:
            from_node_id: ID of the node that contradicts
            to_node_id: ID of the node being contradicted
            confidence: Confidence in this relation
            
        Returns:
            Edge ID if created, None otherwise
        """
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            return None

        edge = EvidenceEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type="contradicts",
            confidence=confidence
        )
        self.edges.append(edge)
        return edge.edge_id

    def build(self) -> EvidenceGraph:
        """Build and return the complete EvidenceGraph.
        
        Returns:
            Constructed EvidenceGraph object
        """
        return EvidenceGraph(
            nodes=list(self.nodes.values()),
            edges=self.edges.copy()
        )

    def clear(self) -> None:
        """Clear all nodes and edges from the builder."""
        self.nodes.clear()
        self.edges.clear()
        self.step_to_node_map.clear()


class EvidenceGraphAnalyzer:
    """Analyzer for evidence graph quality, consistency, and coverage."""

    def __init__(self, graph: EvidenceGraph):
        """Initialize analyzer with a graph.
        
        Args:
            graph: EvidenceGraph to analyze
        """
        self.graph = graph
        self._adjacency: Dict[str, List[Tuple[str, EvidenceEdgeType, float]]] = {}
        self._reverse_adjacency: Dict[str, List[Tuple[str, EvidenceEdgeType, float]]] = {}
        self._build_adjacency()

    def _build_adjacency(self) -> None:
        """Build adjacency lists for graph traversal."""
        # Initialize for all nodes
        for node in self.graph.nodes:
            self._adjacency[node.node_id] = []
            self._reverse_adjacency[node.node_id] = []

        # Add edges
        for edge in self.graph.edges:
            self._adjacency[edge.from_node_id].append(
                (edge.to_node_id, edge.edge_type, edge.confidence)
            )
            self._reverse_adjacency[edge.to_node_id].append(
                (edge.from_node_id, edge.edge_type, edge.confidence)
            )

    def calculate_conclusion_confidence(self, conclusion_node_id: str) -> float:
        """Calculate overall confidence in a conclusion based on supporting evidence.
        
        Args:
            conclusion_node_id: ID of the conclusion node
            
        Returns:
            Confidence score between 0 and 1
        """
        if conclusion_node_id not in self._reverse_adjacency:
            return 0.0

        conclusion_node = self.graph.get_node_by_id(conclusion_node_id)
        if not conclusion_node:
            return 0.0

        # Get all supporting edges
        supporting_edges = [
            (from_id, conf)
            for from_id, edge_type, conf in self._reverse_adjacency[conclusion_node_id]
            if edge_type == "supports"
        ]

        if not supporting_edges:
            # No support, return base confidence
            return conclusion_node.confidence

        # Combine support confidence (average weighted by each support's confidence)
        total_support = 0.0
        total_weight = 0.0
        for from_id, edge_conf in supporting_edges:
            from_node = self.graph.get_node_by_id(from_id)
            if from_node:
                support_strength = from_node.confidence * edge_conf
                total_support += support_strength
                total_weight += 1.0

        avg_support = total_support / total_weight if total_weight > 0 else 0.0

        # Combine base confidence with support
        combined_confidence = (conclusion_node.confidence * 0.3) + (avg_support * 0.7)

        # Check for contradictions that reduce confidence
        contradictory_edges = [
            (from_id, conf)
            for from_id, edge_type, conf in self._reverse_adjacency[conclusion_node_id]
            if edge_type == "contradicts"
        ]

        contradiction_penalty = 0.0
        for from_id, edge_conf in contradictory_edges:
            from_node = self.graph.get_node_by_id(from_id)
            if from_node:
                contradiction_strength = from_node.confidence * edge_conf
                contradiction_penalty += contradiction_strength * 0.5  # Each contradiction reduces confidence by half its strength

        final_confidence = max(0.0, combined_confidence - contradiction_penalty)
        return min(1.0, final_confidence)

    def find_contradictions(self) -> List[Tuple[str, str, float]]:
        """Find all contradictions in the graph.
        
        Returns:
            List of (node1_id, node2_id, contradiction_strength) tuples
        """
        contradictions = []
        for edge in self.graph.edges:
            if edge.edge_type == "contradicts":
                node1 = self.graph.get_node_by_id(edge.from_node_id)
                node2 = self.graph.get_node_by_id(edge.to_node_id)
                if node1 and node2:
                    strength = node1.confidence * node2.confidence * edge.confidence
                    contradictions.append((edge.from_node_id, edge.to_node_id, strength))
        return contradictions

    def get_evidence_coverage(self, conclusion_node_id: str) -> float:
        """Calculate what percentage of supporting evidence for a conclusion comes from source nodes.
        
        Args:
            conclusion_node_id: ID of the conclusion node
            
        Returns:
            Coverage percentage between 0 and 1
        """
        if conclusion_node_id not in self._reverse_adjacency:
            return 0.0

        # Traverse all supporting nodes recursively
        visited: Set[str] = set()
        source_count = 0
        total_support_count = 0

        def traverse(node_id: str) -> None:
            nonlocal source_count, total_support_count
            if node_id in visited:
                return
            visited.add(node_id)

            node = self.graph.get_node_by_id(node_id)
            if not node:
                return

            if node.node_type == "source":
                source_count += 1
                total_support_count += 1
                return

            # Count as intermediate support
            total_support_count += 1

            # Traverse supporting nodes
            for from_id, edge_type, _ in self._reverse_adjacency[node_id]:
                if edge_type == "supports":
                    traverse(from_id)

        traverse(conclusion_node_id)

        if total_support_count == 0:
            return 0.0

        return source_count / total_support_count

    def check_for_missing_evidence(self) -> List[Tuple[str, str]]:
        """Find nodes that require additional evidence.
        
        Returns:
            List of (node_id, required_evidence_node_id) tuples
        """
        missing = []
        for edge in self.graph.edges:
            if edge.edge_type == "requires_more_evidence":
                missing.append((edge.from_node_id, edge.to_node_id))
        return missing

    def generate_audit_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive audit summary of the evidence graph.
        
        Returns:
            Dictionary with audit metrics and quality scores
        """
        conclusions = [n for n in self.graph.nodes if n.node_type == "conclusion"]
        contradictions = self.find_contradictions()
        missing_evidence = self.check_for_missing_evidence()

        # Calculate average conclusion confidence
        avg_conclusion_confidence = 0.0
        if conclusions:
            confidences = [self.calculate_conclusion_confidence(n.node_id) for n in conclusions]
            avg_conclusion_confidence = sum(confidences) / len(confidences)

        # Calculate average evidence coverage
        avg_evidence_coverage = 0.0
        if conclusions:
            coverages = [self.get_evidence_coverage(n.node_id) for n in conclusions]
            avg_evidence_coverage = sum(coverages) / len(coverages)

        return {
            "graph_id": self.graph.graph_id,
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "node_counts_by_type": {
                "source": len([n for n in self.graph.nodes if n.node_type == "source"]),
                "observation": len([n for n in self.graph.nodes if n.node_type == "observation"]),
                "hypothesis": len([n for n in self.graph.nodes if n.node_type == "hypothesis"]),
                "conclusion": len(conclusions)
            },
            "contradictions_found": len(contradictions),
            "contradiction_details": contradictions,
            "missing_evidence_count": len(missing_evidence),
            "missing_evidence_details": missing_evidence,
            "average_conclusion_confidence": avg_conclusion_confidence,
            "average_evidence_coverage": avg_evidence_coverage,
            "quality_score": (avg_conclusion_confidence * 0.5 + avg_evidence_coverage * 0.5) 
                            * max(0.0, 1.0 - len(contradictions) * 0.1)
                            * max(0.0, 1.0 - len(missing_evidence) * 0.05)
        }

    def format_for_human_review(self, max_length: int = 3000) -> str:
        """Format the evidence graph into a human-readable summary for review.
        
        Args:
            max_length: Maximum length of the returned summary
            
        Returns:
            Formatted string representation of the graph
        """
        parts = []
        parts.append("=== Evidence Graph Summary ===")
        
        # Add nodes
        parts.append("\n--- Evidence Nodes ---")
        for i, node in enumerate(self.graph.nodes, 1):
            content_preview = node.content[:100] + "..." if len(node.content) > 100 else node.content
            parts.append(f"{i}. [{node.node_type.upper()}] (confidence: {node.confidence:.2f}) {content_preview}")
            if node.source_ref:
                parts.append(f"   Source: {node.source_ref}")

        # Add relationships
        parts.append("\n--- Relationships ---")
        for i, edge in enumerate(self.graph.edges, 1):
            from_node = self.graph.get_node_by_id(edge.from_node_id)
            to_node = self.graph.get_node_by_id(edge.to_node_id)
            if from_node and to_node:
                from_preview = from_node.content[:50] + "..." if len(from_node.content) > 50 else from_node.content
                to_preview = to_node.content[:50] + "..." if len(to_node.content) > 50 else to_node.content
                
                relation_str = {
                    "supports": "supports",
                    "contradicts": "CONTRADICTS",
                    "requires_more_evidence": "requires additional evidence:"
                }[edge.edge_type]
                
                parts.append(f"{i}. [{from_node.node_type}] '{from_preview}' {relation_str} [{to_node.node_type}] '{to_preview}'")

        # Add audit summary
        parts.append("\n--- Quality Assessment ---")
        audit = self.generate_audit_summary()
        parts.append(f"Total conclusions: {audit['node_counts_by_type']['conclusion']}")
        parts.append(f"Average conclusion confidence: {audit['average_conclusion_confidence']:.2f}")
        parts.append(f"Average evidence coverage: {audit['average_evidence_coverage']:.2f}")
        parts.append(f"Contradictions found: {audit['contradictions_found']}")
        parts.append(f"Missing evidence requests: {audit['missing_evidence_count']}")
        parts.append(f"Overall quality score: {audit['quality_score']:.2f}")

        # Combine and truncate if needed
        full_text = "\n".join(parts)
        if len(full_text) > max_length:
            full_text = full_text[:max_length] + "\n[TRUNCATED - too long for preview]"

        return full_text
