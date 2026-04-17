"""Tests for code_review domain plugin."""

import pytest
from cee_core.domains.code_review import (
    CODE_REVIEW_DOMAIN_NAME,
    CODE_REVIEW_PLUGIN_PACK,
    build_code_review_tool_registry,
)
from cee_core.domain_plugins import DomainPluginPack


class TestCodeReviewDomain:
    """Tests for code review domain configuration."""

    def test_domain_name_is_set(self):
        """Test that domain name is correctly configured."""
        assert CODE_REVIEW_DOMAIN_NAME == "code_review"

    def test_plugin_pack_has_correct_domain(self):
        """Test that plugin pack has the correct domain name."""
        assert CODE_REVIEW_PLUGIN_PACK.domain_name == CODE_REVIEW_DOMAIN_NAME

    def test_plugin_pack_has_rules(self):
        """Test that plugin pack contains rule packs."""
        assert len(CODE_REVIEW_PLUGIN_PACK.rule_packs) > 0
        rules_pack = CODE_REVIEW_PLUGIN_PACK.rule_packs[0]
        assert rules_pack.name == "code_review_rules"
        assert len(rules_pack.rules) >= 5
        assert "all code changes must have test coverage > 80%" in rules_pack.rules

    def test_plugin_pack_has_glossary(self):
        """Test that plugin pack contains glossary packs."""
        assert len(CODE_REVIEW_PLUGIN_PACK.glossary_packs) > 0
        glossary_pack = CODE_REVIEW_PLUGIN_PACK.glossary_packs[0]
        assert glossary_pack.name == "code_review_glossary"
        assert "coverage" in glossary_pack.terms
        assert "security-sensitive" in glossary_pack.terms

    def test_plugin_pack_has_evaluators(self):
        """Test that plugin pack contains evaluator plugins."""
        assert len(CODE_REVIEW_PLUGIN_PACK.evaluators) > 0
        evaluator_names = [e.name for e in CODE_REVIEW_PLUGIN_PACK.evaluators]
        assert "test_coverage_validator" in evaluator_names
        assert "security_audit_check" in evaluator_names
        assert "dependency_safety" in evaluator_names

    def test_plugin_pack_approval_required_sections(self):
        """Test that plugin pack has approval required sections."""
        assert "self_model" in CODE_REVIEW_PLUGIN_PACK.approval_required_patch_sections
        assert "goals" in CODE_REVIEW_PLUGIN_PACK.approval_required_patch_sections


class TestCodeReviewTools:
    """Tests for code review domain tools."""

    def test_build_tool_registry(self):
        """Test that tool registry can be built."""
        registry = build_code_review_tool_registry()
        assert registry is not None

    def test_registry_contains_analyze_code(self):
        """Test that registry contains analyze_code tool."""
        registry = build_code_review_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "analyze_code" in tool_names

    def test_registry_contains_check_coverage(self):
        """Test that registry contains check_coverage tool."""
        registry = build_code_review_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "check_coverage" in tool_names

    def test_registry_contains_audit_dependencies(self):
        """Test that registry contains audit_dependencies tool."""
        registry = build_code_review_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "audit_dependencies" in tool_names

    def test_registry_contains_run_linters(self):
        """Test that registry contains run_linters tool."""
        registry = build_code_review_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "run_linters" in tool_names

    def test_all_tools_are_read_only(self):
        """Test that all code review tools are read-only (safe)."""
        registry = build_code_review_tool_registry()
        tools = registry.list()
        for tool in tools:
            assert tool.risk == "read", f"Tool {tool.name} should be read-only"

    def test_analyze_code_tool_schema(self):
        """Test analyze_code tool has correct input schema."""
        registry = build_code_review_tool_registry()
        tool = registry.get("analyze_code")
        assert tool is not None
        assert "file_path" in tool.input_schema["required"]
        assert "analysis_type" in tool.input_schema["properties"]

    def test_check_coverage_tool_schema(self):
        """Test check_coverage tool has correct input schema."""
        registry = build_code_review_tool_registry()
        tool = registry.get("check_coverage")
        assert tool is not None
        assert "module" in tool.input_schema["required"]
        assert "threshold" in tool.input_schema["properties"]


class TestCodeReviewVsDocumentAnalysis:
    """Tests comparing code_review with document_analysis domains."""

    def test_domains_have_different_names(self):
        """Test that the two domains have distinct names."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_DOMAIN_NAME
        
        assert CODE_REVIEW_DOMAIN_NAME != DOCUMENT_ANALYSIS_DOMAIN_NAME

    def test_domains_have_different_rule_sets(self):
        """Test that the two domains have different rules."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_PLUGIN_PACK
        
        code_review_rules = CODE_REVIEW_PLUGIN_PACK.rule_packs[0].rules
        doc_analysis_rules = DOCUMENT_ANALYSIS_PLUGIN_PACK.rule_packs[0].rules
        
        # They should have different rules
        assert code_review_rules != doc_analysis_rules
        # Code review focuses on code quality
        assert any("coverage" in rule for rule in code_review_rules)
        # Document analysis focuses on sources
        assert any("source" in rule.lower() for rule in doc_analysis_rules)

    def test_domains_have_different_glossaries(self):
        """Test that the two domains have domain-specific glossaries."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_PLUGIN_PACK
        
        code_review_terms = set()
        for pack in CODE_REVIEW_PLUGIN_PACK.glossary_packs:
            code_review_terms.update(pack.terms.keys())
        
        doc_analysis_terms = set()
        for pack in DOCUMENT_ANALYSIS_PLUGIN_PACK.glossary_packs:
            doc_analysis_terms.update(pack.terms.keys())
        
        # They should have different terms
        assert code_review_terms != doc_analysis_terms
        # Code review has code-specific terms
        assert "coverage" in code_review_terms or "security-sensitive" in code_review_terms
        # Document analysis has document-specific terms
        assert "source" in doc_analysis_terms or "claim" in doc_analysis_terms
