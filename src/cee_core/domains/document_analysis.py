"""Document analysis domain plugin.

This is the first real domain plugin for CEE, implementing the MVP target:
"multi-step document analysis with traceable conclusions."

Domain rules:
- Conclusions require at least 2 independent sources
- All claims must carry provenance
- Memory writes require evidence metadata (enforced by confidence gate)

Domain tools:
- read_docs: read document content
- search_index: search document index
- extract_entities: extract named entities from text

All tools are read-only (risk="read").
"""

from __future__ import annotations

from cee_core.domain_plugins import (
    ConnectorSpec,
    DomainPluginPack,
    DomainRulePack,
    EvaluatorPlugin,
    GlossaryPack,
)
from cee_core.tools import ToolRegistry, ToolSpec


DOCUMENT_ANALYSIS_DOMAIN_NAME = "document_analysis"


DOCUMENT_ANALYSIS_PLUGIN_PACK = DomainPluginPack(
    domain_name=DOCUMENT_ANALYSIS_DOMAIN_NAME,
    rule_packs=(
        DomainRulePack(
            name="document_analysis_rules",
            version="1.0",
            rules=(
                "conclusions require at least 2 independent sources",
                "all claims must carry provenance",
                "memory writes require evidence metadata",
                "belief confidence below 0.8 requires human review",
            ),
        ),
    ),
    glossary_packs=(
        GlossaryPack(
            name="document_analysis_glossary",
            version="1.0",
            terms={
                "source": "an independent document or data reference",
                "claim": "a factual assertion extracted from source material",
                "conclusion": "a synthesized judgment backed by multiple sources",
                "provenance": "the origin chain of a piece of information",
                "entity": "a named person, organization, or concept in a document",
            },
        ),
    ),
    evaluators=(
        EvaluatorPlugin(
            name="source_coverage",
            version="1.0",
            target="beliefs",
            metrics=("source_count", "independent_source_ratio"),
        ),
        EvaluatorPlugin(
            name="conclusion_traceability",
            version="1.0",
            target="beliefs",
            metrics=("provenance_depth", "claim_to_source_ratio"),
        ),
    ),
    connectors=(),
    state_extensions=(),
    denied_patch_sections=(),
    approval_required_patch_sections=("self_model",),
)


def build_document_analysis_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="read_docs",
        description="Read document content from the analysis corpus",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for documents"},
                "max_results": {"type": "integer", "description": "Maximum number of results"},
            },
            "required": ["query"],
        },
    ))
    registry.register(ToolSpec(
        name="search_index",
        description="Search the document index for relevant entries",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search terms",
                },
            },
            "required": ["terms"],
        },
    ))
    registry.register(ToolSpec(
        name="extract_entities",
        description="Extract named entities from document text",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to extract entities from"},
                "entity_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity types to extract (person, org, location)",
                },
            },
            "required": ["text"],
        },
    ))
    return registry
