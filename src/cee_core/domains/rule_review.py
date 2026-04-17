"""Rule review domain plugin.

This is the second domain plugin for CEE, used to verify the core engine
can support multiple domains without modification.

Domain rules:
- Compliance checks must reference at least one applicable regulation
- High-risk compliance gaps require explicit human approval
- All findings must include severity assessment
- Remediation recommendations require evidence of feasibility

Domain tools:
- check_compliance: Check content against compliance rules
- find_regulations: Find applicable regulations for content
- assess_risk: Assess risk level of compliance findings
- generate_remediation: Generate remediation recommendations
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


RULE_REVIEW_DOMAIN_NAME = "rule_review"


RULE_REVIEW_PLUGIN_PACK = DomainPluginPack(
    domain_name=RULE_REVIEW_DOMAIN_NAME,
    rule_packs=(
        DomainRulePack(
            name="rule_review_rules",
            version="1.0",
            rules=(
                "compliance checks must reference at least one applicable regulation",
                "high-risk compliance gaps require explicit human approval",
                "all findings must include severity assessment",
                "remediation recommendations require evidence of feasibility",
                "severity score above 0.7 requires human review",
            ),
        ),
    ),
    glossary_packs=(
        GlossaryPack(
            name="rule_review_glossary",
            version="1.0",
            terms={
                "compliance_rule": "a specific regulatory requirement or organizational policy",
                "compliance_gap": "a discrepancy between content and applicable rules",
                "severity": "the impact level of a compliance issue (critical/high/medium/low)",
                "remediation": "action plan to address a compliance gap",
                "regulation_reference": "official citation of a regulatory requirement",
                "risk_assessment": "evaluation of likelihood and impact of non-compliance",
            },
        ),
    ),
    evaluators=(
        EvaluatorPlugin(
            name="compliance_coverage",
            version="1.0",
            target="beliefs",
            metrics=("rule_coverage", "gap_detection_rate"),
        ),
        EvaluatorPlugin(
            name="remediation_quality",
            version="1.0",
            target="beliefs",
            metrics=("feasibility_score", "implementation_time_estimate"),
        ),
    ),
    connectors=(),
    state_extensions=(),
    denied_patch_sections=(),
    approval_required_patch_sections=("self_model",),
)


def build_rule_review_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="check_compliance",
        description="Check content against compliance rules and identify gaps",
        risk="read",
        reversible=True,
        observable_result=True,
        evidence_required=0.3,
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to check for compliance"},
                "rule_set": {"type": "string", "description": "Rule set to use (e.g., 'gdpr', 'sox', 'internal_policy')"},
                "depth": {"type": "string", "description": "Review depth: 'basic', 'detailed', 'comprehensive'"},
            },
            "required": ["content", "rule_set"],
        },
    ))
    registry.register(ToolSpec(
        name="find_regulations",
        description="Find applicable regulations for given content",
        risk="read",
        reversible=True,
        observable_result=True,
        evidence_required=0.2,
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to analyze"},
                "jurisdiction": {"type": "string", "description": "Jurisdiction to consider (e.g., 'us', 'eu', 'global')"},
                "industry": {"type": "string", "description": "Industry sector (e.g., 'finance', 'healthcare', 'tech')"},
            },
            "required": ["content"],
        },
    ))
    registry.register(ToolSpec(
        name="assess_risk",
        description="Assess risk level and severity of compliance findings",
        risk="read",
        reversible=True,
        observable_result=True,
        evidence_required=0.5,
        input_schema={
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of compliance findings to assess",
                },
                "context": {"type": "string", "description": "Additional context for risk assessment"},
            },
            "required": ["findings"],
        },
    ))
    registry.register(ToolSpec(
        name="generate_remediation",
        description="Generate actionable remediation recommendations",
        risk="read",
        reversible=True,
        observable_result=True,
        evidence_required=0.6,
        input_schema={
            "type": "object",
            "properties": {
                "gaps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of compliance gaps to address",
                },
                "constraints": {"type": "string", "description": "Implementation constraints (time, budget, resources)"},
                "priority_framework": {"type": "string", "description": "Priority framework: 'risk_based', 'quick_wins_first', 'regulatory_deadline'"},
            },
            "required": ["gaps"],
        },
    ))
    return registry
