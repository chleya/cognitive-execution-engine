"""Run artifact contract for sharing and replaying deterministic runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .event_log import replay_serialized_transition_events
from .narration import render_event_narration
from .planner import PlanSpec
from .runtime import RunResult
from .schemas import require_schema_version
from .state import State
from .tasks import TaskSpec


RUN_ARTIFACT_SCHEMA_VERSION = "cee.run_artifact.v1"


@dataclass(frozen=True)
class RunArtifact:
    """Portable artifact for a deterministic runtime run."""

    task: TaskSpec
    plan: PlanSpec
    event_payloads: tuple[dict[str, object], ...]
    narration_lines: tuple[str, ...]
    replayed_state_snapshot: dict[str, Any]
    allowed_count: int
    blocked_count: int
    approval_required_count: int
    denied_count: int

    @classmethod
    def from_run_result(cls, result: RunResult) -> "RunArtifact":
        return cls(
            task=result.task,
            plan=result.plan,
            event_payloads=tuple(event.to_dict() for event in result.event_log.all()),
            narration_lines=render_event_narration(result.event_log.all()),
            replayed_state_snapshot=result.replayed_state.snapshot(),
            allowed_count=len(result.allowed_transitions),
            blocked_count=len(result.blocked_transitions),
            approval_required_count=len(result.approval_required_transitions),
            denied_count=len(result.denied_transitions),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": RUN_ARTIFACT_SCHEMA_VERSION,
            "task": self.task.to_dict(),
            "plan": self.plan.to_dict(),
            "event_payloads": list(self.event_payloads),
            "narration_lines": list(self.narration_lines),
            "replayed_state_snapshot": self.replayed_state_snapshot,
            "counts": {
                "allowed": self.allowed_count,
                "blocked": self.blocked_count,
                "approval_required": self.approval_required_count,
                "denied": self.denied_count,
            },
        }

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

        replayed_state_snapshot = payload["replayed_state_snapshot"]
        if not isinstance(replayed_state_snapshot, dict):
            raise ValueError("RunArtifact replayed_state_snapshot must be an object")

        return cls(
            task=TaskSpec.from_dict(payload["task"]),  # type: ignore[arg-type]
            plan=PlanSpec.from_dict(payload["plan"]),  # type: ignore[arg-type]
            event_payloads=tuple(event_payloads),  # type: ignore[arg-type]
            narration_lines=tuple(narration_lines),
            replayed_state_snapshot=replayed_state_snapshot,
            allowed_count=int(counts["allowed"]),
            blocked_count=int(counts["blocked"]),
            approval_required_count=int(counts["approval_required"]),
            denied_count=int(counts["denied"]),
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

    def replay_state(self) -> State:
        return replay_serialized_transition_events(self.event_payloads)


def run_result_to_artifact(result: RunResult) -> RunArtifact:
    return RunArtifact.from_run_result(result)


def replay_run_artifact_json(artifact: str) -> State:
    return RunArtifact.loads(artifact).replay_state()
