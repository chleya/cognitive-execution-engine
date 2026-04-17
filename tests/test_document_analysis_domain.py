import pytest

from cee_core import (
    DomainContext,
    DomainPluginRegistry,
    EventLog,
    State,
    StatePatch,
    evaluate_patch_policy_in_domain,
    execute_task_in_domain,
)
from cee_core.domains.document_analysis import (
    DOCUMENT_ANALYSIS_DOMAIN_NAME,
    DOCUMENT_ANALYSIS_PLUGIN_PACK,
    build_document_analysis_tool_registry,
)


def test_document_analysis_plugin_pack_has_rules():
    assert len(DOCUMENT_ANALYSIS_PLUGIN_PACK.rule_packs) == 1
    rules = DOCUMENT_ANALYSIS_PLUGIN_PACK.rule_packs[0]
    assert rules.name == "document_analysis_rules"
    assert len(rules.rules) >= 3


def test_document_analysis_plugin_pack_has_glossary():
    assert len(DOCUMENT_ANALYSIS_PLUGIN_PACK.glossary_packs) == 1
    glossary = DOCUMENT_ANALYSIS_PLUGIN_PACK.glossary_packs[0]
    assert "source" in glossary.terms
    assert "claim" in glossary.terms
    assert "conclusion" in glossary.terms


def test_document_analysis_plugin_pack_has_evaluators():
    assert len(DOCUMENT_ANALYSIS_PLUGIN_PACK.evaluators) == 2
    names = [e.name for e in DOCUMENT_ANALYSIS_PLUGIN_PACK.evaluators]
    assert "source_coverage" in names
    assert "conclusion_traceability" in names


def test_document_analysis_self_model_requires_approval():
    registry = DomainPluginRegistry()
    registry.register(DOCUMENT_ANALYSIS_PLUGIN_PACK)
    ctx = DomainContext(
        domain_name=DOCUMENT_ANALYSIS_DOMAIN_NAME,
        plugin_pack=DOCUMENT_ANALYSIS_PLUGIN_PACK,
    )

    patch = StatePatch(section="self_model", key="k", op="set", value="v")
    decision = evaluate_patch_policy_in_domain(patch, ctx)

    assert decision.verdict == "requires_approval"


def test_document_analysis_tool_registry_has_three_tools():
    registry = build_document_analysis_tool_registry()
    tools = registry.list()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"read_docs", "search_index", "extract_entities"}


def test_document_analysis_tools_are_all_read_only():
    registry = build_document_analysis_tool_registry()
    for tool in registry.list():
        assert tool.risk == "read"


def test_document_analysis_runs_through_runtime():
    registry = DomainPluginRegistry()
    registry.register(DOCUMENT_ANALYSIS_PLUGIN_PACK)
    ctx = DomainContext(
        domain_name=DOCUMENT_ANALYSIS_DOMAIN_NAME,
        plugin_pack=DOCUMENT_ANALYSIS_PLUGIN_PACK,
    )

    log = EventLog()
    result = execute_task_in_domain("analyze document risk factors", ctx, event_log=log)

    assert result.task.objective == "analyze document risk factors"
    assert result.replayed_state.meta["version"] >= 1
    assert result.event_log.all()
