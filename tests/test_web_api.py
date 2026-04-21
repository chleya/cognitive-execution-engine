"""Tests for CEE Web API."""

import os
import json
import tempfile
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from cee_core.web_api import create_app, TaskRequest
from cee_core.config import CEEConfig, PersistenceConfig, APIConfig


def _create_client_with_config(**config_overrides):
    config = CEEConfig(**config_overrides) if config_overrides else CEEConfig()
    app = create_app(config=config)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_has_version(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert "version" in response.json()


class TestRootEndpoint:
    def test_root(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/")

        assert response.status_code == 200
        assert "name" in response.json()
        assert response.json()["name"] == "Cognitive Execution Engine API"

    def test_root_has_docs_link(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/")

        assert "docs" in response.json()


class TestExportEndpoint:
    def test_export_no_state(self):
        app = create_app()
        client = TestClient(app)

        response = client.post("/export", json={})

        assert response.status_code == 404


class TestExecutionReportEndpoint:
    def test_execution_report_nonexistent_returns_404(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)

        response = client.get("/reports/nonexistent_run")

        assert response.status_code == 404

    def test_execution_report_from_artifact(self, tmp_path):
        os.environ.pop("CEE_API_KEY", None)
        from cee_core.config import CEEConfig, PersistenceConfig
        from cee_core.persistence import StateStore
        from cee_core.run_artifact import RunArtifact
        from cee_core.tasks import TaskSpec
        from cee_core.planner import PlanSpec

        storage_dir = str(tmp_path / "storage")
        config = CEEConfig(persistence=PersistenceConfig(storage_dir=storage_dir))
        app = create_app(config=config)

        store = StateStore(storage_dir)
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
        )
        store.save_run_artifact("test_run", artifact.to_dict())

        with TestClient(app) as client:
            response = client.get("/reports/test_run")

            assert response.status_code == 200
            assert "text/markdown" in response.headers.get("content-type", "")
            assert "test_run" in response.text


class TestMetricsEndpoint:
    def test_metrics(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/metrics")

        assert response.status_code == 200
        assert "subscribers" in response.json()


class TestTasksEndpoint:
    def test_list_tasks_empty(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/tasks")

        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestAPIKeyMiddleware:
    def test_no_key_required_when_env_not_set(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)

        response = client.get("/world")

        assert response.status_code == 200

    def test_exempt_health_endpoint(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/health")

            assert response.status_code == 200
        finally:
            del os.environ["CEE_API_KEY"]

    def test_exempt_root_endpoint(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/")

            assert response.status_code == 200
        finally:
            del os.environ["CEE_API_KEY"]

    def test_reject_request_without_key(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/world")

            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid or missing API key"
        finally:
            del os.environ["CEE_API_KEY"]

    def test_reject_request_with_wrong_key(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/world", headers={"X-API-Key": "wrong-key"})

            assert response.status_code == 401
        finally:
            del os.environ["CEE_API_KEY"]

    def test_allow_request_with_correct_key(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/world", headers={"X-API-Key": "test-secret-key"})

            assert response.status_code == 200
        finally:
            del os.environ["CEE_API_KEY"]


class TestConfigIntegration:
    def test_create_app_with_config(self):
        config = CEEConfig()
        app = create_app(config=config)
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200

    def test_create_app_with_custom_persistence_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CEEConfig(
                persistence=PersistenceConfig(storage_dir=tmpdir)
            )
            app = create_app(config=config)
            client = TestClient(app)

            response = client.get("/health")

            assert response.status_code == 200
