"""Run artifact contract for sharing and replaying deterministic runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .narration import render_event_narration
from .planner import PlanSpec
from .runtime import RunResult
from .schemas import require_schema_version
from .tasks import TaskSpec


RUN_ARTIFACT_SCHEMA_VERSION = "cee.run_artifact.v1"


@dataclass(frozen=True)
class RunArtifact:
    """Portable artifact for a deterministic runtime run."""

    task: TaskSpec
    plan: PlanSpec
    event_payloads: tuple[dict[str, object], ...]
    narration_lines: tuple[str, ...]
    allowed_count: int
    blocked_count: int
    approval_required_count: int
    denied_count: int
    workflow_data: dict[str, Any] | None = None
    workflow_result_data: dict[str, Any] | None = None
    world_state_snapshot: dict[str, Any] | None = None

    @classmethod
    def from_run_result(cls, result: RunResult) -> "RunArtifact":
        from .workflow import Workflow, WorkflowStep, WorkflowResult, StepResult

        steps = []
        step_results = []
        for i, (ce, decision) in enumerate(zip(result.commitment_events, result.plan_result.policy_decisions)):
            step_id = f"step_{i}"
            action = "allow"
            if decision.requires_approval:
                action = "requires_approval"
            elif not decision.allowed:
                action = "deny"
            steps.append(WorkflowStep(
                step_id=step_id,
                name=ce.commitment_kind,
                action=action,
            ))
            status = "succeeded" if decision.allowed and not decision.requires_approval else "blocked"
            if decision.requires_approval:
                status = "requires_approval"
            step_results.append(StepResult(
                step_id=step_id,
                status=status,
                output=ce.to_dict(),
            ))

        for i, tc_event in enumerate(result.plan_result.tool_call_events):
            step_id = f"tool_call_{i}"
            steps.append(WorkflowStep(
                step_id=step_id,
                name="tool_call",
                action=tc_event.call.tool_name,
            ))
            step_results.append(StepResult(
                step_id=step_id,
                status="succeeded",
                output=tc_event.to_dict() if hasattr(tc_event, 'to_dict') else str(tc_event),
            ))

        workflow = Workflow(
            name=f"task_{result.task.kind}",
            steps=steps,
            workflow_id=f"wf_{result.task.task_id}",
        ) if steps else None

        workflow_result = WorkflowResult(
            workflow_id=f"wf_{result.task.task_id}",
            status="succeeded" if result.plan_result.blocked_count == 0 else "partial",
            step_results=step_results,
            variables=result.world_state.to_dict() if result.world_state is not None else {},
            total_execution_time_ms=0.0,
        ) if step_results else None

        return cls(
            task=result.task,
            plan=result.plan,
            event_payloads=tuple(event.to_dict() for event in result.event_log.all()),
            narration_lines=render_event_narration(result.event_log.all()),
            allowed_count=result.allowed_count,
            blocked_count=result.blocked_count,
            approval_required_count=result.requires_approval_count,
            denied_count=len(result.denied_transitions),
            workflow_data=workflow.to_dict() if workflow is not None else None,
            workflow_result_data=workflow_result.to_dict() if workflow_result is not None else None,
            world_state_snapshot=result.world_state.to_dict() if result.world_state is not None else None,
        )

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "schema_version": RUN_ARTIFACT_SCHEMA_VERSION,
            "task": self.task.to_dict(),
            "plan": self.plan.to_dict(),
            "event_payloads": list(self.event_payloads),
            "narration_lines": list(self.narration_lines),
            "counts": {
                "allowed": self.allowed_count,
                "blocked": self.blocked_count,
                "approval_required": self.approval_required_count,
                "denied": self.denied_count,
            },
        }
        if self.workflow_data is not None:
            d["workflow_data"] = self.workflow_data
        if self.workflow_result_data is not None:
            d["workflow_result_data"] = self.workflow_result_data
        if self.world_state_snapshot is not None:
            d["world_state_snapshot"] = self.world_state_snapshot
        return d

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RunArtifact":
        require_schema_version(payload, RUN_ARTIFACT_SCHEMA_VERSION)
        counts = payload["counts"]
        if not isinstance(counts, dict):
            raise ValueError("RunArtifact counts must be an object")

        event_payloads = payload["event_payloads"]
        if not isinstance(event_payloads, list):
            raise ValueError("RunArtifact event_payloads must be a list")

        narration_lines = payload.get("narration_lines", [])
        if not isinstance(narration_lines, list) or not all(
            isinstance(line, str) for line in narration_lines
        ):
            raise ValueError("RunArtifact narration_lines must be a list of strings")

        return cls(
            task=TaskSpec.from_dict(payload["task"]),  # type: ignore[arg-type]
            plan=PlanSpec.from_dict(payload["plan"]),  # type: ignore[arg-type]
            event_payloads=tuple(event_payloads),  # type: ignore[arg-type]
            narration_lines=tuple(narration_lines),
            allowed_count=int(counts["allowed"]),
            blocked_count=int(counts["blocked"]),
            approval_required_count=int(counts["approval_required"]),
            denied_count=int(counts["denied"]),
            workflow_data=payload.get("workflow_data") if isinstance(payload.get("workflow_data"), dict) else None,
            workflow_result_data=payload.get("workflow_result_data") if isinstance(payload.get("workflow_result_data"), dict) else None,
            world_state_snapshot=payload.get("world_state_snapshot") if isinstance(payload.get("world_state_snapshot"), dict) else None,
        )

    def dumps(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def loads(cls, artifact: str) -> "RunArtifact":
        payload = json.loads(artifact)
        if not isinstance(payload, dict):
            raise ValueError("RunArtifact must be a JSON object")
        return cls.from_dict(payload)

def run_result_to_artifact(result: RunResult) -> RunArtifact:
    return RunArtifact.from_run_result(result)
