from cee_core import (
    CommitmentEvent,
    DeliberationEvent,
    Event,
    EventLog,
    ModelRevisionEvent,
    ReasoningStep,
    RevisionDelta,
    ToolCallSpec,
    ToolPolicyDecision,
    ToolResultEvent,
    WorldState,
    build_observation_event,
    observation_from_tool_result,
    render_event_narration,
)
from cee_core.tools import ToolCallEvent


def test_render_event_narration_covers_small_step_flow():
    tool_result = ToolResultEvent(
        call_id="toolcall_1",
        tool_name="read_docs",
        status="succeeded",
        result={"query": "runtime", "hits": 2},
    )
    observation = observation_from_tool_result(tool_result)

    ws = WorldState(state_id="ws_0")
    commitment = CommitmentEvent(
        event_id="evt_obs_1",
        source_state_id="ws_0",
        commitment_kind="observe",
        intent_summary="Read docs about runtime policy",
    )

    delta = RevisionDelta(
        delta_id="d1",
        target_kind="entity_update",
        target_ref="beliefs.tool.read_docs.result",
        before_summary="not set",
        after_summary='{"hits": 2}',
        justification="observation from read_docs",
        raw_value={"hits": 2},
    )
    revision = ModelRevisionEvent(
        revision_id="rev_1",
        prior_state_id="ws_0",
        caused_by_event_id="evt_obs_1",
        revision_kind="expansion",
        deltas=(delta,),
        resulting_state_id="ws_1",
        revision_summary="Updated beliefs from tool result",
    )

    events = (
        Event(event_type="task.received", payload={"objective": "read docs about runtime policy"}),
        DeliberationEvent(
            reasoning_step=ReasoningStep(
                task_id="task_1",
                summary="Select next action",
                hypothesis="Need docs",
                missing_information=("docs not read",),
                candidate_actions=("propose_plan", "request_read_tool"),
                chosen_action="request_read_tool",
                rationale="Need docs first.",
                stop_condition="Stop after action selection.",
            )
        ),
        ToolCallEvent(
            call=ToolCallSpec(tool_name="read_docs", arguments={"query": "runtime"}),
            decision=ToolPolicyDecision(
                verdict="allow",
                reason="read tool allowed",
                tool_name="read_docs",
            ),
        ),
        tool_result,
        build_observation_event(observation),
        commitment,
        revision,
    )

    lines = render_event_narration(events)

    assert lines == (
        "Received task: read docs about runtime policy",
        "Selected next action: request_read_tool",
        "Proposed tool call: read_docs (allow)",
        "Completed tool call: read_docs",
        "Recorded observation from tool: read_docs",
        "Committed observe: Read docs about runtime policy",
        "Revised model (expansion): Updated beliefs from tool result",
    )


def test_render_event_narration_ignores_unknown_event_types():
    log = EventLog()
    log.append(Event(event_type="audit.note", payload={"message": "ignored"}))

    assert render_event_narration(log.all()) == ()
