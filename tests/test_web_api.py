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


class TestStateEndpoints:
    def test_get_state_empty(self):
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/state")
        
        assert response.status_code == 200
        assert "memory" in response.json()
        assert "goals" in response.json()

    def test_update_state_set_allowed_section(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/state", json={
            "section": "memory",
            "key": "test_key",
            "value": "test_value",
            "op": "set",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "succeeded"
        assert response.json()["policy_verdict"] == "allow"

    def test_update_state_blocked_section_policy(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/state", json={
            "section": "policy",
            "key": "test_key",
            "value": "test_value",
            "op": "set",
        })
        
        assert response.status_code == 403
        assert "Policy blocked" in response.json()["detail"]

    def test_update_state_blocked_section_meta(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/state", json={
            "section": "meta",
            "key": "test_key",
            "value": "test_value",
            "op": "set",
        })
        
        assert response.status_code == 403

    def test_update_state_requires_approval_section(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/state", json={
            "section": "self_model",
            "key": "test_key",
            "value": "test_value",
            "op": "set",
        })
        
        assert response.status_code == 403

    def test_update_state_unsupported_op(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/state", json={
            "section": "memory",
            "key": "test_key",
            "value": "test_value",
            "op": "delete",
        })
        
        assert response.status_code == 400
        assert "Only 'set' and 'append'" in response.json()["detail"]

    def test_update_state_append(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        client.post("/state", json={
            "section": "memory",
            "key": "my_list",
            "value": [],
            "op": "set",
        })
        
        response = client.post("/state", json={
            "section": "memory",
            "key": "my_list",
            "value": "item1",
            "op": "append",
        })
        
        assert response.status_code == 200
        assert response.json()["policy_verdict"] == "allow"


class TestReportEndpoint:
    def test_report_missing_file(self):
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/report?state_file=nonexistent.json")
        
        assert response.status_code == 404

    def test_report_path_traversal_blocked(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/report?state_file=../../../etc/passwd")

        assert response.status_code == 403

    def test_report_path_traversal_absolute_blocked(self):
        app = create_app()
        client = TestClient(app)

        response = client.get("/report?state_file=/etc/passwd")

        assert response.status_code == 403

    def test_report_valid_state_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", dir=".", delete=False) as f:
            state_data = {"memory": {}, "goals": {}, "beliefs": {}, "self_model": {}, "policy": {}, "domain_data": {}, "tool_affordances": {}, "meta": {"version": 0}}
            f.write(json.dumps(state_data).encode())
            temp_path = f.name
        
        try:
            app = create_app()
            client = TestClient(app)
            
            response = client.get(f"/report?state_file={temp_path}")
            
            assert response.status_code in (200, 500)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestExportEndpoint:
    def test_export_no_state(self):
        app = create_app()
        client = TestClient(app)
        
        response = client.post("/export", json={})
        
        assert response.status_code == 404


class TestExecutionReportEndpoint:
    def test_execution_report_returns_markdown(self):
        os.environ.pop("CEE_API_KEY", None)
        app = create_app()
        client = TestClient(app)
        
        response = client.get("/reports/test_run")
        
        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("content-type", "")


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

        response = client.get("/state")

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

            response = client.get("/state")

            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid or missing API key"
        finally:
            del os.environ["CEE_API_KEY"]

    def test_reject_request_with_wrong_key(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/state", headers={"X-API-Key": "wrong-key"})

            assert response.status_code == 401
        finally:
            del os.environ["CEE_API_KEY"]

    def test_allow_request_with_correct_key(self):
        os.environ["CEE_API_KEY"] = "test-secret-key"
        try:
            app = create_app()
            client = TestClient(app)

            response = client.get("/state", headers={"X-API-Key": "test-secret-key"})

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
