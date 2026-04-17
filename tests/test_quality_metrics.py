from cee_core import (
    DomainPluginPack,
    InMemoryReadOnlyToolRunner,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    compute_quality_metrics,
    execute_task,
    execute_task_in_domain,
)


def _docs_runner() -> InMemoryReadOnlyToolRunner:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})
    return runner


def test_quality_metrics_for_standard_run_hit_expected_invariants():
    result = execute_task("analyze project risk")
    metrics = compute_quality_metrics(result)

    assert metrics.replay_success_rate == 1.0
    assert metrics.policy_bypass_rate == 0.0
    assert metrics.unauthorized_tool_execution_rate == 0.0
    assert metrics.schema_valid_event_rate == 1.0
    assert metrics.audit_coverage_rate == 1.0
    assert metrics.narration_consistency_rate == 1.0
    assert metrics.allowed_transition_count == 4
    assert metrics.blocked_transition_count == 0
    assert metrics.tool_call_count == 0
    assert metrics.total_event_count == 6
    assert metrics.schema_valid_event_count == 6


def test_quality_metrics_for_tool_run_report_observation_counts():
    result = execute_task_in_domain(
        "read docs about runtime policy",
        build_domain_context("core"),
        tool_runner=_docs_runner(),
        promote_tool_observations_to_belief_keys={},
    )
    metrics = compute_quality_metrics(result)

    assert metrics.replay_success_rate == 1.0
    assert metrics.unauthorized_tool_execution_rate == 0.0
    assert metrics.automatic_belief_promotion_rate == 0.0
    assert metrics.tool_call_count == 1
    assert metrics.tool_result_count == 1
    assert metrics.observation_count == 1
    assert metrics.promotion_event_count == 0


def test_quality_metrics_for_domain_overlay_keep_integrity_signal():
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )
    result = execute_task_in_domain("update the project belief summary", domain_ctx)
    metrics = compute_quality_metrics(result)

    assert metrics.domain_tightening_integrity_rate == 1.0
    assert metrics.blocked_transition_count == 2
