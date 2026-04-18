"""Tests for execution metrics and observability framework."""

import pytest

from cee_core.observability import (
    ExecutionMetricsCollector,
    ExecutionObserver,
    ExecutionPhase,
    ConsoleMetricsExporter,
    DebugContext,
    PhaseTiming,
)
from cee_core.event_log import EventLog
from cee_core.events import Event, StateTransitionEvent
from cee_core.policy import PolicyDecision
from cee_core.tools import ToolCallEvent, ToolCallSpec, ToolResultEvent


class TestPhaseTiming:
    def test_incomplete_phase(self):
        timing = PhaseTiming(
            phase=ExecutionPhase.PLANNING,
            start_time=0.0,
        )

        assert timing.is_complete is False
        assert timing.duration_ms is None

    def test_complete_phase(self):
        timing = PhaseTiming(
            phase=ExecutionPhase.EXECUTION,
            start_time=0.0,
            end_time=1.0,
            duration_ms=1000.0,
        )

        assert timing.is_complete is True
        assert timing.duration_ms == 1000.0


class TestExecutionMetricsCollector:
    def test_phase_timing(self):
        collector = ExecutionMetricsCollector()

        collector.start_phase(ExecutionPhase.COMPILATION)
        collector.end_phase(ExecutionPhase.COMPILATION)

        duration = collector.get_phase_duration_ms(ExecutionPhase.COMPILATION)
        assert duration is not None
        assert duration >= 0

    def test_event_recording(self):
        collector = ExecutionMetricsCollector()

        event = Event(
            event_type="task.received",
            payload={"task_id": "task_1"},
            actor="compiler",
        )
        collector.record_event(event)

        assert collector.total_events == 1

    def test_tool_result_recording(self):
        collector = ExecutionMetricsCollector()

        success_event = ToolResultEvent(
            call_id="call_1",
            tool_name="test_tool",
            status="succeeded",
            result="data",
        )
        collector.record_event(success_event)

        failed_event = ToolResultEvent(
            call_id="call_2",
            tool_name="test_tool",
            status="failed",
            error_message="error",
        )
        collector.record_event(failed_event)

        assert collector._event_counts["tool.succeeded"] == 1
        assert collector._event_counts["tool.failed"] == 1

    def test_error_recording(self):
        collector = ExecutionMetricsCollector()

        collector.record_error("test error 1")
        collector.record_error("test error 2")

        assert collector.total_errors == 2

    def test_tool_execution_time(self):
        collector = ExecutionMetricsCollector()

        collector.record_tool_execution_time(100.0)
        collector.record_tool_execution_time(200.0)

        assert collector.avg_tool_execution_time_ms == 150.0

    def test_custom_metric_recording(self):
        collector = ExecutionMetricsCollector()

        collector.record_metric(
            name="custom.test",
            value=42.0,
            unit="count",
            phase=ExecutionPhase.PLANNING,
            tags={"key": "value"},
        )

        assert len(collector._metrics) == 1
        assert collector._metrics[0].name == "custom.test"
        assert collector._metrics[0].value == 42.0

    def test_get_summary(self):
        collector = ExecutionMetricsCollector()

        collector.start_phase(ExecutionPhase.COMPILATION)
        collector.end_phase(ExecutionPhase.COMPILATION)

        collector.record_error("test error")

        summary = collector.get_summary()

        assert "total_duration_ms" in summary
        assert "phase_durations" in summary
        assert "total_errors" in summary
        assert summary["total_errors"] == 1

    def test_empty_tool_metrics(self):
        collector = ExecutionMetricsCollector()

        summary = collector.get_summary()

        assert summary["tool_metrics"]["total_executions"] == 0
        assert summary["tool_metrics"]["avg_execution_time_ms"] == 0.0

    def test_multiple_phase_timings(self):
        collector = ExecutionMetricsCollector()

        phases = [
            ExecutionPhase.COMPILATION,
            ExecutionPhase.DELIBERATION,
            ExecutionPhase.PLANNING,
            ExecutionPhase.EXECUTION,
        ]

        for phase in phases:
            collector.start_phase(phase)
            collector.end_phase(phase)

        summary = collector.get_summary()

        for phase in phases:
            assert phase.value in summary["phase_durations"]
            assert summary["phase_durations"][phase.value] is not None


class TestDebugContext:
    def test_no_breakpoints(self):
        ctx = DebugContext()

        assert ctx.should_break_at("any.event") is False

    def test_matching_breakpoint(self):
        ctx = DebugContext(breakpoints=["task.received", "plan.created"])

        assert ctx.should_break_at("task.received") is True
        assert ctx.should_break_at("unknown.event") is False

    def test_verbose_logging_default(self):
        ctx = DebugContext()

        assert ctx.verbose_logging is True


class TestConsoleMetricsExporter:
    def test_export_does_not_raise(self, capsys):
        collector = ExecutionMetricsCollector()
        collector.start_phase(ExecutionPhase.COMPILATION)
        collector.end_phase(ExecutionPhase.COMPILATION)
        collector.record_error("test error")
        collector.record_tool_execution_time(100.0)

        exporter = ConsoleMetricsExporter()
        exporter.export(collector)

        captured = capsys.readouterr()
        assert "Execution Metrics Summary" in captured.out
        assert "Total Errors: 1" in captured.out


class TestExecutionObserver:
    def test_observe_event(self):
        observer = ExecutionObserver()

        event = Event(
            event_type="test.event",
            payload={"key": "value"},
            actor="test",
        )
        observer.observe_event(event)

        assert observer.metrics.total_events == 1

    def test_bind_event_log(self):
        log = EventLog()
        observer = ExecutionObserver()
        observer.bind_event_log(log)

        assert observer._event_log is log

    def test_get_execution_report(self):
        observer = ExecutionObserver()

        report = observer.get_execution_report()

        assert "metrics" in report
        assert "debug_mode" in report
        assert "step_through_enabled" in report["debug_mode"]
        assert "breakpoints" in report["debug_mode"]

    def test_export_metrics(self, capsys):
        observer = ExecutionObserver()
        observer.metrics.record_error("test error")
        observer.export_metrics()

        captured = capsys.readouterr()
        assert "Execution Metrics Summary" in captured.out

    def test_verbose_logging_records_metrics(self):
        observer = ExecutionObserver(
            debug_context=DebugContext(verbose_logging=True),
        )

        event = Event(
            event_type="test.event",
            payload={},
            actor="test",
        )
        observer.observe_event(event)

        observed_metrics = [m for m in observer.metrics._metrics if m.name == "event.observed"]
        assert len(observed_metrics) == 1
