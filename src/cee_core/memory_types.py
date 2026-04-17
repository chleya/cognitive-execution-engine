"""Precedent memory type definitions.

Memory is structured object, not just text chunks. Each memory entry
captures the full context of a previous task execution, including state
changes, evidence used, outcome, and audit information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, UTC


@dataclass(frozen=True)
class PrecedentMemory:
    """A structured memory entry capturing a previous execution precedent.
    
    This is a first-class object in the system, not just a text embedding.
    It captures all relevant context for future retrieval and decision making.
    """

    task_signature: str  # 任务类型唯一标识，例如 "document_analysis.extract_info"
    state_diff: Dict[str, Any]  # 任务执行后的状态变更
    evidence_refs: List[str]  # 引用的证据ID列表
    outcome: str  # 执行结果："success" / "failure" / "partial_success"
    memory_id: str = field(default_factory=lambda: f"mem_{uuid4().hex}")
    failure_mode: Optional[str] = None  # 失败模式ID，如果执行失败
    approval_result: Optional[str] = None  # 审批结论："approved" / "rejected" / "auto_approved"
    semantic_vector: Optional[List[float]] = None  # 语义向量用于检索
    domain_label: str = "default"  # 所属域标签
    task_summary: str = ""  # 任务执行摘要，用于快速理解
    created_at: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "task_signature": self.task_signature,
            "state_diff": self.state_diff,
            "evidence_refs": self.evidence_refs,
            "outcome": self.outcome,
            "failure_mode": self.failure_mode,
            "approval_result": self.approval_result,
            "semantic_vector": self.semantic_vector,
            "domain_label": self.domain_label,
            "task_summary": self.task_summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PrecedentMemory":
        return cls(
            task_signature=payload["task_signature"],
            state_diff=payload["state_diff"],
            evidence_refs=payload["evidence_refs"],
            outcome=payload["outcome"],
            memory_id=payload.get("memory_id", f"mem_{uuid4().hex}"),
            failure_mode=payload.get("failure_mode"),
            approval_result=payload.get("approval_result"),
            semantic_vector=payload.get("semantic_vector"),
            domain_label=payload.get("domain_label", "default"),
            task_summary=payload.get("task_summary", ""),
            created_at=payload.get("created_at", datetime.now(UTC).timestamp()),
        )


@dataclass(frozen=True)
class MemoryRetrievalResult:
    """Result of a memory retrieval query."""

    memory: PrecedentMemory
    relevance_score: float  # 0-1的相关性分数
    match_reason: str = ""  # 匹配原因说明

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "relevance_score": self.relevance_score,
            "match_reason": self.match_reason,
        }
