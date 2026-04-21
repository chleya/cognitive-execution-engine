"""Execution metrics and observability framework.

Provides real-time execution metrics, progress tracking, and debug capabilities
for the CEE runtime while preserving audit semantics.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol
from enum import Enum

from .event_log import EventLog
from .events import Event, DeliberationEvent
from .commitment import CommitmentEvent
from .revision import ModelRevisionEvent
from .tools import ToolCallEvent, ToolResultEvent


class ExecutionPhase(Enum):
    """Phases of execution."""
    INITIALIZATION = "initialization"
    COMPILATION = "compilation"
    DELIBERATION = "deliberation"
    PLANNING = "planning"
    EXECUTION = "execution"
    APPROVAL = "approval"
    COMPLETION = "completion"
    ERROR = "error"


@dataclass(frozen=True)
class PhaseTiming:
    """Timing information for an execution phase."""
    phase: ExecutionPhase
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        return self.end_time is not None


@dataclass(frozen=True)
class ExecutionMetric:
    """A single execution metric."""
    name: str
    value: float
    unit: str
    timestamp: float
    phase: Optional[ExecutionPhase] = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExecutionMetricsCollector:
    """Collects and aggregates execution metrics."""

    _metrics: List[ExecutionMetric] = field(default_factory=list)
    _phase_timings: Dict[ExecutionPhase, PhaseTiming] = field(default_factory=dict)
    _current_phase: Optional[ExecutionPhase] = None
    _start_time: float = field(default_factory=time.monotonic)
    _event_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _tool_execution_times: List[float] = field(default_factory=list)
    _errors: List[str] = field(default_factory=list)

    def start_phase(self, phase: ExecutionPhase) -> None:
        """Start timing a new execution phase."""
        self._current_phase = phase
        self._phase_timings[phase] = PhaseTiming(
            phase=phase,
            start_time=time.monotonic(),
        )

    def end_phase(self, phase: Optional[ExecutionPhase] = None) -> None:
        """End timing for current or specified phase."""
        target_phase = phase or self._current_phase
        if target_phase is None:
            return
        
        if target_phase in self._phase_timings:
            timing = self._phase_timings[target_phase]
            end_time = time.monotonic()
            duration_ms = (end_time - timing.start_time) * 1000.0
            self._phase_timings[target_phase] = PhaseTiming(
                phase=timing.phase,
                start_time=timing.start_time,
                end_time=end_time,
                duration_ms=duration_ms,
            )

    def record_metric(self, name: str, value: float, unit: str, phase: Optional[ExecutionPhase] = None, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a custom metric."""
        metric = ExecutionMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=time.monotonic(),
            phase=phase or self._current_phase,
            tags=tags or {},
        )
        self._metrics.append(metric)

    def record_event(self, event: Event | DeliberationEvent | CommitmentEvent | ModelRevisionEvent | ToolCallEvent | ToolResultEvent) -> None:
        """Record an event and update counters."""
        self._event_counts[event.event_type] += 1
        
        if isinstance(event, ToolResultEvent):
            if event.status == "succeeded":
                self._event_counts["tool.succeeded"] += 1
            elif event.status == "failed":
                self._event_counts["tool.failed"] += 1

    def record_error(self, error_message: str) -> None:
        """Record an error."""
        self._errors.append(error_message)

    def record_tool_execution_time(self, duration_ms: float) -> None:
        """Record tool execution time."""
        self._tool_execution_times.append(duration_ms)

    @property
    def total_events(self) -> int:
        return sum(self._event_counts.values())

    @property
    def total_errors(self) -> int:
        return len(self._errors)

    @property
    def avg_tool_execution_time_ms(self) -> float:
        if not self._tool_execution_times:
            return 0.0
        return sum(self._tool_execution_times) / len(self._tool_execution_times)

    def get_phase_duration_ms(self, phase: ExecutionPhase) -> Optional[float]:
        """Get duration for a specific phase."""
        if phase not in self._phase_timings:
            return None
        return self._phase_timings[phase].duration_ms

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected metrics."""
        phase_durations = {
            phase.value: timing.duration_ms
            for phase, timing in self._phase_timings.items()
            if timing.duration_ms is not None
        }
        
        total_duration_ms = (time.monotonic() - self._start_time) * 1000.0
        
        return {
            "total_duration_ms": total_duration_ms,
            "phase_durations": phase_durations,
            "event_counts": dict(self._event_counts),
            "total_events": self.total_events,
            "total_errors": self.total_errors,
            "errors": self._errors[-10:],  # Last 10 errors
            "tool_metrics": {
                "total_executions": len(self._tool_execution_times),
                "avg_execution_time_ms": self.avg_tool_execution_time_ms,
                "max_execution_time_ms": max(self._tool_execution_times) if self._tool_execution_times else 0,
                "min_execution_time_ms": min(self._tool_execution_times) if self._tool_execution_times else 0,
            },
            "custom_metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "phase": m.phase.value if m.phase else None,
                    "tags": m.tags,
                }
                for m in self._metrics[-20:]  # Last 20 custom metrics
            ],
        }


class MetricsExporter(Protocol):
    """Protocol for exporting metrics."""
    def export(self, metrics: ExecutionMetricsCollector) -> None:
        """Export metrics to external system."""


@dataclass(frozen=True)
class ConsoleMetricsExporter:
    """Export metrics to console output."""
    
    def export(self, metrics: ExecutionMetricsCollector) -> None:
        summary = metrics.get_summary()
        print("\n=== Execution Metrics Summary ===")
        print(f"Total Duration: {summary['total_duration_ms']:.2f}ms")
        print(f"Total Events: {summary['total_events']}")
        print(f"Total Errors: {summary['total_errors']}")
        
        if summary['phase_durations']:
            print("\nPhase Durations:")
            for phase, duration in summary['phase_durations'].items():
                print(f"  {phase}: {duration:.2f}ms")
        
        if summary['tool_metrics']['total_executions'] > 0:
            print("\nTool Metrics:")
            print(f"  Total Executions: {summary['tool_metrics']['total_executions']}")
            print(f"  Avg Time: {summary['tool_metrics']['avg_execution_time_ms']:.2f}ms")
        
        if summary['errors']:
            print("\nRecent Errors:")
            for error in summary['errors']:
                print(f"  - {error}")
        print("=" * 35)


@dataclass(frozen=True)
class DebugContext:
    """Context for debug mode execution."""
    
    enable_step_through: bool = False
    breakpoints: List[str] = field(default_factory=list)
    verbose_logging: bool = True
    pause_on_error: bool = False
    
    def should_break_at(self, event_type: str) -> bool:
        """Check if execution should break at this event type."""
        return event_type in self.breakpoints


class ExecutionObserver:
    """Combines metrics collection with debug capabilities."""
    
    def __init__(
        self,
        metrics_collector: Optional[ExecutionMetricsCollector] = None,
        debug_context: Optional[DebugContext] = None,
        exporters: Optional[List[MetricsExporter]] = None,
    ):
        self.metrics = metrics_collector or ExecutionMetricsCollector()
        self.debug = debug_context or DebugContext()
        self._exporters = exporters or [ConsoleMetricsExporter()]
        self._event_log: Optional[EventLog] = None
    
    def bind_event_log(self, event_log: EventLog) -> "ExecutionObserver":
        """Bind to an event log for automatic metric recording."""
        self._event_log = event_log
        return self
    
    def observe_event(self, event: Event | DeliberationEvent | CommitmentEvent | ModelRevisionEvent | ToolCallEvent | ToolResultEvent) -> None:
        """Observe an event and record metrics."""
        self.metrics.record_event(event)
        
        if self.debug.verbose_logging:
            self.metrics.record_metric(
                name="event.observed",
                value=1,
                unit="count",
                tags={"event_type": event.event_type},
            )
        
        if self.debug.should_break_at(event.event_type):
            print(f"[DEBUG BREAKPOINT] Event: {event.event_type}")
    
    def export_metrics(self) -> None:
        """Export metrics to all configured exporters."""
        for exporter in self._exporters:
            exporter.export(self.metrics)
    
    def get_execution_report(self) -> Dict[str, Any]:
        """Get a comprehensive execution report."""
        return {
            "metrics": self.metrics.get_summary(),
            "debug_mode": {
                "step_through_enabled": self.debug.enable_step_through,
                "breakpoints": self.debug.breakpoints,
                "verbose_logging": self.debug.verbose_logging,
            },
        }
