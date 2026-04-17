"""Contextual chunk processor for improved retrieval.

Implements Contextual Retrieval technique where each chunk is augmented
with contextual information from the surrounding document, significantly
improving retrieval accuracy compared to standard chunking methods.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class DocumentChunk:
    """A chunk of document content with contextual metadata."""

    chunk_id: str
    content: str
    context_prefix: str
    start_offset: int
    end_offset: int
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

    def get_full_text_for_embedding(self) -> str:
        """Get combined context + content for embedding generation."""
        return f"{self.context_prefix}\n\n{self.content}"


class Contextualizer:
    """Processes documents into contextually augmented chunks."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        context_window_size: int = 200
    ):
        """Initialize contextualizer.
        
        Args:
            chunk_size: Target size of each content chunk in characters
            chunk_overlap: Overlap between consecutive chunks
            context_window_size: Size of preceding context to include as prefix
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.context_window_size = context_window_size

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple but effective rules."""
        # Simple sentence splitting for Chinese and English
        text = re.sub(r'([。！？.!?])', r'\1\n', text)
        sentences = [s.strip() for s in text.split('\n') if s.strip()]
        return sentences

    def _split_long_sentence(self, sentence: str, max_length: int) -> List[str]:
        """Split a long sentence into smaller parts."""
        if len(sentence) <= max_length:
            return [sentence]
        
        # Try to split on natural boundaries
        split_points = [
            (match.start(), match.end())
            for match in re.finditer(r'[,，、；; ]', sentence)
        ]
        
        parts = []
        current_pos = 0
        
        for start, end in split_points:
            if end - current_pos > max_length:
                # Split at this point
                parts.append(sentence[current_pos:end].strip())
                current_pos = end
        
        # Add remaining part
        if current_pos < len(sentence):
            parts.append(sentence[current_pos:].strip())
        
        # If no split points found, split arbitrarily
        if not parts:
            parts = [
                sentence[i:i+max_length]
                for i in range(0, len(sentence), max_length)
            ]
        
        return parts

    def process_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_summary: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Process a full document into contextually augmented chunks.
        
        Args:
            content: Full document text
            metadata: Document metadata to include with each chunk
            document_summary: Optional pre-generated document summary to use as context
            
        Returns:
            List of DocumentChunk objects with contextual prefixes
        """
        if metadata is None:
            metadata = {}
        
        sentences = self._split_into_sentences(content)
        
        # Build chunks by combining sentences
        chunks = []
        current_chunk = []
        current_length = 0
        start_offset = 0
        
        for i, sentence in enumerate(sentences):
            # Split very long sentences
            if len(sentence) > self.chunk_size * 0.8:
                sentence_parts = self._split_long_sentence(sentence, self.chunk_size // 2)
            else:
                sentence_parts = [sentence]
            
            for part in sentence_parts:
                part_length = len(part)
                
                if current_length + part_length > self.chunk_size and current_chunk:
                    # Finalize current chunk
                    chunk_content = ' '.join(current_chunk)
                    end_offset = start_offset + len(chunk_content)
                    
                    # Build context prefix
                    context_parts = []
                    if document_summary:
                        context_parts.append(f"Document summary: {document_summary}")
                    
                    # Add preceding context from previous sentences
                    preceding_context = []
                    prev_length = 0
                    for j in range(max(0, i-10), i):
                        sent = sentences[j]
                        if prev_length + len(sent) > self.context_window_size:
                            break
                        preceding_context.append(sent)
                        prev_length += len(sent)
                    
                    if preceding_context:
                        context_parts.append(f"Preceding context: {' '.join(preceding_context)}")
                    
                    context_prefix = '\n'.join(context_parts)
                    
                    chunks.append(DocumentChunk(
                        chunk_id=f"chunk_{uuid4().hex}",
                        content=chunk_content,
                        context_prefix=context_prefix,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        metadata=metadata.copy()
                    ))
                    
                    # Start new chunk with overlap
                    overlap_content = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else ''
                    current_chunk = [overlap_content, part] if overlap_content else [part]
                    current_length = len(' '.join(current_chunk))
                    start_offset = end_offset - len(overlap_content)
                else:
                    # Add to current chunk
                    current_chunk.append(part)
                    current_length += part_length + 1  # +1 for space
        
        # Add final chunk
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            end_offset = start_offset + len(chunk_content)
            
            context_parts = []
            if document_summary:
                context_parts.append(f"Document summary: {document_summary}")
            
            # Add preceding context
            preceding_context = []
            prev_length = 0
            for j in range(max(0, len(sentences)-10), len(sentences)):
                sent = sentences[j]
                if prev_length + len(sent) > self.context_window_size:
                    break
                preceding_context.append(sent)
                prev_length += len(sent)
            
            if preceding_context:
                context_parts.append(f"Preceding context: {' '.join(preceding_context)}")
            
            context_prefix = '\n'.join(context_parts)
            
            chunks.append(DocumentChunk(
                chunk_id=f"chunk_{uuid4().hex}",
                content=chunk_content,
                context_prefix=context_prefix,
                start_offset=start_offset,
                end_offset=end_offset,
                metadata=metadata.copy()
            ))
        
        return chunks

    def add_context_to_chunks(
        self,
        chunks: List[Dict[str, Any]],
        full_document: str,
        document_summary: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Add contextual prefixes to existing chunks.
        
        Args:
            chunks: List of existing chunks with 'content' and 'offset' fields
            full_document: Full original document text
            document_summary: Optional document summary
            
        Returns:
            List of DocumentChunk with contextual prefixes
        """
        contextualized = []
        
        for i, chunk in enumerate(chunks):
            content = chunk['content']
            start_offset = chunk.get('start_offset', 0)
            
            # Get preceding context
            context_start = max(0, start_offset - self.context_window_size)
            preceding_text = full_document[context_start:start_offset].strip()
            
            context_parts = []
            if document_summary:
                context_parts.append(f"Document summary: {document_summary}")
            
            if preceding_text:
                # Take the last few sentences from preceding text
                preceding_sentences = self._split_into_sentences(preceding_text)[-3:]
                if preceding_sentences:
                    context_parts.append(f"Preceding context: {' '.join(preceding_sentences)}")
            
            context_prefix = '\n'.join(context_parts)
            
            contextualized.append(DocumentChunk(
                chunk_id=chunk.get('chunk_id', f"chunk_{uuid4().hex}"),
                content=content,
                context_prefix=context_prefix,
                start_offset=start_offset,
                end_offset=chunk.get('end_offset', start_offset + len(content)),
                metadata=chunk.get('metadata', {})
            ))
        
        return contextualized
