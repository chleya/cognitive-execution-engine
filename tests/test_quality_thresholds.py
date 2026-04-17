from cee_core import (
    DomainPluginPack,
    InMemoryReadOnlyToolRunner,
    ToolRegistry,
    ToolSpec,
    assess_quality_gates,
    assess_quality_gates_for_run,
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


def test_quality_gates_pass_core_checks_for_standard_run():
    metrics = compute_quality_metrics(execute_task("analyze project risk"))
    gates = assess_quality_gates(metrics)
    check_by_name = {check.name: check for check in gates.checks}

    assert gates.overall_status == "insufficient_evidence"
    assert check_by_name["replay_consistency"].status == "pass"
    assert check_by_name["schema_event_validity"].status == "pass"
    assert check_by_name["unauthorized_tool_execution"].status == "insufficient_evidence"


def test_quality_gates_for_tool_run_have_tool_evidence():
    result = execute_task_in_domain(
        "read docs about runtime policy",
        build_domain_context("core"),
        tool_runner=_docs_runner(),
        promote_tool_observations_to_belief_keys={},
    )
    gates = assess_quality_gates_for_run(result)
    check_by_name = {check.name: check for check in gates.checks}

    assert check_by_name["unauthorized_tool_execution"].status == "pass"
    assert check_by_name["automatic_belief_promotion"].status == "pass"


def test_quality_gates_for_domain_overlay_use_domain_evidence():
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )
    gates = assess_quality_gates_for_run(
        execute_task_in_domain("update the project belief summary", domain_ctx)
    )
    check_by_name = {check.name: check for check in gates.checks}

    assert check_by_name["domain_tightening_integrity"].status == "pass"
