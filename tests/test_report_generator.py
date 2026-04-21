"""Tests for the report generator."""

import json
import pytest

from cee_core.event_log import EventLog
from cee_core.events import Event, DeliberationEvent
from cee_core.events import Event as BaseEvent
from cee_core.commitment import CommitmentEvent
from cee_core.revision import ModelRevisionEvent
from cee_core.world_schema import RevisionDelta
from cee_core.tools import ToolCallSpec, ToolPolicyDecision, ToolCallEvent, ToolResultEvent
from cee_core.workflow import Workflow, WorkflowStep, WorkflowResult, StepResult
from cee_core.report_generator import ReportGenerator, ReportData, ReportSection


class TestReportData:
    def test_create_report_data(self):
        sections = [
            ReportSection(heading="Summary", content="test content"),
        ]
        data = ReportData(
            run_id="run_001",
            title="Test Report",
            sections=sections,
            metadata={"key": "value"},
        )

        assert data.run_id == "run_001"
        assert data.title == "Test Report"
        assert len(data.sections) == 1
        assert data.metadata["key"] == "value"

    def test_report_data_to_dict(self):
        sections = [
            ReportSection(heading="Summary", content="content", level=2),
        ]
        data = ReportData(
            run_id="run_002",
            title="Dict Report",
            sections=sections,
            metadata={},
        )

        d = data.to_dict()

        assert d["run_id"] == "run_002"
        assert d["title"] == "Dict Report"
        assert len(d["sections"]) == 1
        assert d["sections"][0]["heading"] == "Summary"
        assert d["sections"][0]["level"] == 2


class TestReportSection:
    def test_create_section_default_level(self):
        section = ReportSection(heading="Test", content="body")
        assert section.heading == "Test"
        assert section.content == "body"
        assert section.level == 2

    def test_create_section_custom_level(self):
        section = ReportSection(heading="Test", content="body", level=3)
        assert section.level == 3


class TestReportGeneratorGenerate:
    def test_generate_with_no_data(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="run_empty")

        assert data.run_id == "run_empty"
        assert data.title == "Execution Report: run_empty"
        assert isinstance(data.sections, list)
        assert isinstance(data.metadata, dict)

    def test_generate_default_run_id(self):
        gen = ReportGenerator()
        data = gen.generate()

        assert data.run_id == "unknown"

    def test_generate_with_workflow(self):
        workflow = Workflow(
            name="Test Workflow",
            steps=[
                WorkflowStep(step_id="s1", name="Step 1", action="act1"),
                WorkflowStep(step_id="s2", name="Step 2", action="act2"),
            ],
        )

        gen = ReportGenerator(workflow=workflow)
        data = gen.generate(run_id="run_wf")

        assert data.run_id == "run_wf"
        assert any("Test Workflow" in s.content for s in data.sections)

    def test_generate_with_workflow_result(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_1",
            status="succeeded",
            step_results=[
                StepResult(step_id="s1", status="succeeded", execution_time_ms=100.0),
                StepResult(step_id="s2", status="succeeded", execution_time_ms=200.0),
            ],
            total_execution_time_ms=300.0,
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="run_wr")

        assert data.run_id == "run_wr"
        assert any("succeeded" in s.content.lower() for s in data.sections)

    def test_generate_with_event_log(self):
        event_log = EventLog()
        event_log.append(
            Event(
                event_type="workflow.started",
                payload={"workflow_id": "wf_1"},
                actor="workflow_runner",
            )
        )

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="run_el")

        assert data.run_id == "run_el"

    def test_generate_with_all_data(self):
        workflow = Workflow(
            name="Full Workflow",
            steps=[
                WorkflowStep(step_id="s1", name="Step 1", action="act1"),
            ],
        )

        workflow_result = WorkflowResult(
            workflow_id="wf_1",
            status="succeeded",
            step_results=[
                StepResult(step_id="s1", status="succeeded", execution_time_ms=50.0),
            ],
            variables={"s1_summary": "done"},
            total_execution_time_ms=50.0,
        )

        event_log = EventLog()
        event_log.append(
            Event(
                event_type="workflow.started",
                payload={"workflow_id": "wf_1"},
                actor="workflow_runner",
            )
        )
        event_log.append(
            Event(
                event_type="workflow.completed",
                payload={"workflow_id": "wf_1", "status": "succeeded"},
                actor="workflow_runner",
            )
        )

        metrics_summary = {
            "total_duration_ms": 100.0,
            "phase_durations": {"compilation": 50.0},
            "event_counts": {"workflow.started": 1, "workflow.completed": 1},
            "tool_metrics": {
                "total_executions": 0,
                "avg_execution_time_ms": 0.0,
                "max_execution_time_ms": 0.0,
                "min_execution_time_ms": 0.0,
            },
        }

        gen = ReportGenerator(
            event_log=event_log,
            workflow=workflow,
            workflow_result=workflow_result,
            metrics_summary=metrics_summary,
        )
        data = gen.generate(run_id="run_full")

        assert data.run_id == "run_full"
        assert len(data.sections) > 0
        assert "Full Workflow" in data.metadata.get("workflow_name", "")


class TestRenderMarkdown:
    def test_render_basic_markdown(self):
        gen = ReportGenerator()
        md = gen.render_markdown(run_id="test_run")

        assert "# Execution Report: test_run" in md
        assert isinstance(md, str)
        assert len(md) > 0

    def test_render_markdown_with_workflow(self):
        workflow = Workflow(
            name="MD Workflow",
            steps=[
                WorkflowStep(step_id="s1", name="Step 1", action="act1"),
            ],
        )

        workflow_result = WorkflowResult(
            workflow_id="wf_1",
            status="succeeded",
            step_results=[
                StepResult(step_id="s1", status="succeeded", execution_time_ms=100.0),
            ],
            total_execution_time_ms=100.0,
        )

        gen = ReportGenerator(
            workflow=workflow,
            workflow_result=workflow_result,
        )
        md = gen.render_markdown(run_id="md_test")

        assert "# Execution Report: md_test" in md
        assert "MD Workflow" in md
        assert "succeeded" in md.lower()

    def test_render_markdown_has_section_headings(self):
        gen = ReportGenerator()
        md = gen.render_markdown(run_id="heading_test")

        assert "## Execution Summary" in md


class TestExecutionSummary:
    def test_summary_with_workflow_result(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_sum",
            status="succeeded",
            step_results=[
                StepResult(step_id="s1", status="succeeded", execution_time_ms=10.0),
                StepResult(step_id="s2", status="failed", execution_time_ms=20.0, error_message="err"),
                StepResult(step_id="s3", status="skipped"),
            ],
            total_execution_time_ms=30.0,
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="sum_test")

        summary_section = next(s for s in data.sections if s.heading == "Execution Summary")
        assert "succeeded" in summary_section.content.lower()
        assert "Succeeded: 1" in summary_section.content
        assert "Failed: 1" in summary_section.content
        assert "Skipped: 1" in summary_section.content

    def test_summary_with_workflow_info(self):
        workflow = Workflow(
            name="Summary Info WF",
            steps=[
                WorkflowStep(step_id="s1", name="S1", action="a1"),
                WorkflowStep(step_id="s2", name="S2", action="a2"),
            ],
        )

        gen = ReportGenerator(workflow=workflow)
        data = gen.generate(run_id="sum_info")

        summary_section = next(s for s in data.sections if s.heading == "Execution Summary")
        assert "Summary Info WF" in summary_section.content
        assert "**Total Steps**: 2" in summary_section.content


class TestDecisionTrace:
    def test_decision_trace_with_commitment_events(self):
        event_log = EventLog()

        commitment = CommitmentEvent(
            event_id="evt_1",
            source_state_id="ws_0",
            commitment_kind="observe",
            intent_summary="Read document content",
            action_summary="request observation from reality interface",
        )
        event_log.append(commitment)

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="trace_test")

        trace_sections = [s for s in data.sections if s.heading == "Decision Trace"]
        assert len(trace_sections) == 1
        assert "evt_1" in trace_sections[0].content
        assert "observe" in trace_sections[0].content
        assert "Read document content" in trace_sections[0].content

    def test_decision_trace_with_revision_events(self):
        event_log = EventLog()

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="entity_update",
            target_ref="memory.test_key",
            before_summary="not set",
            after_summary="test_value",
            justification="test",
            raw_value="test_value",
        )
        revision = ModelRevisionEvent(
            revision_id="rev_1",
            prior_state_id="ws_0",
            caused_by_event_id="evt_1",
            revision_kind="expansion",
            deltas=(delta,),
            resulting_state_id="ws_1",
            revision_summary="Store result",
        )
        event_log.append(revision)

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="trace_test")

        trace_sections = [s for s in data.sections if s.heading == "Decision Trace"]
        assert len(trace_sections) == 1
        assert "rev_1" in trace_sections[0].content
        assert "memory.test_key" in trace_sections[0].content
        assert "expansion" in trace_sections[0].content

    def test_decision_trace_with_no_commitment_or_revision_events(self):
        event_log = EventLog()
        event_log.append(
            Event(
                event_type="workflow.started",
                payload={"workflow_id": "wf_1"},
                actor="workflow_runner",
            )
        )

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="no_trace")

        trace_sections = [s for s in data.sections if s.heading == "Decision Trace"]
        assert len(trace_sections) == 0

    def test_decision_trace_empty_event_log(self):
        gen = ReportGenerator(event_log=EventLog())
        data = gen.generate(run_id="empty_trace")

        trace_sections = [s for s in data.sections if s.heading == "Decision Trace"]
        assert len(trace_sections) == 0

    def test_decision_trace_no_event_log(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="no_log")

        trace_sections = [s for s in data.sections if s.heading == "Decision Trace"]
        assert len(trace_sections) == 0


class TestToolCallHistory:
    def test_tool_calls_with_events(self):
        event_log = EventLog()

        call_spec = ToolCallSpec(
            tool_name="test_tool",
            arguments={"key": "value"},
            call_id="call_001",
        )
        policy = ToolPolicyDecision(
            verdict="allow",
            reason="allowed",
            tool_name="test_tool",
        )
        tool_call_event = ToolCallEvent(call=call_spec, decision=policy)
        event_log.append(tool_call_event)

        tool_result = ToolResultEvent(
            call_id="call_001",
            tool_name="test_tool",
            status="succeeded",
            result="output data",
        )
        event_log.append(tool_result)

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="tool_test")

        tool_sections = [s for s in data.sections if s.heading == "Tool Call History"]
        assert len(tool_sections) == 1
        assert "test_tool" in tool_sections[0].content
        assert "call_001" in tool_sections[0].content

    def test_tool_calls_failed_result(self):
        event_log = EventLog()

        tool_result = ToolResultEvent(
            call_id="call_fail",
            tool_name="failing_tool",
            status="failed",
            error_message="Tool execution failed",
        )
        event_log.append(tool_result)

        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="fail_tool")

        tool_sections = [s for s in data.sections if s.heading == "Tool Call History"]
        assert len(tool_sections) == 1
        assert "failing_tool" in tool_sections[0].content
        assert "Tool execution failed" in tool_sections[0].content

    def test_tool_calls_no_events(self):
        event_log = EventLog()
        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="no_tools")

        tool_sections = [s for s in data.sections if s.heading == "Tool Call History"]
        assert len(tool_sections) == 0

    def test_tool_calls_no_event_log(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="no_log_tools")

        tool_sections = [s for s in data.sections if s.heading == "Tool Call History"]
        assert len(tool_sections) == 0


class TestStepResults:
    def test_step_results_section(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_steps",
            status="succeeded",
            step_results=[
                StepResult(
                    step_id="sr_1",
                    status="succeeded",
                    execution_time_ms=100.0,
                    variables={"var1": "val1"},
                ),
                StepResult(
                    step_id="sr_2",
                    status="failed",
                    error_message="Step error",
                    execution_time_ms=50.0,
                ),
            ],
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="steps_test")

        step_sections = [s for s in data.sections if s.heading == "Step Results"]
        assert len(step_sections) == 1
        assert "sr_1" in step_sections[0].content
        assert "sr_2" in step_sections[0].content
        assert "Step error" in step_sections[0].content

    def test_step_results_empty(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_empty",
            status="succeeded",
            step_results=[],
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="empty_steps")

        step_sections = [s for s in data.sections if s.heading == "Step Results"]
        assert len(step_sections) == 0

    def test_step_results_no_workflow_result(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="no_wr")

        step_sections = [s for s in data.sections if s.heading == "Step Results"]
        assert len(step_sections) == 0


class TestFinalResults:
    def test_final_results_with_variables(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_final",
            status="succeeded",
            step_results=[],
            variables={"result_key": "result_value", "another": 42},
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="final_test")

        final_sections = [s for s in data.sections if s.heading == "Final Results"]
        assert len(final_sections) == 1
        assert "result_key" in final_sections[0].content

    def test_final_results_no_variables(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_novar",
            status="succeeded",
            step_results=[],
            variables={},
        )

        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="no_vars")

        final_sections = [s for s in data.sections if s.heading == "Final Results"]
        assert len(final_sections) == 0


class TestMetricsSection:
    def test_metrics_with_summary(self):
        metrics_summary = {
            "total_duration_ms": 500.0,
            "phase_durations": {
                "compilation": 100.0,
                "execution": 400.0,
            },
            "event_counts": {
                "workflow.started": 1,
                "workflow.completed": 1,
            },
            "tool_metrics": {
                "total_executions": 5,
                "avg_execution_time_ms": 50.0,
                "max_execution_time_ms": 100.0,
                "min_execution_time_ms": 10.0,
            },
        }

        gen = ReportGenerator(metrics_summary=metrics_summary)
        data = gen.generate(run_id="metrics_test")

        metric_sections = [s for s in data.sections if s.heading == "Execution Metrics"]
        assert len(metric_sections) == 1
        assert "500.0" in metric_sections[0].content
        assert "compilation" in metric_sections[0].content
        assert "execution" in metric_sections[0].content

    def test_metrics_no_summary(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="no_metrics")

        metric_sections = [s for s in data.sections if s.heading == "Execution Metrics"]
        assert len(metric_sections) == 0


class TestMetadata:
    def test_metadata_basic(self):
        gen = ReportGenerator()
        data = gen.generate(run_id="meta_test")

        assert data.metadata["report_format"] == "markdown"
        assert data.metadata["generated_by"] == "ReportGenerator"

    def test_metadata_with_workflow(self):
        workflow = Workflow(
            name="Meta WF",
            steps=[WorkflowStep(step_id="s1", name="S1", action="a1")],
        )
        gen = ReportGenerator(workflow=workflow)
        data = gen.generate(run_id="meta_wf")

        assert data.metadata["workflow_name"] == "Meta WF"

    def test_metadata_with_workflow_result(self):
        workflow_result = WorkflowResult(
            workflow_id="wf_meta",
            status="failed",
            step_results=[],
            total_execution_time_ms=123.45,
        )
        gen = ReportGenerator(workflow_result=workflow_result)
        data = gen.generate(run_id="meta_wr")

        assert data.metadata["status"] == "failed"
        assert data.metadata["total_execution_time_ms"] == 123.45

    def test_metadata_with_event_log(self):
        event_log = EventLog()
        event_log.append(
            Event(
                event_type="test.event",
                payload={},
                actor="system",
            )
        )
        gen = ReportGenerator(event_log=event_log)
        data = gen.generate(run_id="meta_el")

        assert data.metadata["event_count"] == 1


class TestIntegration:
    def test_full_report_from_mock_workflow(self):
        event_log = EventLog()

        event_log.append(
            Event(
                event_type="workflow.started",
                payload={"workflow_id": "wf_int", "workflow_name": "Integration"},
                actor="workflow_runner",
            )
        )

        commitment = CommitmentEvent(
            event_id="evt_int",
            source_state_id="ws_0",
            commitment_kind="tool_contact",
            intent_summary="Analyze data",
            action_summary="call analyze tool",
        )
        event_log.append(commitment)

        delta = RevisionDelta(
            delta_id="d1",
            target_kind="entity_update",
            target_ref="memory.result",
            before_summary="not set",
            after_summary="done",
            justification="Store result",
            raw_value="done",
        )
        revision = ModelRevisionEvent(
            revision_id="rev_int",
            prior_state_id="ws_0",
            caused_by_event_id="evt_int",
            revision_kind="expansion",
            deltas=(delta,),
            resulting_state_id="ws_1",
            revision_summary="Store result",
        )
        event_log.append(revision)

        call_spec = ToolCallSpec(tool_name="analyze", arguments={"input": "data"}, call_id="call_int")
        tool_policy = ToolPolicyDecision(verdict="allow", reason="read tool", tool_name="analyze")
        event_log.append(ToolCallEvent(call=call_spec, decision=tool_policy))

        event_log.append(ToolResultEvent(
            call_id="call_int",
            tool_name="analyze",
            status="succeeded",
            result={"findings": ["ok"]},
        ))

        event_log.append(
            Event(
                event_type="workflow.completed",
                payload={"workflow_id": "wf_int", "status": "succeeded"},
                actor="workflow_runner",
            )
        )

        workflow = Workflow(
            name="Integration Workflow",
            steps=[
                WorkflowStep(step_id="int_s1", name="Analyze", action="analyze", inputs={"input": "data"}),
            ],
        )

        workflow_result = WorkflowResult(
            workflow_id="wf_int",
            status="succeeded",
            step_results=[
                StepResult(
                    step_id="int_s1",
                    status="succeeded",
                    output={"findings": ["ok"]},
                    variables={"int_s1_summary": "Analysis complete"},
                    execution_time_ms=150.0,
                ),
            ],
            variables={"int_s1_summary": "Analysis complete"},
            total_execution_time_ms=150.0,
        )

        metrics_summary = {
            "total_duration_ms": 200.0,
            "phase_durations": {"compilation": 50.0, "execution": 150.0},
            "event_counts": {"workflow.started": 1, "workflow.completed": 1},
            "tool_metrics": {
                "total_executions": 1,
                "avg_execution_time_ms": 50.0,
                "max_execution_time_ms": 50.0,
                "min_execution_time_ms": 50.0,
            },
        }

        gen = ReportGenerator(
            event_log=event_log,
            workflow=workflow,
            workflow_result=workflow_result,
            metrics_summary=metrics_summary,
        )

        data = gen.generate(run_id="int_run")
        md = gen.render_markdown(run_id="int_run")

        assert data.run_id == "int_run"
        assert len(data.sections) > 0

        assert "# Execution Report: int_run" in md
        assert "Integration Workflow" in md
        assert "Execution Summary" in md
        assert "Decision Trace" in md
        assert "Tool Call History" in md
        assert "Step Results" in md
        assert "Final Results" in md
        assert "Execution Metrics" in md

    def test_report_with_failed_workflow(self):
        workflow = Workflow(
            name="Failing Workflow",
            steps=[
                WorkflowStep(step_id="f1", name="Fail Step", action="fail_act"),
            ],
        )

        workflow_result = WorkflowResult(
            workflow_id="wf_fail",
            status="failed",
            step_results=[
                StepResult(
                    step_id="f1",
                    status="failed",
                    error_message="Something went wrong",
                    execution_time_ms=10.0,
                ),
            ],
            total_execution_time_ms=10.0,
            error_message="Something went wrong",
        )

        gen = ReportGenerator(
            workflow=workflow,
            workflow_result=workflow_result,
        )

        md = gen.render_markdown(run_id="fail_run")

        assert "failed" in md.lower()
        assert "Something went wrong" in md

    def test_report_markdown_contains_all_sections_for_full_run(self):
        event_log = EventLog()
        event_log.append(
            Event(
                event_type="workflow.started",
                payload={"workflow_id": "wf_full"},
                actor="workflow_runner",
            )
        )

        workflow = Workflow(
            name="Full Run",
            steps=[WorkflowStep(step_id="s1", name="S1", action="a1")],
        )

        workflow_result = WorkflowResult(
            workflow_id="wf_full",
            status="succeeded",
            step_results=[StepResult(step_id="s1", status="succeeded", execution_time_ms=10.0)],
            total_execution_time_ms=10.0,
        )

        gen = ReportGenerator(
            event_log=event_log,
            workflow=workflow,
            workflow_result=workflow_result,
        )

        md = gen.render_markdown(run_id="full_run")

        assert "## Execution Summary" in md
