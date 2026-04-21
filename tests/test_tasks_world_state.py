"""Tests for TASKS-NEW-STATE-001: /tasks operates on WorldState directly."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from cee_core.runtime import execute_task, execute_task_in_domain, RunResult
from cee_core.domain_context import DomainContext
from cee_core.event_log import EventLog
from cee_core.world_state import WorldState
from cee_core.run_artifact import RunArtifact, run_result_to_artifact
from cee_core.persistence import StateStore, save_world_state, load_world_state
from cee_core.config import CEEConfig, PersistenceConfig, PolicyConfig


class TestRunResultWorldState:
    def test_execute_task_produces_world_state_in_dual_mode(self):
        ctx = DomainContext(domain_name="core", event_format="dual")
        result = execute_task_in_domain("test task", ctx)
        assert result.world_state is not None
        assert isinstance(result.world_state, WorldState)

    def test_execute_task_produces_world_state_in_new_mode(self):
        ctx = DomainContext(domain_name="core", event_format="new")
        result = execute_task_in_domain("test task", ctx)
        assert result.world_state is not None
        assert isinstance(result.world_state, WorldState)

    def test_execute_task_produces_world_state_by_default(self):
        result = execute_task_in_domain("test task", DomainContext(domain_name="core"))
        assert result.world_state is not None
        assert isinstance(result.world_state, WorldState)

    def test_world_state_has_provenance(self):
        ctx = DomainContext(domain_name="core", event_format="dual")
        result = execute_task_in_domain("test task", ctx)
        assert result.world_state is not None
        assert len(result.world_state.provenance_refs) > 0

    def test_world_state_replay_matches_commitment_count(self):
        ctx = DomainContext(domain_name="core", event_format="dual")
        result = execute_task_in_domain("test task", ctx)
        assert result.world_state is not None
        assert len(result.world_state.provenance_refs) == len(result.commitment_events)


class TestRunArtifactWorldStateSnapshot:
    def test_artifact_contains_world_state_snapshot_in_dual_mode(self):
        ctx = DomainContext(domain_name="core", event_format="dual")
        result = execute_task_in_domain("test task", ctx)
        artifact = run_result_to_artifact(result)
        assert artifact.world_state_snapshot is not None
        assert "state_id" in artifact.world_state_snapshot

    def test_artifact_contains_world_state_snapshot_by_default(self):
        result = execute_task_in_domain("test task", DomainContext(domain_name="core"))
        artifact = run_result_to_artifact(result)
        assert artifact.world_state_snapshot is not None
        assert "state_id" in artifact.world_state_snapshot

    def test_artifact_world_state_roundtrip(self):
        ctx = DomainContext(domain_name="core", event_format="dual")
        result = execute_task_in_domain("test task", ctx)
        artifact = run_result_to_artifact(result)

        data = artifact.to_dict()
        assert "world_state_snapshot" in data
        assert data["world_state_snapshot"] is not None

        restored = RunArtifact.from_dict(data)
        assert restored.world_state_snapshot is not None
        assert restored.world_state_snapshot["state_id"] == artifact.world_state_snapshot["state_id"]


class TestWorldStatePrimaryPersistence:
    def test_save_and_load_world_state(self, tmp_path):
        store = StateStore(str(tmp_path))
        ws = WorldState(
            state_id="ws_3",
            entities=(),
            hypotheses=(),
            dominant_goals=("test goal",),
            anchored_fact_summaries=("fact1",),
            provenance_refs=("rev-1", "rev-2"),
        )

        save_world_state(store, ws)
        loaded = load_world_state(store)

        assert loaded.state_id == "ws_3"
        assert loaded.dominant_goals == ("test goal",)
        assert loaded.anchored_fact_summaries == ("fact1",)
        assert loaded.provenance_refs == ("rev-1", "rev-2")

    def test_load_world_state_fallback_empty(self, tmp_path):
        store = StateStore(str(tmp_path))
        ws = load_world_state(store)
        assert ws.state_id == "ws_0"

    def test_world_state_overwrites_on_save(self, tmp_path):
        store = StateStore(str(tmp_path))

        ws1 = WorldState(state_id="ws_1", dominant_goals=("goal1",))
        save_world_state(store, ws1)
        loaded1 = load_world_state(store)
        assert loaded1.dominant_goals == ("goal1",)

        ws2 = WorldState(state_id="ws_2", dominant_goals=("goal2",))
        save_world_state(store, ws2)
        loaded2 = load_world_state(store)
        assert loaded2.dominant_goals == ("goal2",)
        assert loaded2.state_id == "ws_2"


class TestTasksEndpointWorldState:
    @pytest.fixture
    def app_client(self, tmp_path):
        from cee_core.web_api import create_app
        from fastapi.testclient import TestClient

        config = CEEConfig(
            persistence=PersistenceConfig(storage_dir=str(tmp_path)),
            policy=PolicyConfig(event_format="dual"),
        )
        app = create_app(config=config)
        return TestClient(app)

    def test_tasks_returns_world_state(self, app_client):
        resp = app_client.post("/tasks", json={"task": "test task", "domain": "core"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"]["world_state"] is not None
        assert "state_id" in data["result"]["world_state"]

    def test_tasks_persists_world_state_file(self, app_client, tmp_path):
        resp = app_client.post("/tasks", json={"task": "test task", "domain": "core"})
        assert resp.status_code == 200

        ws_file = tmp_path / "world_state.json"
        assert ws_file.exists()

        ws_data = json.loads(ws_file.read_text(encoding="utf-8"))
        assert "state_id" in ws_data

    def test_tasks_world_state_matches_get_world(self, app_client):
        app_client.post("/tasks", json={"task": "test task", "domain": "core"})

        resp = app_client.get("/world")
        assert resp.status_code == 200
        ws_data = resp.json()
        assert "state_id" in ws_data

    def test_tasks_list_returns_run_ids(self, app_client):
        resp1 = app_client.post("/tasks", json={"task": "task 1", "domain": "core"})
        resp2 = app_client.post("/tasks", json={"task": "task 2", "domain": "core"})

        list_resp = app_client.get("/tasks")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] >= 2
        run_ids = [t["run_id"] for t in data["tasks"]]
        assert resp1.json()["task_id"] in run_ids
        assert resp2.json()["task_id"] in run_ids

    def test_tasks_world_state_has_provenance(self, app_client):
        resp = app_client.post("/tasks", json={"task": "test task", "domain": "core"})
        data = resp.json()
        ws = data["result"]["world_state"]
        assert len(ws.get("provenance_refs", [])) > 0

    def test_tasks_new_format_returns_world_state(self, tmp_path):
        from cee_core.web_api import create_app
        from fastapi.testclient import TestClient

        config = CEEConfig(
            persistence=PersistenceConfig(storage_dir=str(tmp_path)),
        )
        app = create_app(config=config)
        client = TestClient(app)

        resp = client.post("/tasks", json={"task": "test task", "domain": "core"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["world_state"] is not None


class TestGetWorldDirectLoad:
    @pytest.fixture
    def app_client(self, tmp_path):
        from cee_core.web_api import create_app
        from fastapi.testclient import TestClient

        config = CEEConfig(
            persistence=PersistenceConfig(storage_dir=str(tmp_path)),
            policy=PolicyConfig(event_format="dual"),
        )
        app = create_app(config=config)
        return TestClient(app)

    def test_world_loads_directly_saved_state(self, app_client):
        app_client.post("/tasks", json={"task": "test task", "domain": "core"})

        resp = app_client.get("/world")
        assert resp.status_code == 200
        ws_data = resp.json()
        assert ws_data["state_id"] != "ws_0"

    def test_world_fallback_to_bridge_when_no_file(self, tmp_path):
        from cee_core.web_api import create_app
        from fastapi.testclient import TestClient

        config = CEEConfig(
            persistence=PersistenceConfig(storage_dir=str(tmp_path)),
        )
        app = create_app(config=config)
        client = TestClient(app)

        resp = client.get("/world")
        assert resp.status_code == 200
        ws_data = resp.json()
        assert "state_id" in ws_data
