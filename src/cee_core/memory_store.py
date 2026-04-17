"""Precedent memory storage layer.

Handles persistent storage and retrieval of structured PrecedentMemory objects.
This layer abstracts the underlying storage backend (file system / database).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC

from .memory_types import PrecedentMemory, MemoryRetrievalResult
from .retrieval_types import RetrievalQuery


class MemoryStore:
    """Persistent storage for PrecedentMemory objects."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize memory store.
        
        Args:
            storage_path: Path to directory for storing memory entries.
                         Defaults to ./memory_store in current working directory.
        """
        if storage_path is None:
            storage_path = os.path.join(os.getcwd(), "memory_store")
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory index for fast lookups
        self._memory_index: Dict[str, PrecedentMemory] = {}
        self._load_existing_memories()

    def _load_existing_memories(self) -> None:
        """Load all existing memory entries from disk into memory."""
        for mem_file in self.storage_path.glob("mem_*.json"):
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    mem_data = json.load(f)
                    memory = PrecedentMemory.from_dict(mem_data)
                    self._memory_index[memory.memory_id] = memory
            except Exception as e:
                print(f"Failed to load memory file {mem_file}: {e}")

    def add_memory(self, memory: PrecedentMemory) -> str:
        """Add a new memory entry to the store.
        
        Args:
            memory: PrecedentMemory object to store
            
        Returns:
            memory_id of the stored entry
        """
        # Save to in-memory index
        self._memory_index[memory.memory_id] = memory
        
        # Save to disk
        mem_file = self.storage_path / f"{memory.memory_id}.json"
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump(memory.to_dict(), f, indent=2, ensure_ascii=False)
        
        return memory.memory_id

    def get_memory(self, memory_id: str) -> Optional[PrecedentMemory]:
        """Retrieve a memory entry by ID.
        
        Args:
            memory_id: ID of the memory to retrieve
            
        Returns:
            PrecedentMemory object if found, None otherwise
        """
        return self._memory_index.get(memory_id)

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory entry.
        
        Args:
            memory_id: ID of the memory to delete
            
        Returns:
            True if memory was deleted, False if not found
        """
        if memory_id not in self._memory_index:
            return False
        
        # Remove from in-memory index
        del self._memory_index[memory_id]
        
        # Remove from disk
        mem_file = self.storage_path / f"{memory_id}.json"
        if mem_file.exists():
            mem_file.unlink()
        
        return True

    def list_memories(
        self,
        domain_label: Optional[str] = None,
        task_signature: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[PrecedentMemory]:
        """List memory entries with optional filters.
        
        Args:
            domain_label: Filter by domain label
            task_signature: Filter by task signature
            outcome: Filter by outcome
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            List of matching PrecedentMemory objects, sorted by creation time (newest first)
        """
        memories = list(self._memory_index.values())
        
        # Apply filters
        if domain_label:
            memories = [m for m in memories if m.domain_label == domain_label]
        
        if task_signature:
            memories = [m for m in memories if m.task_signature == task_signature]
        
        if outcome:
            memories = [m for m in memories if m.outcome == outcome]
        
        # Sort by creation time (newest first)
        memories.sort(key=lambda m: m.created_at, reverse=True)
        
        # Apply pagination
        return memories[offset:offset + limit]

    def search_memories(self, query: RetrievalQuery) -> List[MemoryRetrievalResult]:
        """Search memories based on query.
        
        This is a baseline keyword-based search. The more advanced semantic search
        will be implemented in MemoryIndex.
        
        Args:
            query: RetrievalQuery object with search parameters
            
        Returns:
            List of MemoryRetrievalResult objects sorted by relevance
        """
        memories = self.list_memories(
            domain_label=query.domain_label,
            task_signature=query.task_signature,
            limit=1000  # Get up to 1000 for filtering
        )
        
        # Filter by outcome if specified
        if query.include_outcomes:
            memories = [m for m in memories if m.outcome in query.include_outcomes]
        
        results = []
        query_text_lower = query.query_text.lower()
        
        for memory in memories:
            # Simple keyword matching for baseline
            relevance = 0.0
            match_reasons = []
            
            # Match in task summary
            if query_text_lower in memory.task_summary.lower():
                relevance += 0.4
                match_reasons.append("matched in task summary")
            
            # Match in task signature
            if query_text_lower in memory.task_signature.lower():
                relevance += 0.3
                match_reasons.append("matched in task signature")
            
            # Match in state diff keys/values
            state_diff_str = json.dumps(memory.state_diff).lower()
            if query_text_lower in state_diff_str:
                relevance += 0.2
                match_reasons.append("matched in state change data")
            
            # Only include results above minimum relevance
            if relevance >= query.min_relevance:
                results.append(MemoryRetrievalResult(
                    memory=memory,
                    relevance_score=min(relevance, 1.0),
                    match_reason="; ".join(match_reasons)
                ))
        
        # Sort by relevance score descending
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        
        # Apply limit
        return results[:query.limit]

    def get_count(self) -> int:
        """Return total number of memories in the store."""
        return len(self._memory_index)

    def cleanup_old_memories(self, days_to_keep: int = 365) -> int:
        """Delete memories older than specified number of days.
        
        Args:
            days_to_keep: Number of days to keep memories for
            
        Returns:
            Number of memories deleted
        """
        cutoff_time = datetime.now(UTC).timestamp() - (days_to_keep * 86400)
        deleted_count = 0
        
        for memory in list(self._memory_index.values()):
            if memory.created_at < cutoff_time:
                self.delete_memory(memory.memory_id)
                deleted_count += 1
        
        return deleted_count
