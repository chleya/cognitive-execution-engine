"""Unified retrieval interface combining precedent memory and document retrieval.

Provides hybrid retrieval capabilities with contextual embeddings,
result reranking, and formatted context generation for LLM consumption.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple, Literal
from dataclasses import dataclass

from .retrieval_types import RetrievalQuery
from .memory_types import MemoryRetrievalResult
from .memory_index import MemoryIndex
from .contextualizer import Contextualizer, DocumentChunk
from .llm_provider import get_default_embedding_provider


@dataclass
class RetrievalResult:
    """Unified retrieval result for both memories and documents."""

    content: str
    relevance_score: float
    result_type: Literal["precedent_memory", "document_chunk"]
    source_id: str
    metadata: Dict[str, Any]
    match_reason: str = ""


class Retriever:
    """Unified retrieval interface for CEE."""

    def __init__(
        self,
        memory_index: MemoryIndex,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        context_window_size: int = 200,
        embedding_provider=None
    ):
        """Initialize retriever.
        
        Args:
            memory_index: MemoryIndex instance for precedent retrieval
            chunk_size: Target chunk size for document processing
            chunk_overlap: Overlap between document chunks
            context_window_size: Context window size for contextual chunking
            embedding_provider: Embedding provider instance (defaults to global)
        """
        self.memory_index = memory_index
        self.contextualizer = Contextualizer(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            context_window_size=context_window_size
        )
        self.embedding_provider = embedding_provider or get_default_embedding_provider()
        
        # In-memory document chunk index (for runtime document retrieval)
        self._document_chunks: Dict[str, DocumentChunk] = {}
        self._document_index: Dict[str, List[str]] = {}  # document_id -> list of chunk_ids

    def index_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_summary: Optional[str] = None
    ) -> int:
        """Process and index a document for retrieval.
        
        Args:
            document_id: Unique identifier for the document
            content: Full document text
            metadata: Optional document metadata
            document_summary: Optional pre-generated document summary
            
        Returns:
            Number of chunks created and indexed
        """
        if metadata is None:
            metadata = {}
        
        metadata['document_id'] = document_id
        
        # Process into contextual chunks
        chunks = self.contextualizer.process_document(
            content=content,
            metadata=metadata,
            document_summary=document_summary
        )
        
        # Generate embeddings for each chunk
        for chunk in chunks:
            embed_text = chunk.get_full_text_for_embedding()
            chunk.embedding = self.embedding_provider.get_embedding(embed_text)
            self._document_chunks[chunk.chunk_id] = chunk
        
        # Update document index
        self._document_index[document_id] = [c.chunk_id for c in chunks]
        
        return len(chunks)

    def delete_document(self, document_id: str) -> bool:
        """Delete a document from the index.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            True if document was deleted, False if not found
        """
        if document_id not in self._document_index:
            return False
        
        # Delete all chunks for this document
        for chunk_id in self._document_index[document_id]:
            if chunk_id in self._document_chunks:
                del self._document_chunks[chunk_id]
        
        # Delete from document index
        del self._document_index[document_id]
        
        return True

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import numpy as np
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    def _keyword_match_score(self, query: str, text: str) -> float:
        """Calculate simple keyword match score."""
        if not query or not text:
            return 0.0
        
        query_terms = set(query.lower().split())
        text_terms = set(text.lower().split())
        
        if not query_terms:
            return 0.0
        
        matching_terms = query_terms.intersection(text_terms)
        return len(matching_terms) / len(query_terms)

    def search_documents(
        self,
        query: RetrievalQuery,
        document_ids: Optional[List[str]] = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[RetrievalResult]:
        """Search across indexed documents.
        
        Args:
            query: RetrievalQuery object
            document_ids: Optional list of document IDs to restrict search to
            semantic_weight: Weight for semantic similarity
            keyword_weight: Weight for keyword matching
            
        Returns:
            List of RetrievalResult sorted by relevance
        """
        # Get query embedding
        query_vector = self.embedding_provider.get_embedding(query.query_text)
        
        # Get all chunks to search
        chunks_to_search = []
        if document_ids:
            for doc_id in document_ids:
                if doc_id in self._document_index:
                    chunks_to_search.extend([
                        self._document_chunks[cid] 
                        for cid in self._document_index[doc_id] 
                        if cid in self._document_chunks
                    ])
        else:
            chunks_to_search = list(self._document_chunks.values())
        
        # Calculate scores
        results = []
        for chunk in chunks_to_search:
            if chunk.embedding is None:
                continue
            
            semantic_score = self._cosine_similarity(query_vector, chunk.embedding)
            keyword_score = self._keyword_match_score(query.query_text, chunk.content)
            
            combined_score = (semantic_score * semantic_weight) + (keyword_score * keyword_weight)
            
            if combined_score >= query.min_relevance:
                results.append(RetrievalResult(
                    content=chunk.content,
                    relevance_score=min(combined_score, 1.0),
                    result_type="document_chunk",
                    source_id=chunk.chunk_id,
                    metadata=chunk.metadata,
                    match_reason=f"semantic similarity: {semantic_score:.2f}, keyword match: {keyword_score:.2f}"
                ))
        
        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        return results[:query.limit]

    def search_precedents(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Search precedent memory.
        
        Args:
            query: RetrievalQuery object
            
        Returns:
            List of RetrievalResult for matching precedents
        """
        memory_results = self.memory_index.search(query)
        
        # Convert to unified RetrievalResult format
        results = []
        for mr in memory_results:
            results.append(RetrievalResult(
                content=f"Task: {mr.memory.task_signature}\nSummary: {mr.memory.task_summary}\nOutcome: {mr.memory.outcome}",
                relevance_score=mr.relevance_score,
                result_type="precedent_memory",
                source_id=mr.memory.memory_id,
                metadata={
                    "task_signature": mr.memory.task_signature,
                    "outcome": mr.memory.outcome,
                    "failure_mode": mr.memory.failure_mode,
                    "domain_label": mr.memory.domain_label,
                    "state_diff": mr.memory.state_diff
                },
                match_reason=mr.match_reason
            ))
        
        return results

    def search(
        self,
        query: RetrievalQuery,
        include_precedents: bool = True,
        include_documents: bool = True,
        document_ids: Optional[List[str]] = None,
        precedent_weight: float = 0.6,
        document_weight: float = 0.4
    ) -> List[RetrievalResult]:
        """Unified search across both precedents and documents.
        
        Args:
            query: RetrievalQuery object
            include_precedents: Whether to include precedent memory results
            include_documents: Whether to include document results
            document_ids: Optional list of document IDs to search
            precedent_weight: Weight for precedent results in combined ranking
            document_weight: Weight for document results in combined ranking
            
        Returns:
            Combined list of RetrievalResult sorted by relevance
        """
        all_results = []
        
        if include_precedents:
            prec_results = self.search_precedents(query)
            for r in prec_results:
                r.relevance_score *= precedent_weight
                all_results.append(r)
        
        if include_documents:
            doc_results = self.search_documents(query, document_ids)
            for r in doc_results:
                r.relevance_score *= document_weight
                all_results.append(r)
        
        # Sort all results by adjusted relevance score
        all_results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        return all_results[:query.limit]

    def rerank_results(
        self,
        query: str,
        results: List[RetrievalResult],
        top_k: Optional[int] = None
    ) -> List[RetrievalResult]:
        """Rerank retrieval results using more precise cross-attention scoring.
        
        Currently implements a simple reranking based on combined semantic
        and keyword relevance. Can be extended with cross-encoder models.
        
        Args:
            query: Original search query
            results: List of retrieval results to rerank
            top_k: Number of top results to return (defaults to all)
            
        Returns:
            Reranked list of RetrievalResult
        """
        query_vector = self.embedding_provider.get_embedding(query)
        
        for result in results:
            # Recalculate semantic similarity with just the content
            content_vector = self.embedding_provider.get_embedding(result.content)
            semantic_score = self._cosine_similarity(query_vector, content_vector)
            
            # Recalculate keyword match
            keyword_score = self._keyword_match_score(query, result.content)
            
            # Adjust score (give more weight to direct content match)
            result.relevance_score = (semantic_score * 0.6) + (keyword_score * 0.4)
        
        # Sort again
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        if top_k is not None:
            results = results[:top_k]
        
        return results

    def get_formatted_context(
        self,
        results: List[RetrievalResult],
        max_context_length: int = 4000,
        include_metadata: bool = True
    ) -> str:
        """Format retrieval results into a context string for LLM prompts.
        
        Args:
            results: List of RetrievalResult to format
            max_context_length: Maximum length of the returned context
            include_metadata: Whether to include metadata in the context
            
        Returns:
            Formatted context string
        """
        context_parts = []
        total_length = 0
        
        for i, result in enumerate(results, 1):
            result_text = f"\n--- Result {i} ({result.result_type}) ---\n"
            result_text += f"Content: {result.content}\n"
            
            if include_metadata and result.metadata:
                metadata_str = ", ".join([f"{k}: {v}" for k, v in result.metadata.items() if v])
                if metadata_str:
                    result_text += f"Metadata: {metadata_str}\n"
            
            result_text += f"Relevance: {result.relevance_score:.2f}\n"
            
            # Check if adding this would exceed max length
            if total_length + len(result_text) > max_context_length:
                # If even the first result is too long, truncate it
                if i == 1:
                    truncated_length = max_context_length - total_length - 30  # Leave room for truncation notice
                    result_text = result_text[:truncated_length] + "\n[TRUNCATED]\n"
                    context_parts.append(result_text)
                break
            
            context_parts.append(result_text)
            total_length += len(result_text)
        
        return "\n".join(context_parts)

    def clear_document_index(self) -> None:
        """Clear all indexed documents from memory."""
        self._document_chunks.clear()
        self._document_index.clear()
