"""API-level integration tests covering the full closed loop:
/tasks -> /world -> /world/commitment -> /reports/{run_id}

These tests verify that the API endpoints form a coherent, auditable
execution chain, not just isolated endpoints.
"""

import json
import pytest
from pathlib import Path

from cee_core.web_api import create_app
from cee_core.config import CEEConfig, PersistenceConfig
from cee_core.persistence import StateStore


@pytest.fixture
def app_with_storage(tmp_path):
    storage_dir = str(tmp_path / "storage")
    config = CEEConfig(persistence=PersistenceConfig(storage_dir=storage_dir))
    app = create_app(config=config)
    return app, storage_dir


@pytest.fixture
def client(app_with_storage):
    from fastapi.testclient import TestClient
    app, _ = app_with_storage
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


class TestWorldEndpoint:
    def test_get_world_state(self, client):
        resp = client.get("/world")
        assert resp.status_code == 200
        data = resp.json()
        assert "state_id" in data
        assert "entities" in data
        assert "hypotheses" in data
        assert "anchored_fact_summaries" in data


class TestWorldCommitmentEndpoint:
    def test_observe_commitment(self, client):
        resp = client.post("/world/commitment", json={
            "commitment_kind": "observe",
            "intent_summary": "Check project status",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "commitment" in data
        assert data["commitment"]["commitment_kind"] == "observe"
        assert "world_state_id" in data

    def test_commitment_with_revision(self, client):
        resp = client.post("/world/commitment", json={
            "commitment_kind": "observe",
            "intent_summary": "Verify alpha status",
            "success": True,
            "external_result_summary": "alpha_status=delayed",
            "observation_summaries": ["alpha_status=delayed"],
            "new_anchor_fact_summaries": ["alpha_status=delayed"],
            "revision_summary": "Confirmed alpha is delayed",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "revision" in data
        assert data["revision"]["revision_kind"] in ("expansion", "correction")
        assert data["anchored_facts_count"] >= 1

    def test_commitment_persists_world_state(self, client, app_with_storage):
        _, storage_dir = app_with_storage
        store = StateStore(storage_dir)

        client.post("/world/commitment", json={
            "commitment_kind": "observe",
            "intent_summary": "Check status",
            "new_anchor_fact_summaries": ["test_fact=verified"],
        })

        from cee_core.persistence import load_world_state
        ws = load_world_state(store)
        assert "test_fact=verified" in ws.anchored_fact_summaries

    def test_commitment_persists_events(self, client, app_with_storage):
        _, storage_dir = app_with_storage
        store = StateStore(storage_dir)

        client.post("/world/commitment", json={
            "commitment_kind": "observe",
            "intent_summary": "Check status",
        })

        from cee_core.persistence import load_commitment_events
        events = load_commitment_events(store)
        assert len(events) >= 1

    def test_irreversible_act_blocked(self, client):
        resp = client.post("/world/commitment", json={
            "commitment_kind": "act",
            "intent_summary": "Deploy to production",
        })
        assert resp.status_code == 403

    def test_unknown_commitment_kind(self, client):
        resp = client.post("/world/commitment", json={
            "commitment_kind": "invalid",
            "intent_summary": "Test",
        })
        assert resp.status_code == 400


class TestReportsEndpoint:
    def test_nonexistent_run_returns_404(self, client):
        resp = client.get("/reports/nonexistent_run")
        assert resp.status_code == 404
        assert "RunArtifact" in resp.json()["detail"]

    def test_report_from_artifact_without_workflow(self, client, app_with_storage):
        _, storage_dir = app_with_storage
        store = StateStore(storage_dir)

        from cee_core.run_artifact import RunArtifact
        from cee_core.tasks import TaskSpec
        from cee_core.planner import PlanSpec

        task = TaskSpec(objective="Test task", kind="verification", risk_level="low", success_criteria=(), requested_primitives=())
        plan = PlanSpec(objective="Test task", candidate_deltas=())
        artifact = RunArtifact(
            task=task,
            plan=plan,
            event_payloads=(),
            narration_lines=("Task started", "Task completed"),
            allowed_count=1,
            blocked_count=0,
            approval_required_count=0,
            denied_count=0,
            world_state_snapshot=None,
        )
        store.save_run_artifact("run_abc", artifact.to_dict())

        resp = client.get("/reports/run_abc")

        assert resp.status_code == 200
        assert "run_abc" in resp.text
        assert "Execution Summary" in resp.text

    def test_report_from_artifact_with_workflow(self, client, app_with_storage):
        _, storage_dir = app_with_storage
        store = StateStore(storage_dir)

        from cee_core.run_artifact import RunArtifact
        from cee_core.tasks import TaskSpec
        from cee_core.planner import PlanSpec
        from cee_core.workflow import Workflow, WorkflowResult, WorkflowStep, StepResult

        task = TaskSpec(objective="Analyze codebase", kind="verification", risk_level="low", success_criteria=(), requested_primitives=())
        plan = PlanSpec(objective="Analyze codebase", candidate_deltas=())
        workflow = Workflow(
            name="test_workflow",
            steps=[
                WorkflowStep(step_id="s1", name="analyze", action="read"),
                WorkflowStep(step_id="s2", name="report", action="write"),
            ],
            workflow_id="wf_test_001",
        )
        workflow_result = WorkflowResult(
            workflow_id="wf_test_001",
            status="succeeded",
            step_results=[
                StepResult(step_id="s1", status="succeeded", execution_time_ms=100.0),
                StepResult(step_id="s2", status="succeeded", execution_time_ms=200.0),
            ],
            variables={"result": "analysis_complete"},
            total_execution_time_ms=300.0,
        )
        artifact = RunArtifact(
            task=task,
            plan=plan,
            event_payloads=(),
            narration_lines=("Step 1 completed", "Step 2 completed"),
            allowed_count=2,
            blocked_count=0,
            approval_required_count=0,
            denied_count=0,
            workflow_data=workflow.to_dict(),
            workflow_result_data=workflow_result.to_dict(),
        )
        store.save_run_artifact("run_wf", artifact.to_dict())

        resp = client.get("/reports/run_wf")
        assert resp.status_code == 200
        assert "run_wf" in resp.text
        assert "Step Results" in resp.text
        assert "Final Results" in resp.text


class TestRunArtifactPersistence:
    def test_save_and_load_run_artifact(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        artifact_data = {"test": "data", "counts": {"allowed": 5}}
        store.save_run_artifact("run_001", artifact_data)

        loaded = store.load_run_artifact("run_001")
        assert loaded is not None
        assert loaded["test"] == "data"

    def test_load_nonexistent_returns_none(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        assert store.load_run_artifact("nonexistent") is None

    def test_list_run_ids(self, tmp_path):
        store = StateStore(str(tmp_path / "store"))
        store.save_run_artifact("run_001", {"a": 1})
        store.save_run_artifact("run_002", {"b": 2})

        ids = store.list_run_ids()
        assert "run_001" in ids
        assert "run_002" in ids


class TestAutoApproveDefault:
    def test_auto_approve_defaults_to_false(self):
        from cee_core.web_api import TaskRequest
        req = TaskRequest(task="test", domain="default")
        assert req.auto_approve is False

    def test_calibration_auto_approve_defaults_to_false(self):
        from cee_core.web_api import CalibrationRequest
        req = CalibrationRequest()
        assert req.auto_approve is False
