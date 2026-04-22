"""FastAPI Web service for the Cognitive Execution Engine.

Provides REST API and WebSocket endpoints for:
1. Task execution
2. State management
3. Event streaming
4. Report generation
"""

from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .runtime import execute_task_in_domain
from .domain_context import DomainContext
from .event_log import EventLog
from .commitment import CommitmentEvent
from .revision import ModelRevisionEvent
from .approval import ApprovalGate, StaticApprovalProvider
from .persistence import StateStore, load_world_state_from_file, save_world_state
from .observability import ExecutionObserver, ExecutionPhase, DebugContext
from .import_export import ImportExportManager
from .handoff_report import build_handoff_report
from .handoff_validator import validate_handoff_state_file
from .calibration import run_calibration_cycle
from .run_artifact import run_result_to_artifact
from .report_generator import ReportGenerator
from .config import CEEConfig, load_config
from .world_state import WorldState

import logging

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    """Task execution request."""
    task: str = Field(..., description="Task description to execute")
    domain: str = Field(default="core", description="Domain context name")
    auto_approve: bool = Field(default=False, description="Auto-approve transitions (must be explicitly enabled)")


class TaskResponse(BaseModel):
    """Task execution response."""
    task_id: str
    status: str
    result: Dict[str, Any]
    metrics: Dict[str, Any]


class CalibrationRequest(BaseModel):
    """Calibration request."""
    auto_approve: bool = Field(default=False)


class CommitmentRequest(BaseModel):
    """Commitment execution request."""
    commitment_kind: str = Field(default="observe", description="Kind: observe, act, tool_contact, internal_commit")
    intent_summary: str = Field(default="", description="Summary of the commitment intent")
    target_entity_ids: List[str] = Field(default_factory=list, description="Target entity IDs")
    observation_summaries: List[str] = Field(default_factory=list, description="Observation summaries")
    success: bool = Field(default=True, description="Whether the commitment succeeded")
    external_result_summary: str = Field(default="", description="Summary of external result")
    discarded_hypothesis_ids: List[str] = Field(default_factory=list, description="Hypothesis IDs to discard")
    strengthened_hypothesis_ids: List[str] = Field(default_factory=list, description="Hypothesis IDs to strengthen")
    new_anchor_fact_summaries: List[str] = Field(default_factory=list, description="New anchored fact summaries")
    revision_summary: str = Field(default="", description="Summary of the revision")


class ExportRequest(BaseModel):
    """Export request."""
    source_name: str = Field(default="api")
    domain: str = Field(default="core")



def _get_store(request: Request) -> StateStore:
    """Get the StateStore from app.state, initializing lazily if needed."""
    store = getattr(request.app.state, "state_store", None)
    if store is None:
        config = getattr(request.app.state, "app_config", None)
        if config is None:
            config = load_config()
            request.app.state.app_config = config
        store = StateStore(config.persistence.storage_dir)
        request.app.state.state_store = store
    return store


def _get_config(request: Request) -> CEEConfig:
    """Get the CEEConfig from app.state."""
    return getattr(request.app.state, "app_config", None)


async def _broadcast_event(event_data: Dict[str, Any], subscribers: List[WebSocket]) -> None:
    """Broadcast event to all WebSocket subscribers."""
    disconnected = []
    for ws in subscribers:
        try:
            await ws.send_json(event_data)
        except Exception:
            logger.warning("WebSocket broadcast failed", exc_info=True)
            disconnected.append(ws)

    for ws in disconnected:
        if ws in subscribers:
            subscribers.remove(ws)


def _build_metrics_from_artifact(artifact) -> Dict[str, Any]:
    """Build a metrics summary from a RunArtifact for report generation."""
    return {
        "allowed": artifact.allowed_count,
        "blocked": artifact.blocked_count,
        "approval_required": artifact.approval_required_count,
        "denied": artifact.denied_count,
        "total_events": len(artifact.event_payloads),
    }


def _rebuild_event_log_from_artifact(artifact) -> EventLog:
    """Rebuild an EventLog from a RunArtifact's event payloads.

    Attempts to deserialize each payload as its correct event type
    (CommitmentEvent, ModelRevisionEvent, DeliberationEvent,
    ToolCallEvent, ToolResultEvent) with fallback to generic Event.
    """
    from .events import DeliberationEvent
    from .tools import ToolCallEvent, ToolResultEvent

    log = EventLog()
    for payload in artifact.event_payloads:
        if not isinstance(payload, dict):
            continue
        event_type = payload.get("event_type", "")
        try:
            if event_type == "commitment":
                event = CommitmentEvent.from_dict(payload)
                log.append(event)
            elif event_type == "revision":
                event = ModelRevisionEvent.from_dict(payload)
                log.append(event)
            elif event_type == "deliberation.step":
                event = DeliberationEvent.from_dict(payload)
                log.append(event)
            elif event_type == "tool.call":
                event = ToolCallEvent.from_dict(payload)
                log.append(event)
            elif event_type == "tool.result":
                event = ToolResultEvent.from_dict(payload)
                log.append(event)
            else:
                event = Event(
                    event_type=event_type,
                    payload=payload.get("payload", payload),
                    actor=payload.get("actor", "unknown"),
                )
                log.append(event)
        except Exception:
            pass
    return log


def _render_artifact_stub(artifact_data: Dict[str, Any], run_id: str) -> str:
    """Render a minimal report stub from raw artifact data."""
    counts = artifact_data.get("counts", {})
    lines = [
        f"# Run Report: {run_id}",
        "",
        "## Summary",
        f"- Allowed: {counts.get('allowed', 0)}",
        f"- Blocked: {counts.get('blocked', 0)}",
        f"- Approval Required: {counts.get('approval_required', 0)}",
        f"- Denied: {counts.get('denied', 0)}",
        "",
    ]
    narration = artifact_data.get("narration_lines", [])
    if narration:
        lines.append("## Narration")
        for line in narration:
            lines.append(f"- {line}")
    return "\n".join(lines)


_EXEMPT_PATHS = frozenset({"/", "/health", "/docs", "/openapi.json"})


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key_env: str = "CEE_API_KEY"):
        super().__init__(app)
        self.api_key_env = api_key_env

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        if request.url.path.startswith("/ws/"):
            return await call_next(request)

        required_key = os.environ.get(self.api_key_env)
        if not required_key:
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key")
        if provided_key != required_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    config = getattr(app.state, "app_config", None)
    if config is None:
        config = load_config()
        app.state.app_config = config

    store = StateStore(config.persistence.storage_dir)
    app.state.state_store = store

    state_file = Path(config.persistence.state_file)
    if state_file.exists():
        try:
            store.load_world_state()
        except Exception:
            logger.error("Failed to load world state", exc_info=True)

    app.state.event_subscribers = []
    app.state.task_queue = {}

    yield

    subscribers = getattr(app.state, "event_subscribers", [])
    for ws in subscribers:
        try:
            await ws.close()
        except Exception:
            logger.debug("WebSocket close failed")
    subscribers.clear()


def create_app(config: Optional[CEEConfig] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = load_config()

    app = FastAPI(
        title="Cognitive Execution Engine API",
        description="REST API and WebSocket interface for CEE",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.app_config = config

    app.add_middleware(APIKeyMiddleware, api_key_env=config.api.api_key_env)

    @app.get("/health")
    async def health_check(request: Request):
        """Health check endpoint."""
        subscribers = getattr(request.app.state, "event_subscribers", [])
        task_queue = getattr(request.app.state, "task_queue", {})
        return {
            "status": "healthy",
            "version": "1.0.0",
            "subscribers": len(subscribers),
            "pending_tasks": len(task_queue),
        }

    @app.post("/tasks", response_model=TaskResponse)
    async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks, http_request: Request):
        """Execute a task through the CEE pipeline."""
        import uuid

        task_id = str(uuid.uuid4())[:8]
        store = _get_store(http_request)
        subscribers = getattr(http_request.app.state, "event_subscribers", [])

        config = _get_config(http_request)
        event_fmt = config.policy.event_format if config else "new"
        domain = DomainContext(domain_name=request.domain, event_format=event_fmt)
        log = EventLog()

        gate = None
        if request.auto_approve:
            gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

        observer = ExecutionObserver(
            debug_context=DebugContext(verbose_logging=False)
        )
        observer.metrics.start_phase(ExecutionPhase.COMPILATION)

        try:
            result = execute_task_in_domain(
                request.task,
                domain,
                event_log=log,
                approval_gate=gate,
            )

            observer.metrics.end_phase(ExecutionPhase.COMPILATION)

            event_count = len(list(log.all()))

            for event in log.all():
                event_data = {
                    "task_id": task_id,
                    "event_type": event.event_type,
                    "payload": event.to_dict() if hasattr(event, 'to_dict') else {},
                    "actor": getattr(event, 'actor', 'system'),
                }
                await _broadcast_event(event_data, subscribers)

                try:
                    store.append_event(event)
                except Exception:
                    logger.warning("Failed to persist event", exc_info=True)

            response_data = {
                "task": {
                    "objective": result.task.objective,
                    "kind": result.task.kind,
                    "risk_level": result.task.risk_level,
                },
                "events": event_count,
                "allowed_transitions": result.allowed_count,
                "denied_transitions": len(result.denied_transitions),
                "approval_required": result.requires_approval_count,
                "redirect_proposed": result.redirect_proposed,
                "commitment_events": len(result.commitment_events),
                "revision_events": len(result.revision_events),
                "world_state": result.world_state.to_dict() if result.world_state else None,
            }

            metrics = observer.metrics.get_summary()

            if result.world_state is not None:
                try:
                    save_world_state(store, result.world_state)
                except Exception:
                    logger.error("Failed to save WorldState", exc_info=True)

            try:
                from .persistence import append_commitment_event, append_revision_event
                for ce in result.commitment_events:
                    append_commitment_event(store, ce)
                for rev in result.revision_events:
                    append_revision_event(store, rev)
            except Exception:
                logger.warning("Failed to persist commitment/revision events", exc_info=True)

            try:
                from .run_artifact import run_result_to_artifact
                artifact = run_result_to_artifact(result)
                store.save_run_artifact(task_id, artifact.to_dict())
            except Exception:
                logger.warning("Failed to save run artifact", exc_info=True)

            return TaskResponse(
                task_id=task_id,
                status="completed",
                result=response_data,
                metrics=metrics,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/reports/{run_id}")
    async def get_execution_report(run_id: str, request: Request):
        """Get Markdown execution report for a specific run.

        Only returns a report if a RunArtifact exists for this run_id.
        There is no fallback to global event data — a report is bound
        to exactly one run, identified by run_id.
        """
        store = _get_store(request)

        try:
            artifact_data = store.load_run_artifact(run_id)

            if artifact_data is not None:
                from .run_artifact import RunArtifact
                try:
                    artifact = RunArtifact.from_dict(artifact_data)

                    workflow = None
                    workflow_result = None
                    if artifact.workflow_data is not None:
                        try:
                            from .workflow import Workflow
                            workflow = Workflow.from_dict(artifact.workflow_data)
                        except Exception:
                            pass
                    if artifact.workflow_result_data is not None:
                        try:
                            from .workflow import WorkflowResult
                            workflow_result = WorkflowResult.from_dict(artifact.workflow_result_data)
                        except Exception:
                            pass

                    gen = ReportGenerator(
                        event_log=_rebuild_event_log_from_artifact(artifact),
                        metrics_summary=_build_metrics_from_artifact(artifact),
                        workflow=workflow,
                        workflow_result=workflow_result,
                    )
                    md = gen.render_markdown(run_id=run_id)
                except Exception:
                    md = _render_artifact_stub(artifact_data, run_id)

                from fastapi.responses import PlainTextResponse
                return PlainTextResponse(content=md, media_type="text/markdown")

            raise HTTPException(status_code=404, detail=f"No RunArtifact found for run_id: {run_id}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/calibrate")
    async def calibrate(request: CalibrationRequest, http_request: Request):
        """Run self-model calibration cycle."""
        config = _get_config(http_request)
        state_file = Path(config.persistence.state_file) if config else Path("cee_state.json")
        self_model: dict[str, object] = {}

        if state_file.exists():
            try:
                ws = load_world_state_from_file(state_file)
                self_model = {
                    "capabilities": list(ws.self_capability_summary),
                    "limits": list(ws.self_limit_summary),
                    "reliability": ws.self_reliability_estimate,
                }
            except Exception:
                logger.error("Failed to load world state for calibration", exc_info=True)

        log = EventLog()
        gate = None
        if request.auto_approve:
            gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))

        try:
            result = run_calibration_cycle(log, current_self_model=self_model, approval_gate=gate)
            
            return {
                "total_transitions": result.snapshot.total_transitions,
                "allow_rate": result.snapshot.allow_rate,
                "denial_rate": result.snapshot.denial_rate,
                "escalation_rate": result.snapshot.approval_escalation_rate,
                "redirect_count": result.snapshot.redirect_count,
                "proposal_count": result.proposal_count,
                "approved_count": result.approved_count,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/export")
    async def export_state(request: ExportRequest, http_request: Request):
        """Export execution state."""
        config = _get_config(http_request)
        state_file = Path(config.persistence.state_file) if config else Path("cee_state.json")
        if not state_file.exists():
            raise HTTPException(status_code=404, detail="No state file found")

        try:
            ws = load_world_state_from_file(state_file)
            log = EventLog()

            manager = ImportExportManager()
            package = manager.export_execution(
                ws,
                log,
                source_name=request.source_name,
                domain_name=request.domain,
            )
            
            return {
                "status": "succeeded",
                "package": json.loads(package.to_json()),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        """WebSocket endpoint for real-time event streaming."""
        await websocket.accept()
        subscribers = getattr(websocket.app.state, "event_subscribers", [])
        subscribers.append(websocket)

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            if websocket in subscribers:
                subscribers.remove(websocket)
        except Exception:
            logger.debug("WebSocket events connection closed unexpectedly")
            if websocket in subscribers:
                subscribers.remove(websocket)

    @app.websocket("/ws/tasks/{task_id}")
    async def websocket_task(websocket: WebSocket, task_id: str):
        """WebSocket endpoint for task-specific updates."""
        await websocket.accept()
        task_queue = getattr(websocket.app.state, "task_queue", {})

        if task_id in task_queue:
            await websocket.send_json(task_queue[task_id])
        
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("WebSocket task connection closed")

    @app.get("/tasks")
    async def list_tasks(request: Request):
        """List recent tasks."""
        store = _get_store(request)
        try:
            run_ids = store.list_run_ids()
            return {
                "tasks": [{"run_id": rid} for rid in run_ids],
                "total": len(run_ids),
            }
        except Exception:
            return {
                "tasks": [],
                "total": 0,
            }

    @app.get("/world")
    async def get_world_state(request: Request):
        """Get current engine state as WorldState."""
        from .persistence import load_world_state

        store = _get_store(request)

        try:
            ws = load_world_state(store)
            return ws.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/world/commitment")
    async def execute_commitment(request: CommitmentRequest, http_request: Request):
        """Execute a commitment through the new architecture with full closed loop.

        Flow: create commitment -> evaluate policy -> persist commitment ->
              derive revision -> persist revision -> apply revision to WorldState ->
              save WorldState.
        """
        from .commitment import (
            make_observation_commitment, make_act_commitment, make_tool_contact_commitment,
            complete_commitment,
        )
        from .commitment_policy import evaluate_commitment_policy
        from .revision import revise_from_commitment
        from .persistence import (
            save_world_state, load_world_state,
            append_commitment_event, append_revision_event,
        )

        store = _get_store(http_request)

        try:
            ws = load_world_state(store)

            valid_kinds = {"observe", "act", "tool_contact", "internal_commit"}
            if request.commitment_kind not in valid_kinds:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown commitment kind: {request.commitment_kind}",
                )

            policy_decision = evaluate_commitment_policy(
                request.commitment_kind,
                reversibility=getattr(request, "reversibility", None),
            )
            if not policy_decision.allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"Commitment policy blocked: {policy_decision.reason}",
                )

            if request.commitment_kind == "observe":
                ce = make_observation_commitment(
                    ws,
                    event_id=f"ce-api-{int(time.monotonic()*1000)}",
                    intent_summary=request.intent_summary,
                    target_entity_ids=tuple(request.target_entity_ids),
                )
            elif request.commitment_kind == "act":
                ce = make_act_commitment(
                    ws,
                    event_id=f"ce-api-{int(time.monotonic()*1000)}",
                    intent_summary=request.intent_summary,
                    action_summary=request.intent_summary,
                    target_entity_ids=tuple(request.target_entity_ids),
                )
            elif request.commitment_kind == "tool_contact":
                ce = make_tool_contact_commitment(
                    ws,
                    event_id=f"ce-api-{int(time.monotonic()*1000)}",
                    intent_summary=request.intent_summary,
                    action_summary=request.intent_summary,
                    target_entity_ids=tuple(request.target_entity_ids),
                )
            elif request.commitment_kind == "internal_commit":
                ce = CommitmentEvent(
                    event_id=f"ce-api-{int(time.monotonic()*1000)}",
                    source_state_id=ws.state_id,
                    commitment_kind="internal_commit",
                    intent_summary=request.intent_summary,
                    action_summary=request.intent_summary,
                    success=True,
                    reversibility="reversible",
                )

            ce = complete_commitment(
                ce,
                success=request.success,
                external_result_summary=request.external_result_summary,
                observation_summaries=tuple(request.observation_summaries),
            )

            append_commitment_event(store, ce)

            rev = None
            new_ws = ws
            if request.discarded_hypothesis_ids or request.strengthened_hypothesis_ids or request.new_anchor_fact_summaries:
                rev, new_ws = revise_from_commitment(
                    ws,
                    ce,
                    revision_id=f"rev-api-{int(time.monotonic()*1000)}",
                    resulting_state_id=f"ws_{int(ws.state_id.split('_')[-1]) + 1}" if ws.state_id.startswith("ws_") else "ws_1",
                    discarded_hypothesis_ids=tuple(request.discarded_hypothesis_ids),
                    strengthened_hypothesis_ids=tuple(request.strengthened_hypothesis_ids),
                    new_anchor_fact_summaries=tuple(request.new_anchor_fact_summaries),
                    revision_summary=request.revision_summary,
                )
                append_revision_event(store, rev)

            save_world_state(store, new_ws)

            result = {
                "status": "completed",
                "commitment": ce.to_dict(),
                "policy_decision": {
                    "allowed": policy_decision.allowed,
                    "reason": policy_decision.reason,
                    "requires_approval": policy_decision.requires_approval,
                },
                "world_state_id": new_ws.state_id,
                "anchored_facts_count": len(new_ws.anchored_fact_summaries),
                "active_hypotheses_count": len(new_ws.active_hypotheses()),
            }

            if rev is not None:
                result["revision"] = {
                    "revision_id": rev.revision_id,
                    "revision_kind": rev.revision_kind,
                    "deltas_count": len(rev.deltas),
                }

            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/metrics")
    async def get_metrics(request: Request):
        """Get engine metrics."""
        subscribers = getattr(request.app.state, "event_subscribers", [])
        task_queue = getattr(request.app.state, "task_queue", {})
        return {
            "uptime_seconds": time.monotonic(),
            "subscribers": len(subscribers),
            "pending_tasks": len(task_queue),
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "Cognitive Execution Engine API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    return app


def main():
    """Run the API server."""
    import uvicorn
    
    config = load_config()
    app = create_app(config=config)
    uvicorn.run(app, host=config.api.host, port=config.api.port)


if __name__ == "__main__":
    main()
