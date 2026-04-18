"""Report generator for execution runs.

Produces human-readable Markdown reports from workflow execution data,
event logs, and observability metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .event_log import EventLog
from .events import DeliberationEvent, Event, StateTransitionEvent
from .tools import ToolCallEvent, ToolResultEvent
from .workflow import Workflow, WorkflowResult, StepResult


@dataclass(frozen=True)
class ReportSection:
    heading: str
    content: str
    level: int = 2


@dataclass(frozen=True)
class ReportData:
    run_id: str
    title: str
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "title": self.title,
            "sections": [
                {"heading": s.heading, "content": s.content, "level": s.level}
                for s in self.sections
            ],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ReportGenerator:
    event_log: Optional[EventLog] = None
    workflow: Optional[Workflow] = None
    workflow_result: Optional[WorkflowResult] = None
    metrics_summary: Optional[Dict[str, Any]] = None

    def generate(self, run_id: Optional[str] = None) -> ReportData:
        rid = run_id or "unknown"
        sections = self._build_summary_section(rid)
        sections += self._build_decision_trace_section()
        sections += self._build_tool_calls_section()
        sections += self._build_step_results_section()
        sections += self._build_final_results_section()
        sections += self._build_metrics_section()

        title = f"Execution Report: {rid}"

        return ReportData(
            run_id=rid,
            title=title,
            sections=sections,
            metadata=self._build_metadata(),
        )

    def render_markdown(self, run_id: Optional[str] = None) -> str:
        data = self.generate(run_id)
        parts = [f"# {data.title}\n"]

        for sec in data.sections:
            prefix = "#" * sec.level
            parts.append(f"{prefix} {sec.heading}\n")
            parts.append(f"{sec.content}\n")

        return "\n".join(parts)

    def _build_summary_section(self, run_id: str) -> List[ReportSection]:
        lines = [f"**Run ID**: {run_id}\n"]

        if self.workflow is not None:
            lines.append(f"**Workflow**: {self.workflow.name}")
            lines.append(f"**Workflow ID**: {self.workflow.workflow_id}")
            lines.append(f"**Total Steps**: {len(self.workflow.steps)}\n")

        if self.workflow_result is not None:
            status = self.workflow_result.status
            total_ms = self.workflow_result.total_execution_time_ms
            lines.append(f"**Status**: {status}")
            lines.append(f"**Total Execution Time**: {total_ms:.2f} ms")
            lines.append(f"**Steps Completed**: {len(self.workflow_result.step_results)}\n")

            succeeded = sum(1 for r in self.workflow_result.step_results if r.status == "succeeded")
            failed = sum(1 for r in self.workflow_result.step_results if r.status == "failed")
            skipped = sum(1 for r in self.workflow_result.step_results if r.status == "skipped")
            lines.append(f"- Succeeded: {succeeded}")
            lines.append(f"- Failed: {failed}")
            lines.append(f"- Skipped: {skipped}\n")

        if self.event_log is not None:
            total_events = len(list(self.event_log.all()))
            lines.append(f"**Total Events**: {total_events}\n")

        return [ReportSection(heading="Execution Summary", content="\n".join(lines))]

    def _build_decision_trace_section(self) -> List[ReportSection]:
        if self.event_log is None:
            return []

        transition_events = self.event_log.transition_events()
        if not transition_events:
            return []

        lines = []
        for event in transition_events:
            lines.append(f"- **Trace**: {event.trace_id}")
            lines.append(f"  - **Actor**: {event.actor}")
            lines.append(f"  - **Section**: {event.patch.section}")
            lines.append(f"  - **Key**: {event.patch.key}")
            lines.append(f"  - **Op**: {event.patch.op}")
            lines.append(f"  - **Policy**: {event.policy_decision.verdict}")
            if event.reason:
                lines.append(f"  - **Reason**: {event.reason}")
            lines.append("")

        return [ReportSection(heading="Decision Trace", content="\n".join(lines))]

    def _build_tool_calls_section(self) -> List[ReportSection]:
        if self.event_log is None:
            return []

        events = self.event_log.all()
        tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_results = [e for e in events if isinstance(e, ToolResultEvent)]

        if not tool_calls and not tool_results:
            return []

        lines = []
        for call in tool_calls:
            lines.append(f"- **Tool**: {call.call.tool_name}")
            lines.append(f"  - **Call ID**: {call.call.call_id}")
            if call.call.arguments:
                lines.append(f"  - **Arguments**: `{json.dumps(call.call.arguments, default=str)}`")
            lines.append("")

        if tool_results:
            lines.append("### Tool Results\n")
            for result in tool_results:
                status_icon = "OK" if result.status == "succeeded" else "FAIL"
                lines.append(f"- [{status_icon}] **{result.tool_name}** ({result.call_id})")
                if result.error_message:
                    lines.append(f"  - **Error**: {result.error_message}")
                lines.append("")

        return [ReportSection(heading="Tool Call History", content="\n".join(lines))]

    def _build_step_results_section(self) -> List[ReportSection]:
        if self.workflow_result is None:
            return []

        step_results = self.workflow_result.step_results
        if not step_results:
            return []

        lines = []
        for sr in step_results:
            lines.append(f"- **Step**: {sr.step_id}")
            lines.append(f"  - **Status**: {sr.status}")
            lines.append(f"  - **Execution Time**: {sr.execution_time_ms:.2f} ms")
            if sr.error_message:
                lines.append(f"  - **Error**: {sr.error_message}")
            if sr.variables:
                lines.append(f"  - **Variables**: `{json.dumps(sr.variables, default=str)}`")
            lines.append("")

        return [ReportSection(heading="Step Results", content="\n".join(lines))]

    def _build_final_results_section(self) -> List[ReportSection]:
        if self.workflow_result is None:
            return []

        final_vars = self.workflow_result.variables
        if not final_vars:
            return []

        lines = []
        for key, value in final_vars.items():
            lines.append(f"- **{key}**: `{json.dumps(value, default=str)}`")

        return [ReportSection(heading="Final Results", content="\n".join(lines))]

    def _build_metrics_section(self) -> List[ReportSection]:
        if self.metrics_summary is None:
            return []

        lines = []
        total_duration = self.metrics_summary.get("total_duration_ms", 0)
        lines.append(f"**Total Duration**: {total_duration:.2f} ms\n")

        phase_durations = self.metrics_summary.get("phase_durations", {})
        if phase_durations:
            lines.append("**Phase Durations**:\n")
            for phase_name, duration in phase_durations.items():
                lines.append(f"- {phase_name}: {duration:.2f} ms")
            lines.append("")

        tool_metrics = self.metrics_summary.get("tool_metrics", {})
        if tool_metrics.get("total_executions", 0) > 0:
            lines.append("**Tool Metrics**:\n")
            lines.append(f"- Total Executions: {tool_metrics['total_executions']}")
            lines.append(f"- Avg Time: {tool_metrics['avg_execution_time_ms']:.2f} ms")
            lines.append(f"- Max Time: {tool_metrics['max_execution_time_ms']:.2f} ms")
            lines.append(f"- Min Time: {tool_metrics['min_execution_time_ms']:.2f} ms\n")

        event_counts = self.metrics_summary.get("event_counts", {})
        if event_counts:
            lines.append("**Event Counts**:\n")
            for event_type, count in event_counts.items():
                lines.append(f"- {event_type}: {count}")

        return [ReportSection(heading="Execution Metrics", content="\n".join(lines))]

    def _build_metadata(self) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "report_format": "markdown",
            "generated_by": "ReportGenerator",
        }
        if self.workflow is not None:
            meta["workflow_id"] = self.workflow.workflow_id
            meta["workflow_name"] = self.workflow.name
        if self.workflow_result is not None:
            meta["status"] = self.workflow_result.status
            meta["total_execution_time_ms"] = self.workflow_result.total_execution_time_ms
        if self.event_log is not None:
            meta["event_count"] = len(list(self.event_log.all()))
        return meta
