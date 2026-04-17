import pytest

from cee_core import (
    ConnectorSpec,
    DomainPluginPack,
    DomainPluginRegistry,
    DomainRulePack,
    EvaluatorPlugin,
    GlossaryPack,
    PolicyDecision,
    State,
    StatePatch,
    apply_patch,
    evaluate_patch_policy,
)


def test_domain_plugin_registry_registers_and_lists_packs():
    registry = DomainPluginRegistry()
    pack = DomainPluginPack(
        domain_name="document-analysis",
        rule_packs=(DomainRulePack(name="doc-rules", version="v1"),),
        glossary_packs=(GlossaryPack(name="doc-terms", version="v1"),),
        evaluators=(
            EvaluatorPlugin(
                name="traceability",
                version="v1",
                target="document-analysis",
                metrics=("citation_coverage",),
            ),
        ),
        connectors=(
            ConnectorSpec(
                name="local_documents",
                kind="filesystem-readonly",
                config_schema={"root": "string"},
            ),
        ),
        state_extensions=("domain_constraints", "active_entities"),
    )

    registry.register(pack)

    assert registry.get("document-analysis") == pack
    assert registry.list() == (pack,)


def test_domain_plugin_registry_rejects_duplicate_domain_names():
    registry = DomainPluginRegistry()
    pack = DomainPluginPack(domain_name="document-analysis")

    registry.register(pack)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(pack)


def test_domain_data_patch_is_allowed_by_policy():
    patch = StatePatch(
        section="domain_data",
        key="active_entities",
        op="set",
        value=["bridge-1"],
    )

    decision = evaluate_patch_policy(patch)

    assert decision == PolicyDecision(
        verdict="allow",
        reason="domain_data patch allowed by Stage 0 policy",
        policy_ref="stage0.patch-policy:v1",
    )


def test_domain_data_patch_updates_state_snapshot():
    state = State()
    patch = StatePatch(
        section="domain_data",
        key="risk_cases",
        op="set",
        value={"rc-1": "open"},
    )

    next_state = apply_patch(state, patch)

    assert next_state.domain_data["risk_cases"] == {"rc-1": "open"}
    assert next_state.meta["version"] == 1
