from cee_core import (
    DomainPluginPack,
    InMemoryReadOnlyToolRunner,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    execute_task,
    execute_task_in_domain,
    render_event_narration,
    run_result_to_artifact,
)


def _docs_runner() -> InMemoryReadOnlyToolRunner:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})
    return runner


def test_replay_matches_run_artifact_replay_for_standard_run():
    result = execute_task("analyze project risk")
    artifact = run_result_to_artifact(result)

    assert artifact.replay_state().snapshot() == result.replayed_state.snapshot()


def test_tool_results_do_not_become_beliefs_without_explicit_promotion():
    result = execute_task_in_domain(
        "read docs about runtime policy",
        build_domain_context("core"),
        tool_runner=_docs_runner(),
        promote_tool_observations_to_belief_keys={},
    )

    assert result.plan_result.allowed_tool_calls
    assert result.replayed_state.beliefs[f"task.{result.task.task_id}.objective"] == "read docs about runtime policy"
    assert "tool.read_docs.result" not in result.replayed_state.beliefs


def test_domain_overlay_never_loosens_core_policy():
    domain_ctx = build_domain_context("construction-site")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="construction-site",
            denied_patch_sections=("memory",),
        ),
    )

    result = execute_task_in_domain("update the project belief summary", domain_ctx)

    memory_events = [e for e in result.plan_result.events if e.patch.section == "memory"]
    assert len(memory_events) == 1
    assert memory_events[0].policy_decision.verdict == "deny"


def test_narration_lines_are_derived_from_event_log():
    result = execute_task("analyze project risk")

    assert render_event_narration(result.event_log.all()) == run_result_to_artifact(result).narration_lines
