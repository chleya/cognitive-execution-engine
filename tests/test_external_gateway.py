"""Tests for external gateway and import/export functionality."""

import json
import os
import tempfile

import pytest

from cee_core.external_gateway import (
    HTTPGateway,
    HTTPGatewayConfig,
    WebhookConfig,
    WebhookDispatcher,
    DefaultWebhookSender,
    RateLimiter,
)
from cee_core.import_export import (
    ImportExportManager,
    ExportPackage,
    ExportManifest,
)
from cee_core.state import State
from cee_core.event_log import EventLog
from cee_core.events import Event
from cee_core.persistence import StateStore


class TestRateLimiter:
    def test_allows_initial_requests(self):
        limiter = RateLimiter(max_calls=5, window_seconds=1.0)
        
        for _ in range(5):
            assert limiter.is_allowed() is True
    
    def test_blocks_after_limit(self):
        limiter = RateLimiter(max_calls=2, window_seconds=1.0)
        
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False
    
    def test_resets_after_window(self):
        limiter = RateLimiter(max_calls=2, window_seconds=0.1)
        
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False
        
        import time
        time.sleep(0.15)
        
        assert limiter.is_allowed() is True


class TestHTTPGatewayConfig:
    def test_default_config(self):
        config = HTTPGatewayConfig(base_url="https://api.example.com")
        
        assert config.base_url == "https://api.example.com"
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.allowed_domains is None
    
    def test_custom_config(self):
        config = HTTPGatewayConfig(
            base_url="https://api.example.com",
            timeout_seconds=10.0,
            max_retries=5,
            allowed_domains=["api.example.com"],
        )
        
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 5
        assert "api.example.com" in config.allowed_domains


class TestHTTPGateway:
    def test_gateway_creation(self):
        config = HTTPGatewayConfig(base_url="https://api.test.com")
        gateway = HTTPGateway(config=config)
        
        assert gateway.config.base_url == "https://api.test.com"
    
    def test_domain_validation_allowed(self):
        config = HTTPGatewayConfig(
            base_url="https://api.example.com",
            allowed_domains=["api.example.com"],
        )
        gateway = HTTPGateway(config=config)

        assert gateway._is_domain_allowed("https://api.example.com/v1") is True

    def test_domain_validation_subdomain_allowed(self):
        config = HTTPGatewayConfig(
            base_url="https://api.example.com",
            allowed_domains=["example.com"],
        )
        gateway = HTTPGateway(config=config)

        assert gateway._is_domain_allowed("https://api.example.com/v1") is True
        assert gateway._is_domain_allowed("https://sub.example.com/path") is True

    def test_domain_validation_blocked(self):
        config = HTTPGatewayConfig(
            base_url="https://api.example.com",
            allowed_domains=["api.example.com"],
        )
        gateway = HTTPGateway(config=config)

        assert gateway._is_domain_allowed("https://evil.com/api") is False

    def test_domain_validation_substring_bypass_blocked(self):
        config = HTTPGatewayConfig(
            base_url="https://api.example.com",
            allowed_domains=["example.com"],
        )
        gateway = HTTPGateway(config=config)

        assert gateway._is_domain_allowed("https://evil-example.com/api") is False
        assert gateway._is_domain_allowed("https://example.com.evil.com/api") is False

    def test_domain_validation_no_restrictions(self):
        config = HTTPGatewayConfig(base_url="https://api.example.com")
        gateway = HTTPGateway(config=config)

        assert gateway._is_domain_allowed("https://any.com/api") is True
    
    def test_get_stats(self):
        config = HTTPGatewayConfig(base_url="https://api.test.com")
        gateway = HTTPGateway(config=config)
        
        stats = gateway.get_stats()
        
        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "error_rate" in stats
    
    def test_request_without_requests_library(self, monkeypatch):
        config = HTTPGatewayConfig(base_url="https://api.test.com")
        gateway = HTTPGateway(config=config)
        
        import sys
        original_requests = sys.modules.get('requests')
        sys.modules['requests'] = None
        
        result = gateway.get("/test", call_id="test_1")
        
        assert result["status"] == "failed"
        assert "not installed" in result["error"]
        
        if original_requests is not None:
            sys.modules['requests'] = original_requests


class TestWebhookConfig:
    def test_default_config(self):
        config = WebhookConfig(url="https://hooks.example.com/test")
        
        assert config.url == "https://hooks.example.com/test"
        assert config.events == ["*"]
        assert config.retry_count == 2


class TestWebhookDispatcher:
    def test_dispatcher_creation(self):
        dispatcher = WebhookDispatcher(webhooks=[])
        
        assert dispatcher._dispatch_count == 0
    
    def test_matches_webhook_wildcard(self):
        webhook = WebhookConfig(
            url="https://hooks.example.com/test",
            events=["*"],
        )
        dispatcher = WebhookDispatcher(webhooks=[webhook])
        
        assert dispatcher._matches_webhook("any.event", webhook) is True
    
    def test_matches_webhook_specific(self):
        webhook = WebhookConfig(
            url="https://hooks.example.com/test",
            events=["task.received", "plan.created"],
        )
        dispatcher = WebhookDispatcher(webhooks=[webhook])
        
        assert dispatcher._matches_webhook("task.received", webhook) is True
        assert dispatcher._matches_webhook("unknown.event", webhook) is False
    
    def test_dispatch_no_matching_webhooks(self):
        webhook = WebhookConfig(
            url="https://hooks.example.com/test",
            events=["specific.event"],
        )
        dispatcher = WebhookDispatcher(webhooks=[webhook])
        
        event = Event(
            event_type="other.event",
            payload={},
            actor="test",
        )
        
        result = dispatcher.dispatch(event)
        
        assert result["dispatched_to"] == 0
    
    def test_get_stats(self):
        dispatcher = WebhookDispatcher(webhooks=[])
        
        stats = dispatcher.get_stats()
        
        assert "total_dispatched" in stats
        assert "total_success" in stats
        assert "success_rate" in stats
    
    def test_default_webhook_sender_without_requests(self, monkeypatch):
        sender = DefaultWebhookSender()
        
        import sys
        original = sys.modules.get('requests')
        sys.modules['requests'] = None
        
        result = sender({"url": "https://test.com", "headers": {}, "data": {}, "timeout": 1.0})
        
        assert result is False
        
        if original is not None:
            sys.modules['requests'] = original


class TestExportManifest:
    def test_default_manifest(self):
        manifest = ExportManifest()
        
        assert manifest.version == "1.0.0"
        assert manifest.export_timestamp != ""
    
    def test_custom_manifest(self):
        manifest = ExportManifest(
            source_name="test_instance",
            domain_name="document_analysis",
            metadata={"key": "value"},
        )
        
        assert manifest.source_name == "test_instance"
        assert manifest.domain_name == "document_analysis"
        assert manifest.metadata["key"] == "value"


class TestExportPackage:
    def test_json_roundtrip(self):
        state = {"goals": {"active": ["task_1"]}}
        events = [{"event_type": "task.received"}]
        manifest = ExportManifest(source_name="test")
        
        package = ExportPackage(
            manifest=manifest,
            state=state,
            events=events,
        )
        
        json_str = package.to_json()
        restored = ExportPackage.from_json(json_str)
        
        assert restored.manifest.source_name == "test"
        assert restored.state == state
        assert len(restored.events) == 1
    
    def test_save_and_load_file(self):
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, "export.json")
        
        state = {"beliefs": {"test": "data"}}
        events = [{"event_type": "test.event"}]
        manifest = ExportManifest(source_name="file_test")
        
        package = ExportPackage(
            manifest=manifest,
            state=state,
            events=events,
        )
        
        saved_path = package.save_to_file(file_path)
        restored = ExportPackage.from_file(saved_path)
        
        assert restored.manifest.source_name == "file_test"
        assert restored.state == {"beliefs": {"test": "data"}}
        
        os.remove(file_path)
        os.rmdir(temp_dir)


class TestImportExportManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store = StateStore(self.temp_dir)
        self.manager = ImportExportManager(state_store=self.store)
    
    def teardown_method(self):
        self.store.clear()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_export_execution(self):
        state = State()
        state.goals["active"] = ["task_1"]
        state.beliefs["test"] = "value"
        
        log = EventLog()
        log.append(Event(
            event_type="task.received",
            payload={"task_id": "task_1"},
            actor="compiler",
        ))
        
        package = self.manager.export_execution(
            state,
            log,
            source_name="test_export",
            domain_name="test_domain",
        )
        
        assert package.manifest.source_name == "test_export"
        assert package.manifest.domain_name == "test_domain"
        assert package.manifest.event_count == 1
        assert package.state["goals"]["active"] == ["task_1"]
    
    def test_import_execution(self):
        state_data = {
            "memory": {},
            "goals": {"active": ["imported_task"]},
            "beliefs": {"key": "value"},
            "self_model": {},
            "policy": {},
            "domain_data": {},
            "tool_affordances": {},
            "meta": {"version": 5},
        }
        manifest = ExportManifest(
            source_name="import_test",
            state_count=1,
            event_count=0,
        )
        package = ExportPackage(
            manifest=manifest,
            state=state_data,
            events=[],
        )
        
        result = self.manager.import_execution(package)
        
        assert result["status"] == "succeeded"
        assert result["state_restored"] is True
        assert result["events_imported"] == 0
        
        restored_state = self.store.load_state()
        assert restored_state.goals["active"] == ["imported_task"]
        assert restored_state.beliefs["key"] == "value"
    
    def test_export_and_import_roundtrip(self):
        original_state = State()
        original_state.goals["active"] = ["roundtrip_task"]
        original_state.beliefs["data"] = "preserved"
        original_state.meta["version"] = 10
        
        original_log = EventLog()
        original_log.append(Event(
            event_type="task.received",
            payload={"task_id": "roundtrip_task"},
            actor="compiler",
        ))
        
        export_path = self.manager.export_to_file(
            original_state,
            original_log,
            os.path.join(self.temp_dir, "roundtrip.json"),
            source_name="roundtrip",
            domain_name="test",
        )
        
        import_result = self.manager.import_from_file(export_path)
        
        assert import_result["status"] == "succeeded"
        assert import_result["state_restored"] is True
        
        imported_state = self.store.load_state()
        assert imported_state.goals["active"] == ["roundtrip_task"]
        assert imported_state.beliefs["data"] == "preserved"
        assert imported_state.meta["version"] == 10
    
    def test_get_export_info(self):
        state = State()
        state.goals["active"] = ["info_task"]
        
        log = EventLog()
        log.append(Event(
            event_type="task.received",
            payload={"task_id": "info_task"},
            actor="compiler",
        ))
        
        export_path = self.manager.export_to_file(
            state,
            log,
            os.path.join(self.temp_dir, "info.json"),
        )
        
        info = self.manager.get_export_info(export_path)
        
        assert info["manifest"]["source_name"] == "cee_instance"
        assert info["manifest"]["event_count"] == 1
        assert "task.received" in info["event_types"]
        assert "state_keys" in info
    
    def test_export_version_warning(self):
        state_data = {
            "memory": {},
            "goals": {},
            "beliefs": {},
            "self_model": {},
            "policy": {},
            "domain_data": {},
            "tool_affordances": {},
            "meta": {},
        }
        manifest = ExportManifest(
            version="0.9.0",
            source_name="old_version",
        )
        package = ExportPackage(
            manifest=manifest,
            state=state_data,
            events=[],
        )
        
        result = self.manager.import_execution(package)
        
        assert len(result["warnings"]) > 0
        assert "Version mismatch" in result["warnings"][0]
