"""Tests for image_control_generation domain plugin."""

import pytest
from cee_core.domains.image_control_generation import (
    IMAGE_CONTROL_DOMAIN_NAME,
    IMAGE_CONTROL_PLUGIN_PACK,
    build_image_control_tool_registry,
)
from cee_core.domain_plugins import DomainPluginPack


class TestImageControlDomain:
    """Tests for image control generation domain configuration."""

    def test_domain_name_is_set(self):
        """Test that domain name is correctly configured."""
        assert IMAGE_CONTROL_DOMAIN_NAME == "image_control_generation"

    def test_plugin_pack_has_correct_domain(self):
        """Test that plugin pack has the correct domain name."""
        assert IMAGE_CONTROL_PLUGIN_PACK.domain_name == IMAGE_CONTROL_DOMAIN_NAME

    def test_plugin_pack_has_rules(self):
        """Test that plugin pack contains rule packs."""
        assert len(IMAGE_CONTROL_PLUGIN_PACK.rule_packs) > 0
        rules_pack = IMAGE_CONTROL_PLUGIN_PACK.rule_packs[0]
        assert rules_pack.name == "image_control_rules"
        assert len(rules_pack.rules) >= 5
        assert "all generated images must include control metadata" in rules_pack.rules

    def test_plugin_pack_has_glossary(self):
        """Test that plugin pack contains glossary packs."""
        assert len(IMAGE_CONTROL_PLUGIN_PACK.glossary_packs) > 0
        glossary_pack = IMAGE_CONTROL_PLUGIN_PACK.glossary_packs[0]
        assert glossary_pack.name == "image_control_glossary"
        assert "control-signal" in glossary_pack.terms
        assert "prompt" in glossary_pack.terms

    def test_plugin_pack_has_evaluators(self):
        """Test that plugin pack contains evaluator plugins."""
        assert len(IMAGE_CONTROL_PLUGIN_PACK.evaluators) > 0
        evaluator_names = [e.name for e in IMAGE_CONTROL_PLUGIN_PACK.evaluators]
        assert "prompt_safety_validator" in evaluator_names
        assert "image_quality_assessment" in evaluator_names
        assert "metadata_compliance" in evaluator_names

    def test_plugin_pack_approval_required_sections(self):
        """Test that plugin pack has approval required sections."""
        assert "self_model" in IMAGE_CONTROL_PLUGIN_PACK.approval_required_patch_sections
        assert "goals" in IMAGE_CONTROL_PLUGIN_PACK.approval_required_patch_sections


class TestImageControlTools:
    """Tests for image control generation domain tools."""

    def test_build_tool_registry(self):
        """Test that tool registry can be built."""
        registry = build_image_control_tool_registry()
        assert registry is not None

    def test_registry_contains_validate_prompt(self):
        """Test that registry contains validate_prompt tool."""
        registry = build_image_control_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "validate_prompt" in tool_names

    def test_registry_contains_check_parameters(self):
        """Test that registry contains check_parameters tool."""
        registry = build_image_control_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "check_parameters" in tool_names

    def test_registry_contains_generate_image_control(self):
        """Test that registry contains generate_image_control tool."""
        registry = build_image_control_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "generate_image_control" in tool_names

    def test_registry_contains_verify_metadata(self):
        """Test that registry contains verify_metadata tool."""
        registry = build_image_control_tool_registry()
        tools = registry.list()
        tool_names = [t.name for t in tools]
        assert "verify_metadata" in tool_names

    def test_tool_risk_levels(self):
        """Test that tools have appropriate risk levels."""
        registry = build_image_control_tool_registry()
        tools = registry.list()
        
        risk_map = {tool.name: tool.risk for tool in tools}
        
        # Validation tools should be read-only
        assert risk_map.get("validate_prompt") == "read"
        assert risk_map.get("check_parameters") == "read"
        assert risk_map.get("verify_metadata") == "read"
        
        # Generation tool should be low risk (write operation)
        assert risk_map.get("generate_image_control") == "low"

    def test_validate_prompt_tool_schema(self):
        """Test validate_prompt tool has correct input schema."""
        registry = build_image_control_tool_registry()
        tool = registry.get("validate_prompt")
        assert tool is not None
        assert "prompt" in tool.input_schema["required"]
        assert "check_copyright" in tool.input_schema["properties"]

    def test_generate_image_control_tool_schema(self):
        """Test generate_image_control tool has correct input schema."""
        registry = build_image_control_tool_registry()
        tool = registry.get("generate_image_control")
        assert tool is not None
        assert "prompt" in tool.input_schema["required"]
        assert "control_type" in tool.input_schema["required"]
        assert "control_type" in tool.input_schema["properties"]
        # Check enum values
        control_type_prop = tool.input_schema["properties"]["control_type"]
        assert "enum" in control_type_prop
        assert "pose" in control_type_prop["enum"]
        assert "depth" in control_type_prop["enum"]


class TestAllDomainsComparison:
    """Tests comparing all three domains to prove CEE is a general engine."""

    def test_three_domains_have_different_names(self):
        """Test that all three domains have distinct names."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_DOMAIN_NAME
        from cee_core.domains.code_review import CODE_REVIEW_DOMAIN_NAME
        
        domains = [
            DOCUMENT_ANALYSIS_DOMAIN_NAME,
            CODE_REVIEW_DOMAIN_NAME,
            IMAGE_CONTROL_DOMAIN_NAME,
        ]
        
        # All should be unique
        assert len(domains) == len(set(domains))

    def test_three_domains_have_different_rule_sets(self):
        """Test that all three domains have different rules."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_PLUGIN_PACK
        from cee_core.domains.code_review import CODE_REVIEW_PLUGIN_PACK
        
        doc_rules = set(DOCUMENT_ANALYSIS_PLUGIN_PACK.rule_packs[0].rules)
        code_rules = set(CODE_REVIEW_PLUGIN_PACK.rule_packs[0].rules)
        image_rules = set(IMAGE_CONTROL_PLUGIN_PACK.rule_packs[0].rules)
        
        # All rule sets should be different
        assert doc_rules != code_rules
        assert doc_rules != image_rules
        assert code_rules != image_rules

    def test_three_domains_have_different_glossaries(self):
        """Test that all three domains have domain-specific glossaries."""
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_PLUGIN_PACK
        from cee_core.domains.code_review import CODE_REVIEW_PLUGIN_PACK
        
        doc_terms = set()
        for pack in DOCUMENT_ANALYSIS_PLUGIN_PACK.glossary_packs:
            doc_terms.update(pack.terms.keys())
        
        code_terms = set()
        for pack in CODE_REVIEW_PLUGIN_PACK.glossary_packs:
            code_terms.update(pack.terms.keys())
        
        image_terms = set()
        for pack in IMAGE_CONTROL_PLUGIN_PACK.glossary_packs:
            image_terms.update(pack.terms.keys())
        
        # All should have different terms
        assert doc_terms != code_terms
        assert doc_terms != image_terms
        assert code_terms != image_terms

    def test_three_domains_demonstrate_engine_generality(self):
        """Test that three domains prove CEE is a general engine."""
        # Document analysis: analysis domain
        # Code review: code quality domain
        # Image control: creative generation domain
        
        # Each domain should have at least one unique characteristic
        from cee_core.domains.document_analysis import DOCUMENT_ANALYSIS_PLUGIN_PACK
        from cee_core.domains.code_review import CODE_REVIEW_PLUGIN_PACK
        
        doc_evaluators = set(e.name for e in DOCUMENT_ANALYSIS_PLUGIN_PACK.evaluators)
        code_evaluators = set(e.name for e in CODE_REVIEW_PLUGIN_PACK.evaluators)
        image_evaluators = set(e.name for e in IMAGE_CONTROL_PLUGIN_PACK.evaluators)
        
        # Each domain has different evaluators
        assert doc_evaluators != code_evaluators
        assert doc_evaluators != image_evaluators
        assert code_evaluators != image_evaluators
