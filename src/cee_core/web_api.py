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
from .state import State, StatePatch, apply_patch
from .event_log import EventLog
from .events import Event, StateTransitionEvent
from .approval import ApprovalGate, StaticApprovalProvider
from .policy import evaluate_patch_policy, build_transition_for_patch
from .persistence import StateStore, load_state_from_file
from .observability import ExecutionObserver, ExecutionPhase, DebugContext
from .import_export import ImportExportManager, ExportPackage
from .handoff_report import build_handoff_report
from .handoff_validator import validate_handoff_state_file
from .calibration import run_calibration_cycle
from .run_artifact import run_result_to_artifact
from .report_generator import ReportGenerator
from .config import CEEConfig, load_config

import logging

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    """Task execution request."""
    task: str = Field(..., description="Task description to execute")
    domain: str = Field(default="core", description="Domain context name")
    auto_approve: bool = Field(default=True, description="Auto-approve transitions")


class TaskResponse(BaseModel):
    """Task execution response."""
    task_id: str
    status: str
    result: Dict[str, Any]
    metrics: Dict[str, Any]


class StateUpdateRequest(BaseModel):
    """State update request."""
    section: str
    key: str
    value: Any
    op: str = Field(default="set", description="Operation: set, append, merge, delete")


class CalibrationRequest(BaseModel):
    """Calibration request."""
    auto_approve: bool = Field(default=True)


class ExportRequest(BaseModel):
    """Export request."""
    source_name: str = Field(default="api")
    domain: str = Field(default="core")


# Global state store and event subscribers
_state_store: Optional[StateStore] = None
_event_subscribers: List[WebSocket] = []
_task_queue: Dict[str, Dict[str, Any]] = {}
_app_config: Optional[CEEConfig] = None


def _get_config_state_file_path() -> Path:
    """Get the state file path from config."""
    if _app_config is not None:
        return Path(_app_config.persistence.state_file)
    return Path("cee_state.json")


async def _broadcast_event(event_data: Dict[str, Any]) -> None:
    """Broadcast event to all WebSocket subscribers."""
    disconnected = []
    for ws in _event_subscribers:
        try:
            await ws.send_json(event_data)
        except Exception:
            logger.warning("WebSocket broadcast failed", exc_info=True)
            disconnected.append(ws)
    
    for ws in disconnected:
        _event_subscribers.remove(ws)


def _validate_path(file_path: str, allowed_dirs: Optional[List[Path]] = None) -> Path:
    if allowed_dirs is None:
        allowed_dirs = [Path.cwd().resolve(), Path("cee_storage").resolve()]

    resolved = Path(file_path).resolve()

    for allowed_dir in allowed_dirs:
        try:
            resolved.relative_to(allowed_dir)
            return resolved
        except ValueError:
            continue

    return None


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
    global _state_store, _app_config
    
    if _app_config is None:
        _app_config = load_config()
    
    _state_store = StateStore(_app_config.persistence.storage_dir)
    
    state_file = Path(_app_config.persistence.state_file)
    if state_file.exists():
        try:
            _state_store.load_state()
        except Exception:
            logger.error("Failed to load state", exc_info=True)
    
    yield
    
    for ws in _event_subscribers:
        try:
            await ws.close()
        except Exception:
            logger.debug("WebSocket close failed")
    _event_subscribers.clear()


def create_app(config: Optional[CEEConfig] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global _app_config
    
    if config is not None:
        _app_config = config
    
    app = FastAPI(
        title="Cognitive Execution Engine API",
        description="REST API and WebSocket interface for CEE",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    if _app_config is not None:
        app.add_middleware(APIKeyMiddleware, api_key_env=_app_config.api.api_key_env)
    else:
        app.add_middleware(APIKeyMiddleware, api_key_env="CEE_API_KEY")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "subscribers": len(_event_subscribers),
            "pending_tasks": len(_task_queue),
        }

    @app.post("/tasks", response_model=TaskResponse)
    async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks):
        """Execute a task through the CEE pipeline."""
        import uuid
        
        task_id = str(uuid.uuid4())[:8]
        
        domain = DomainContext(domain_name=request.domain)
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
            
            # Broadcast events
            for event in log.all():
                event_data = {
                    "task_id": task_id,
                    "event_type": event.event_type,
                    "payload": event.to_dict() if hasattr(event, 'to_dict') else {},
                    "actor": event.actor,
                }
                await _broadcast_event(event_data)
                
                if _state_store is not None:
                    try:
                        _state_store.append_event(event)
                    except Exception:
                        logger.warning("Failed to persist event", exc_info=True)
            
            response_data = {
                "task": {
                    "objective": result.task.objective,
                    "kind": result.task.kind,
                    "risk_level": result.task.risk_level,
                },
                "events": event_count,
                "allowed_transitions": len(result.allowed_transitions),
                "denied_transitions": len(result.denied_transitions),
                "approval_required": len(result.approval_required_transitions),
                "redirect_proposed": result.redirect_proposed,
            }
            
            metrics = observer.metrics.get_summary()
            
            # Save state
            if _state_store is not None:
                try:
                    _state_store.save_state(result.replayed_state)
                except Exception:
                    logger.error("Failed to save state", exc_info=True)
            
            return TaskResponse(
                task_id=task_id,
                status="completed",
                result=response_data,
                metrics=metrics,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/state")
    async def get_state():
        """Get current engine state."""
        global _state_store
        if _state_store is None:
            _state_store = StateStore("cee_storage")
        
        try:
            state = _state_store.load_state()
            return state.snapshot()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/state")
    async def update_state(request: StateUpdateRequest):
        """Update engine state through policy-gated patch path."""
        if _state_store is None:
            raise HTTPException(status_code=500, detail="State store not initialized")
        
        try:
            state = _state_store.load_state()
            
            if request.op not in ("set", "append"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Only 'set' and 'append' operations are supported through the patch path. Got: {request.op}"
                )
            
            patch = StatePatch(
                section=request.section,
                key=request.key,
                op=request.op,
                value=request.value,
            )
            
            policy_decision = evaluate_patch_policy(patch)
            
            if policy_decision.blocked:
                raise HTTPException(
                    status_code=403,
                    detail=f"Policy blocked: {policy_decision.reason} (ref: {policy_decision.policy_ref})"
                )
            
            new_state = apply_patch(state, patch)
            
            _state_store.save_state(new_state)
            
            return {
                "status": "succeeded",
                "section": request.section,
                "key": request.key,
                "op": request.op,
                "policy_verdict": policy_decision.verdict,
                "policy_reason": policy_decision.reason,
            }
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/report")
    async def get_report(state_file: str = "cee_state.json"):
        """Get handoff readiness report."""
        validated = _validate_path(state_file)
        if validated is None:
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside allowed directories",
            )

        if not validated.exists():
            raise HTTPException(status_code=404, detail=f"State file not found: {state_file}")
        
        try:
            report = build_handoff_report(str(validated))
            validation = validate_handoff_state_file(str(validated))
            
            return {
                "report": report,
                "validation": {
                    "is_valid": validation.is_valid,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                },
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/reports/{run_id}")
    async def get_execution_report(run_id: str):
        """Get Markdown execution report for a run."""
        try:
            gen = ReportGenerator()
            md = gen.render_markdown(run_id=run_id)
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=md, media_type="text/markdown")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/calibrate")
    async def calibrate(request: CalibrationRequest):
        """Run self-model calibration cycle."""
        state_file = _get_config_state_file_path()
        state = State()
        
        if state_file.exists():
            try:
                state = load_state_from_file(state_file)
            except Exception:
                logger.error("Failed to load state for calibration", exc_info=True)
        
        log = EventLog()
        gate = None
        if request.auto_approve:
            gate = ApprovalGate(provider=StaticApprovalProvider(verdict="approved"))
        
        try:
            result = run_calibration_cycle(log, state, approval_gate=gate)
            
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
    async def export_state(request: ExportRequest):
        """Export execution state."""
        state_file = _get_config_state_file_path()
        if not state_file.exists():
            raise HTTPException(status_code=404, detail="No state file found")
        
        try:
            state = State()
            log = EventLog()
            
            manager = ImportExportManager()
            package = manager.export_execution(
                state,
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
        _event_subscribers.append(websocket)
        
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            _event_subscribers.remove(websocket)
        except Exception:
            logger.debug("WebSocket events connection closed unexpectedly")
            if websocket in _event_subscribers:
                _event_subscribers.remove(websocket)

    @app.websocket("/ws/tasks/{task_id}")
    async def websocket_task(websocket: WebSocket, task_id: str):
        """WebSocket endpoint for task-specific updates."""
        await websocket.accept()
        
        # Send any queued updates for this task
        if task_id in _task_queue:
            await websocket.send_json(_task_queue[task_id])
        
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("WebSocket task connection closed")

    @app.get("/tasks")
    async def list_tasks():
        """List recent tasks."""
        return {
            "tasks": [],
            "total": 0,
        }

    @app.get("/metrics")
    async def get_metrics():
        """Get engine metrics."""
        return {
            "uptime_seconds": time.monotonic(),
            "subscribers": len(_event_subscribers),
            "pending_tasks": len(_task_queue),
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
