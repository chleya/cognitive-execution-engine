"""End-to-end demo for the document_analysis domain plugin.

This demonstrates the MVP target: multi-step document analysis
with traceable conclusions, running through the full CEE pipeline.
"""

from cee_core import (
    DomainContext,
    DomainPluginRegistry,
    EventLog,
    InMemoryReadOnlyToolRunner,
    QualityMetrics,
    compute_quality_metrics,
    execute_task_in_domain,
    run_result_to_artifact,
)
from cee_core.domains.document_analysis import (
    DOCUMENT_ANALYSIS_DOMAIN_NAME,
    DOCUMENT_ANALYSIS_PLUGIN_PACK,
    build_document_analysis_tool_registry,
)


def main() -> None:
    registry = DomainPluginRegistry()
    registry.register(DOCUMENT_ANALYSIS_PLUGIN_PACK)
    ctx = DomainContext(
        domain_name=DOCUMENT_ANALYSIS_DOMAIN_NAME,
        plugin_pack=DOCUMENT_ANALYSIS_PLUGIN_PACK,
    )

    tool_registry = build_document_analysis_tool_registry()
    tool_runner = InMemoryReadOnlyToolRunner(registry=tool_registry)
    tool_runner.register_handler("read_docs", lambda args: {
        "documents": [
            {"id": "doc_1", "title": "Risk Assessment Report Q1", "content": "..."},
            {"id": "doc_2", "title": "Compliance Audit Findings", "content": "..."},
        ],
        "query": args.get("query", ""),
    })
    tool_runner.register_handler("search_index", lambda args: {
        "matches": [
            {"doc_id": "doc_1", "relevance": 0.92},
            {"doc_id": "doc_2", "relevance": 0.87},
        ],
        "terms": args.get("terms", []),
    })
    tool_runner.register_handler("extract_entities", lambda args: {
        "entities": [
            {"name": "Acme Corp", "type": "organization"},
            {"name": "Regulatory Framework v3", "type": "concept"},
        ],
        "text_length": len(args.get("text", "")),
    })

    log = EventLog()
    result = execute_task_in_domain(
        "analyze document risk factors for compliance review",
        ctx,
        event_log=log,
        tool_runner=tool_runner,
    )

    metrics = compute_quality_metrics(result)

    print("=" * 60)
    print("Document Analysis Domain - End-to-End Demo")
    print("=" * 60)
    print(f"Task: {result.task.objective}")
    print(f"Domain: {result.task.domain_name}")
    print(f"Kind: {result.task.kind}")
    print(f"Risk Level: {result.task.risk_level}")
    print(f"Reasoning Step: {result.reasoning_step.chosen_action}")
    print(f"Plan Objective: {result.plan.objective}")
    print(f"Allowed Transitions: {len(result.allowed_transitions)}")
    print(f"Blocked Transitions: {len(result.blocked_transitions)}")
    print(f"Approval Required: {len(result.approval_required_transitions)}")
    ws = result.world_state
    if ws is not None:
        print(f"WorldState ID: {ws.state_id}")
        print(f"Provenance Refs: {len(ws.provenance_refs)}")
    print(f"Total Events: {metrics.total_event_count}")
    print()
    print("Quality Metrics:")
    print(f"  Replay Success Rate: {metrics.replay_success_rate:.0%}")
    print(f"  Policy Bypass Rate: {metrics.policy_bypass_rate:.0%}")
    print(f"  Schema Valid Event Rate: {metrics.schema_valid_event_rate:.0%}")
    print(f"  Audit Coverage Rate: {metrics.audit_coverage_rate:.0%}")
    print(f"  High-Risk Approval Coverage: {metrics.high_risk_approval_coverage:.0%}")
    print(f"  Domain Tightening Integrity: {metrics.domain_tightening_integrity_rate:.0%}")
    print()

    artifact = run_result_to_artifact(result)
    ws = result.world_state
    if ws is not None:
        print(f"WorldState ID: {ws.state_id}")
        print(f"WorldState Goals: {', '.join(ws.dominant_goals) if ws.dominant_goals else '(none)'}")

    domain_pack = ctx.plugin_pack
    if domain_pack is not None:
        print()
        print("Domain Rules:")
        for pack in domain_pack.rule_packs:
            for rule in pack.rules:
                print(f"  - {rule}")
        print()
        print("Domain Glossary:")
        for pack in domain_pack.glossary_packs:
            for term, definition in pack.terms.items():
                print(f"  {term}: {definition}")

    print()
    print("Demo complete.")


if __name__ == "__main__":
    main()
