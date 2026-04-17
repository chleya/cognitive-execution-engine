"""Memory indexing and semantic retrieval layer.

Provides advanced retrieval capabilities including semantic vector search,
hybrid retrieval combining keyword and semantic matching, and structured
filtering. Uses existing LLM providers for embedding generation.
"""

from __future__ import annotations

import json
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import numpy as np

from .memory_types import PrecedentMemory, MemoryRetrievalResult
from .retrieval_types import RetrievalQuery
from .memory_store import MemoryStore
from .llm_provider import get_default_embedding_provider


class MemoryIndex:
    """Semantic index for precedent memory retrieval."""

    def __init__(
        self,
        memory_store: MemoryStore,
        index_path: Optional[str] = None,
        embedding_dim: int = 1536  # Default for OpenAI embeddings
    ):
        """Initialize memory index.
        
        Args:
            memory_store: MemoryStore instance to use for data retrieval
            index_path: Path to save/load index data
            embedding_dim: Dimension of embedding vectors
        """
        self.memory_store = memory_store
        self.embedding_dim = embedding_dim
        self.embedding_provider = get_default_embedding_provider()
        
        if index_path is None:
            index_path = Path.cwd() / "memory_index"
        
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Index structures
        self._vector_index: Dict[str, List[float]] = {}  # memory_id -> vector
        self._bm25_index: Dict[str, Dict[str, float]] = {}  # Simple keyword index
        self._load_index()

    def _load_index(self) -> None:
        """Load existing index from disk."""
        vector_file = self.index_path / "vector_index.json"
        if vector_file.exists():
            try:
                with open(vector_file, "r", encoding="utf-8") as f:
                    self._vector_index = json.load(f)
            except Exception as e:
                print(f"Failed to load vector index: {e}")

    def _save_index(self) -> None:
        """Save current index to disk."""
        vector_file = self.index_path / "vector_index.json"
        with open(vector_file, "w", encoding="utf-8") as f:
            json.dump(self._vector_index, f)

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using configured provider."""
        return self.embedding_provider.get_embedding(text)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    def index_memory(self, memory: PrecedentMemory) -> None:
        """Index a memory entry for retrieval.
        
        Args:
            memory: PrecedentMemory object to index
        """
        # Generate embedding if not already present
        if memory.semantic_vector is None:
            # Combine relevant fields for embedding
            text_to_embed = f"""
            Task: {memory.task_signature}
            Summary: {memory.task_summary}
            Outcome: {memory.outcome}
            Failure Mode: {memory.failure_mode or 'none'}
            State Changes: {json.dumps(memory.state_diff)[:500]}
            """
            vector = self._get_embedding(text_to_embed)
            # Update memory with vector
            memory = PrecedentMemory(
                memory_id=memory.memory_id,
                task_signature=memory.task_signature,
                state_diff=memory.state_diff,
                evidence_refs=memory.evidence_refs,
                outcome=memory.outcome,
                failure_mode=memory.failure_mode,
                approval_result=memory.approval_result,
                semantic_vector=vector,
                domain_label=memory.domain_label,
                task_summary=memory.task_summary,
                created_at=memory.created_at
            )
            # Update in store
            self.memory_store.add_memory(memory)
        else:
            vector = memory.semantic_vector
        
        # Add to vector index
        self._vector_index[memory.memory_id] = vector
        
        # Save index
        self._save_index()

    def build_index_from_store(self) -> int:
        """Build index for all memories in the store.
        
        Returns:
            Number of memories indexed
        """
        memories = self.memory_store.list_memories(limit=10000)
        indexed_count = 0
        
        for memory in memories:
            if memory.memory_id not in self._vector_index or memory.semantic_vector is None:
                self.index_memory(memory)
                indexed_count += 1
        
        return indexed_count

    def search(
        self,
        query: RetrievalQuery,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[MemoryRetrievalResult]:
        """Hybrid search combining semantic and keyword matching.
        
        Args:
            query: RetrievalQuery object
            semantic_weight: Weight for semantic similarity score (0-1)
            keyword_weight: Weight for keyword match score (0-1)
            
        Returns:
            List of MemoryRetrievalResult sorted by combined relevance
        """
        # First get baseline keyword results from store
        keyword_results = self.memory_store.search_memories(query)
        
        # If no query text, return keyword results as-is
        if not query.query_text:
            return keyword_results
        
        # Get query embedding for semantic search
        query_vector = self._get_embedding(query.query_text)
        
        # Calculate semantic scores for all memories matching filters
        memories = self.memory_store.list_memories(
            domain_label=query.domain_label,
            task_signature=query.task_signature,
            limit=1000
        )
        
        if query.include_outcomes:
            memories = [m for m in memories if m.outcome in query.include_outcomes]
        
        semantic_scores: Dict[str, float] = {}
        for memory in memories:
            if memory.memory_id in self._vector_index:
                sim = self._cosine_similarity(query_vector, self._vector_index[memory.memory_id])
                semantic_scores[memory.memory_id] = sim
        
        # Combine scores
        combined_results: Dict[str, Tuple[MemoryRetrievalResult, float]] = {}
        
        # Add keyword results
        for kw_result in keyword_results:
            memory_id = kw_result.memory.memory_id
            semantic_score = semantic_scores.get(memory_id, 0.0)
            combined_score = (kw_result.relevance_score * keyword_weight) + (semantic_score * semantic_weight)
            combined_results[memory_id] = (kw_result, combined_score)
        
        # Add memories that only have semantic matches
        for memory in memories:
            if memory.memory_id not in combined_results and memory.memory_id in semantic_scores:
                semantic_score = semantic_scores[memory.memory_id]
                if semantic_score >= query.min_relevance:
                    result = MemoryRetrievalResult(
                        memory=memory,
                        relevance_score=semantic_score * semantic_weight,
                        match_reason="semantic similarity match"
                    )
                    combined_results[memory.memory_id] = (result, semantic_score * semantic_weight)
        
        # Sort by combined score descending
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Filter by minimum relevance and apply limit
        final_results = []
        for result, score in sorted_results:
            if score >= query.min_relevance:
                # Update relevance score to combined value
                final_result = MemoryRetrievalResult(
                    memory=result.memory,
                    relevance_score=min(score, 1.0),
                    match_reason=result.match_reason
                )
                final_results.append(final_result)
            
            if len(final_results) >= query.limit:
                break
        
        return final_results

    def get_similar_memories(
        self,
        memory: PrecedentMemory,
        limit: int = 5,
        min_relevance: float = 0.6
    ) -> List[MemoryRetrievalResult]:
        """Find memories similar to a given memory.
        
        Args:
            memory: The memory to find similar entries for
            limit: Maximum number of results
            min_relevance: Minimum relevance score threshold
            
        Returns:
            List of similar memories
        """
        if memory.semantic_vector is None:
            self.index_memory(memory)
            memory = self.memory_store.get_memory(memory.memory_id) or memory
        
        query = RetrievalQuery(
            query_text=memory.task_summary,
            domain_label=memory.domain_label,
            limit=limit + 1,  # +1 to exclude the memory itself
            min_relevance=min_relevance
        )
        
        results = self.search(query)
        
        # Exclude the original memory
        return [r for r in results if r.memory.memory_id != memory.memory_id][:limit]

    def delete_from_index(self, memory_id: str) -> None:
        """Remove a memory from the index.
        
        Args:
            memory_id: ID of memory to remove
        """
        if memory_id in self._vector_index:
            del self._vector_index[memory_id]
            self._save_index()
