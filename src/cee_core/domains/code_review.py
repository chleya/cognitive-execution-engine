"""Code review domain plugin.

This is the second domain for CEE, validating that CEE is a general engine
rather than a single-domain framework.

Domain rules:
- All code changes must have test coverage
- Security-sensitive operations require peer review
- Dependencies must be audited before addition
- Breaking changes require migration plan

Domain tools:
- analyze_code: static analysis of code files
- check_coverage: verify test coverage for changes
- audit_dependencies: check dependency security status
- run_linters: execute code linters

Tools include both read-only (risk="read") and safe-write (risk="low") operations.
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


CODE_REVIEW_DOMAIN_NAME = "code_review"


CODE_REVIEW_PLUGIN_PACK = DomainPluginPack(
    domain_name=CODE_REVIEW_DOMAIN_NAME,
    rule_packs=(
        DomainRulePack(
            name="code_review_rules",
            version="1.0",
            rules=(
                "all code changes must have test coverage > 80%",
                "security-sensitive operations require peer review",
                "new dependencies must be audited before addition",
                "breaking changes require migration plan",
                "no TODO comments without issue tracker reference",
            ),
        ),
    ),
    glossary_packs=(
        GlossaryPack(
            name="code_review_glossary",
            version="1.0",
            terms={
                "coverage": "percentage of code executed by tests",
                "security-sensitive": "operations involving auth, crypto, or data access",
                "breaking-change": "API or behavior change that breaks existing clients",
                "dependency-audit": "verification of third-party package security status",
                "peer-review": "approval from another developer before merge",
                "lint-violation": "code style or quality warning from static analysis",
            },
        ),
    ),
    evaluators=(
        EvaluatorPlugin(
            name="test_coverage_validator",
            version="1.0",
            target="beliefs",
            metrics=("coverage_percentage", "uncovered_branches"),
        ),
        EvaluatorPlugin(
            name="security_audit_check",
            version="1.0",
            target="beliefs",
            metrics=("security_issues", "review_status"),
        ),
        EvaluatorPlugin(
            name="dependency_safety",
            version="1.0",
            target="beliefs",
            metrics=("vulnerable_dependencies", "outdated_packages"),
        ),
    ),
    connectors=(),
    state_extensions=(),
    denied_patch_sections=(),
    approval_required_patch_sections=("self_model", "goals"),
)


def build_code_review_tool_registry() -> ToolRegistry:
    """Build tool registry for code review domain."""
    registry = ToolRegistry()
    
    registry.register(ToolSpec(
        name="analyze_code",
        description="Static analysis of code files for quality and security issues",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to code file"},
                "analysis_type": {
                    "type": "string",
                    "enum": ["quality", "security", "complexity"],
                    "description": "Type of analysis to perform",
                },
            },
            "required": ["file_path"],
        },
    ))
    
    registry.register(ToolSpec(
        name="check_coverage",
        description="Verify test coverage for code changes",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Module to check"},
                "threshold": {"type": "number", "description": "Minimum coverage threshold (0-1)"},
            },
            "required": ["module"],
        },
    ))
    
    registry.register(ToolSpec(
        name="audit_dependencies",
        description="Check dependency security status and licenses",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "dependency_file": {
                    "type": "string",
                    "description": "Path to requirements.txt or package.json",
                },
                "check_licenses": {"type": "boolean", "description": "Whether to check licenses"},
            },
            "required": ["dependency_file"],
        },
    ))
    
    registry.register(ToolSpec(
        name="run_linters",
        description="Execute code linters and style checkers",
        risk="read",
        input_schema={
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of files to lint",
                },
                "linters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Which linters to run (flake8, pylint, black)",
                },
            },
            "required": ["files"],
        },
    ))
    
    return registry
