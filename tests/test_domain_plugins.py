import pytest

from cee_core import (
    ConnectorSpec,
    DomainPluginPack,
    DomainPluginRegistry,
    DomainRulePack,
    EvaluatorPlugin,
    GlossaryPack,
    RevisionDelta,
    WorldState,
    evaluate_delta_policy,
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


def test_domain_data_delta_is_allowed_by_policy():
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="domain_data.active_entities",
        before_summary="not set",
        after_summary='["bridge-1"]',
        justification="test domain data update",
        raw_value=["bridge-1"],
    )

    decision = evaluate_delta_policy(delta)

    assert decision.allowed
    assert not decision.requires_approval


def test_domain_data_delta_updates_world_state_via_replay():
    from cee_core import EventLog, ModelRevisionEvent

    ws = WorldState(state_id="ws_0")
    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="domain_data.risk_cases",
        before_summary="not set",
        after_summary='{"rc-1": "open"}',
        justification="test domain data update",
        raw_value={"rc-1": "open"},
    )

    rev = ModelRevisionEvent(
        revision_id="rev_1",
        prior_state_id="ws_0",
        caused_by_event_id="evt_1",
        revision_kind="expansion",
        deltas=(delta,),
        resulting_state_id="ws_1",
    )

    log = EventLog()
    log.append(rev)

    next_ws = log.replay_world_state(initial=ws)

    entity = next_ws.find_entity("domain-risk_cases")
    assert entity is not None
    assert entity.kind == "domain_data"
