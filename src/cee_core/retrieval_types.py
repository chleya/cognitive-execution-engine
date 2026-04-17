"""Retrieval-related type definitions.

Defines types for contextual retrieval, evidence graph, and retrieval results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from uuid import uuid4


EvidenceNodeType = Literal["source", "observation", "hypothesis", "conclusion"]
EvidenceEdgeType = Literal["supports", "contradicts", "requires_more_evidence"]


@dataclass(frozen=True)
class EvidenceNode:
    """A node in the evidence graph."""

    node_type: EvidenceNodeType
    content: str
    node_id: str = field(default_factory=lambda: f"ev_{uuid4().hex}")
    source_ref: Optional[str] = None  # 原始数据来源引用
    confidence: float = 1.0  # 证据置信度0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "content": self.content,
            "node_id": self.node_id,
            "source_ref": self.source_ref,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class EvidenceEdge:
    """An edge connecting two evidence nodes."""

    from_node_id: str
    to_node_id: str
    edge_type: EvidenceEdgeType
    edge_id: str = field(default_factory=lambda: f"edge_{uuid4().hex}")
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "edge_id": self.edge_id,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class EvidenceGraph:
    """Graph representing evidence and reasoning chain."""

    nodes: List[EvidenceNode] = field(default_factory=list)
    edges: List[EvidenceEdge] = field(default_factory=list)
    graph_id: str = field(default_factory=lambda: f"graph_{uuid4().hex}")

    def add_node(self, node: EvidenceNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: EvidenceEdge) -> None:
        self.edges.append(edge)

    def get_node_by_id(self, node_id: str) -> Optional[EvidenceNode]:
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "graph_id": self.graph_id,
        }


@dataclass(frozen=True)
class RetrievalQuery:
    """Query for contextual retrieval."""

    query_text: str
    domain_label: Optional[str] = None
    task_signature: Optional[str] = None
    limit: int = 10
    min_relevance: float = 0.5
    include_outcomes: Optional[List[str]] = None  # 可选过滤结果类型
