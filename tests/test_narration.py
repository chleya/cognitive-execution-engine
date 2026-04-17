from cee_core import (
    DeliberationEvent,
    Event,
    EventLog,
    PolicyDecision,
    ReasoningStep,
    StatePatch,
    StateTransitionEvent,
    ToolCallSpec,
    ToolPolicyDecision,
    ToolResultEvent,
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
        StateTransitionEvent(
            patch=StatePatch(section="beliefs", key="tool.read_docs.result", op="set", value={"hits": 2}),
            policy_decision=PolicyDecision(
                verdict="allow",
                reason="beliefs patch allowed",
                policy_ref="stage0.patch-policy:v1",
            ),
        ),
    )

    lines = render_event_narration(events)

    assert lines == (
        "Received task: read docs about runtime policy",
        "Selected next action: request_read_tool",
        "Proposed tool call: read_docs (allow)",
        "Completed tool call: read_docs",
        "Recorded observation from tool: read_docs",
        "Evaluated state patch: beliefs.tool.read_docs.result (allow)",
    )


def test_render_event_narration_ignores_unknown_event_types():
    log = EventLog()
    log.append(Event(event_type="audit.note", payload={"message": "ignored"}))

    assert render_event_narration(log.all()) == ()
