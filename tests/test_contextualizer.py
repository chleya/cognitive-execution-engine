"""Tests for contextualizer module."""

import pytest
from src.cee_core.contextualizer import Contextualizer, DocumentChunk


class TestDocumentChunk:
    """Tests for DocumentChunk dataclass."""

    def test_create_chunk(self):
        """Test creating a document chunk."""
        chunk = DocumentChunk(
            chunk_id="chunk_001",
            content="This is the main content.",
            context_prefix="Document summary: Test document",
            start_offset=0,
            end_offset=24,
            metadata={"source": "test"}
        )
        
        assert chunk.chunk_id == "chunk_001"
        assert chunk.content == "This is the main content."
        assert chunk.context_prefix == "Document summary: Test document"
        assert chunk.metadata == {"source": "test"}
        assert chunk.embedding is None

    def test_get_full_text_for_embedding(self):
        """Test getting combined text for embedding."""
        chunk = DocumentChunk(
            chunk_id="chunk_001",
            content="Main content here.",
            context_prefix="Context prefix",
            start_offset=0,
            end_offset=17,
            metadata={}
        )
        
        full_text = chunk.get_full_text_for_embedding()
        assert "Context prefix" in full_text
        assert "Main content here." in full_text


class TestContextualizer:
    """Tests for Contextualizer class."""

    @pytest.fixture
    def contextualizer(self):
        """Create a contextualizer for testing."""
        return Contextualizer(
            chunk_size=100,
            chunk_overlap=20,
            context_window_size=50
        )

    def test_initialize_contextualizer(self):
        """Test initializing contextualizer with custom params."""
        ctx = Contextualizer(
            chunk_size=200,
            chunk_overlap=30,
            context_window_size=100
        )
        
        assert ctx.chunk_size == 200
        assert ctx.chunk_overlap == 30
        assert ctx.context_window_size == 100

    def test_split_into_sentences(self, contextualizer):
        """Test splitting text into sentences."""
        text = "Hello world! How are you? I'm fine. Thanks."
        sentences = contextualizer._split_into_sentences(text)
        
        assert len(sentences) >= 3
        assert any("Hello world" in s for s in sentences)
        assert any("How are you" in s for s in sentences)

    def test_process_short_document(self, contextualizer):
        """Test processing a short document (single chunk)."""
        content = "This is a short document. It has only a few sentences."
        
        chunks = contextualizer.process_document(content)
        
        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert "short document" in chunks[0].content

    def test_process_long_document(self, contextualizer):
        """Test processing a long document (multiple chunks)."""
        sentences = [f"This is sentence {i}. It contains some content." for i in range(50)]
        content = " ".join(sentences)
        
        chunks = contextualizer.process_document(content)
        
        assert len(chunks) > 1
        assert all(c.start_offset < c.end_offset for c in chunks)

    def test_process_with_document_summary(self, contextualizer):
        """Test processing with a document summary."""
        content = "Main content here. More content. Even more."
        summary = "This is a test document about something important."
        
        chunks = contextualizer.process_document(
            content,
            document_summary=summary
        )
        
        assert len(chunks) > 0
        assert "Document summary" in chunks[0].context_prefix
        assert "test document" in chunks[0].context_prefix

    def test_process_with_metadata(self, contextualizer):
        """Test processing with metadata."""
        content = "Test content."
        metadata = {"author": "test", "date": "2024-01-01"}
        
        chunks = contextualizer.process_document(content, metadata=metadata)
        
        assert len(chunks) > 0
        assert chunks[0].metadata["author"] == "test"
        assert chunks[0].metadata["date"] == "2024-01-01"

    def test_chunk_overlap(self, contextualizer):
        """Test that chunks have overlap."""
        sentences = [f"Sentence {i}. " for i in range(20)]
        content = "".join(sentences)
        
        chunks = contextualizer.process_document(content)
        
        if len(chunks) >= 2:
            chunk1_text = chunks[0].content
            chunk2_text = chunks[1].content
            words1 = set(chunk1_text.split())
            words2 = set(chunk2_text.split())
            overlap = words1.intersection(words2)
            assert len(overlap) > 0

    def test_add_context_to_chunks(self, contextualizer):
        """Test adding context to existing chunks."""
        full_document = "This is the beginning. This is the middle. This is the end."
        
        existing_chunks = [
            {
                "content": "This is the beginning.",
                "start_offset": 0,
                "metadata": {}
            },
            {
                "content": "This is the middle.",
                "start_offset": 22,
                "metadata": {}
            }
        ]
        
        contextualized = contextualizer.add_context_to_chunks(
            existing_chunks,
            full_document
        )
        
        assert len(contextualized) == 2
        assert all(isinstance(c, DocumentChunk) for c in contextualized)

    def test_add_context_with_summary(self, contextualizer):
        """Test adding context with document summary."""
        full_document = "Content here."
        existing_chunks = [{"content": "Content here.", "start_offset": 0, "metadata": {}}]
        
        contextualized = contextualizer.add_context_to_chunks(
            existing_chunks,
            full_document,
            document_summary="Test summary"
        )
        
        assert "Document summary" in contextualized[0].context_prefix

    def test_split_long_sentence(self, contextualizer):
        """Test splitting very long sentences."""
        # Test with a sentence that has natural split points
        long_sentence = "This is a very long sentence, that needs to be split, into multiple parts, because it's too long, for a single chunk." * 5
        
        parts = contextualizer._split_long_sentence(long_sentence, max_length=100)
        
        assert len(parts) >= 1
        assert all(len(p) <= 150 for p in parts)

    def test_process_chinese_text(self, contextualizer):
        """Test processing Chinese text."""
        content = "这是一个测试文档。它包含中文句子。我们来测试一下。"
        
        chunks = contextualizer.process_document(content)
        
        assert len(chunks) >= 1
        assert "测试" in chunks[0].content

    def test_process_mixed_language(self, contextualizer):
        """Test processing mixed Chinese and English text."""
        content = "这是中文。This is English. 又是中文。"
        
        chunks = contextualizer.process_document(content)
        
        assert len(chunks) >= 1
        assert "中文" in chunks[0].content or "English" in chunks[0].content
