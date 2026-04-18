"""Real tool implementations for document analysis domain.

Provides actual document parsing, keyword extraction, and analysis tools
that integrate with the CEE tool execution framework.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, List, Dict, Optional

from ..tool_executor import ToolExecutionContext, ToolExecutionResult


def _extract_keywords(text: str, top_k: int = 20) -> List[str]:
    """Extract keywords from text using frequency analysis."""
    words = re.findall(r'\b\w{3,}\b', text.lower())
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
        'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'from', 'this',
        'that', 'they', 'with', 'will', 'each', 'make', 'like', 'just', 'over',
        'such', 'more', 'than', 'them', 'very', 'when', 'what', 'which', 'their',
        'there', 'about', 'into', 'could', 'other', 'also', 'some', 'these',
        'would', 'only', 'then', 'may', 'should', 'must', 'might', 'shall',
    }
    filtered = [w for w in words if w not in stop_words]
    return [word for word, _ in Counter(filtered).most_common(top_k)]


def _extract_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]


def _calculate_readability(text: str) -> Dict[str, Any]:
    """Calculate basic readability metrics."""
    words = text.split()
    sentences = _extract_sentences(text)
    
    if not words or not sentences:
        return {"avg_words_per_sentence": 0, "avg_word_length": 0}
    
    avg_words = len(words) / len(sentences)
    avg_length = sum(len(w) for w in words) / len(words)
    
    return {
        "avg_words_per_sentence": round(avg_words, 2),
        "avg_word_length": round(avg_length, 2),
        "word_count": len(words),
        "sentence_count": len(sentences),
    }


def handle_analyze_document(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Analyze a document and return structured information."""
    content = ctx.arguments.get("content", "")
    if not content or not isinstance(content, str):
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="content argument is required and must be a non-empty string",
        )

    keywords = _extract_keywords(content, top_k=ctx.arguments.get("top_k", 20))
    readability = _calculate_readability(content)
    sentences = _extract_sentences(content)
    
    result = {
        "keywords": keywords,
        "readability": readability,
        "sentence_count": len(sentences),
        "char_count": len(content),
    }

    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )


def handle_search_document(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Search for patterns or keywords in document content."""
    content = ctx.arguments.get("content", "")
    query = ctx.arguments.get("query", "")
    
    if not content or not query:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="both content and query arguments are required",
        )

    matches = re.finditer(re.escape(query), content, re.IGNORECASE)
    positions = [(m.start(), m.end()) for m in matches]
    
    sentences = _extract_sentences(content)
    matching_sentences = [
        s for s in sentences if query.lower() in s.lower()
    ]

    result = {
        "match_count": len(positions),
        "positions": positions[:10],
        "matching_sentences": matching_sentences[:5],
        "query": query,
    }

    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result=result,
    )


def handle_summarize_document(ctx: ToolExecutionContext) -> ToolExecutionResult:
    """Generate an extractive summary based on sentence scoring."""
    content = ctx.arguments.get("content", "")
    max_sentences = ctx.arguments.get("max_sentences", 3)
    
    if not content:
        return ToolExecutionResult(
            tool_name=ctx.tool_name,
            call_id=ctx.call_id,
            status="failed",
            error_message="content argument is required",
        )

    sentences = _extract_sentences(content)
    if len(sentences) <= max_sentences:
        summary = " ".join(sentences)
    else:
        keywords = _extract_keywords(content, top_k=10)
        sentence_scores = []
        for sentence in sentences:
            score = sum(1 for kw in keywords if kw in sentence.lower())
            sentence_scores.append((sentence, score))
        
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [s for s, _ in sentence_scores[:max_sentences]]
        summary = " ".join(top_sentences)

    return ToolExecutionResult(
        tool_name=ctx.tool_name,
        call_id=ctx.call_id,
        status="succeeded",
        result={
            "summary": summary,
            "original_length": len(content),
            "summary_length": len(summary),
            "compression_ratio": round(len(summary) / len(content), 2) if content else 0,
        },
    )
