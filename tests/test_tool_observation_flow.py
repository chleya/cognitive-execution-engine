import json
from cee_core import (
    DomainPluginPack,
    EventLog,
    InMemoryReadOnlyToolRunner,
    ToolCallSpec,
    ToolRegistry,
    ToolSpec,
    build_domain_context,
    run_read_only_tool_observation_flow,
)


def _runner():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="read_docs", description="Read docs", risk="read"))
    registry.register(ToolSpec(name="write_doc", description="Write doc", risk="write"))
    runner = InMemoryReadOnlyToolRunner(registry=registry)
    runner.register_handler("read_docs", lambda args: {"hits": 2, "query": args["query"]})
    return runner


def test_tool_observation_flow_without_promotion_is_audit_only():
    log = EventLog()
    result = run_read_only_tool_observation_flow(
        ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        _runner(),
        event_log=log,
    )

    ws = log.replay_world_state()
    event_types = [event.event_type for event in log.all()]

    assert result.observation is not None
    assert result.promotion_delta is None
    assert "tool.call.proposed" in event_types
    assert "tool.call.result" in event_types
    assert "observation.candidate.recorded" in event_types
    assert ws.state_id == "ws_0"


def test_tool_observation_flow_with_explicit_promotion_updates_belief_via_replay():
    log = EventLog()
    result = run_read_only_tool_observation_flow(
        ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        _runner(),
        event_log=log,
        promote_to_belief_key="tool.read_docs.result",
    )

    ws = log.replay_world_state()

    assert result.promotion_delta is not None
    assert ws.state_id != "ws_0"
    entity = ws.find_entity("belief-tool.read_docs.result")
    assert entity is not None
    belief_data = json.loads(entity.summary)
    assert belief_data["content"] == {
        "hits": 2,
        "query": "risk",
    }


def test_tool_observation_flow_blocked_tool_does_not_observe_or_promote():
    log = EventLog()
    result = run_read_only_tool_observation_flow(
        ToolCallSpec(tool_name="write_doc", arguments={"content": "x"}),
        _runner(),
        event_log=log,
        promote_to_belief_key="tool.write_doc.result",
    )

    ws = log.replay_world_state()
    event_types = [event.event_type for event in log.all()]

    assert result.tool_call_event.decision.verdict == "requires_approval"
    assert result.tool_result_event.status == "failed"
    assert result.observation is None
    assert result.promotion_delta is None
    assert "tool.call.proposed" in event_types
    assert "tool.call.result" in event_types
    assert ws.state_id == "ws_0"


def test_tool_observation_flow_unknown_tool_does_not_observe_or_promote():
    log = EventLog()
    result = run_read_only_tool_observation_flow(
        ToolCallSpec(tool_name="unknown", arguments={}),
        _runner(),
        event_log=log,
        promote_to_belief_key="tool.unknown.result",
    )

    assert result.tool_call_event.decision.verdict == "deny"
    assert result.tool_result_event.status == "failed"
    assert result.observation is None
    assert result.promotion_delta is None
    assert log.replay_world_state().state_id == "ws_0"


def test_tool_observation_flow_promotion_respects_domain_overlay():
    log = EventLog()
    domain_ctx = build_domain_context("compliance-review")
    domain_ctx = type(domain_ctx)(
        domain_name=domain_ctx.domain_name,
        plugin_pack=DomainPluginPack(
            domain_name="compliance-review",
            approval_required_patch_sections=("beliefs",),
        ),
    )

    result = run_read_only_tool_observation_flow(
        ToolCallSpec(tool_name="read_docs", arguments={"query": "risk"}),
        _runner(),
        event_log=log,
        promote_to_belief_key="tool.read_docs.result",
        domain_context=domain_ctx,
    )

    assert result.promotion_delta is not None
    ws = log.replay_world_state()
    entity = ws.find_entity("belief-tool.read_docs.result")
    assert entity is None
    from cee_core.commitment import CommitmentEvent
    promotion_commitments = [
        event
        for event in log.all()
        if isinstance(event, CommitmentEvent) and event.requires_approval
    ]
    assert len(promotion_commitments) >= 1
