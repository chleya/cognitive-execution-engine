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
from cee_core.world_state import WorldState


def _docs_runner() -> InMemoryReadOnlyToolRunner:
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"query": args["query"], "hits": 2})
    return runner


def test_world_state_snapshot_matches_result_for_standard_run():
    result = execute_task("analyze project risk")
    artifact = run_result_to_artifact(result)

    assert artifact.world_state_snapshot is not None
    artifact_ws = WorldState.from_dict(artifact.world_state_snapshot)
    assert result.world_state is not None
    assert artifact_ws == result.world_state


def test_tool_results_do_not_become_beliefs_without_explicit_promotion():
    result = execute_task_in_domain(
        "read docs about runtime policy",
        build_domain_context("core"),
        tool_runner=_docs_runner(),
        promote_tool_observations_to_belief_keys={},
    )

    assert result.plan_result.allowed_tool_calls
    assert result.world_state is not None


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

    memory_decisions = [
        d for d in result.plan_result.policy_decisions
        if "memory" in d.reason.lower()
    ]
    assert len(memory_decisions) == 1
    assert not memory_decisions[0].allowed
    assert not memory_decisions[0].requires_approval


def test_narration_lines_are_derived_from_event_log():
    result = execute_task("analyze project risk")

    assert render_event_narration(result.event_log.all()) == run_result_to_artifact(result).narration_lines
