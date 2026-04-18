import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from cee_core.config import (
    APIConfig,
    CEEConfig,
    LLMConfig,
    ObservabilityConfig,
    PersistenceConfig,
    PolicyConfig,
    ToolConfig,
    load_config,
)


class TestDefaultConfig:
    def test_default_cee_config(self):
        config = CEEConfig()

        assert config.llm.provider == "static"
        assert config.llm.model == "gpt-4"
        assert config.tools.rate_limit == 60
        assert config.tools.timeout_seconds == 30.0
        assert config.policy.auto_approve_read is True
        assert config.persistence.storage_dir == "cee_storage"
        assert config.observability.verbose_logging is False
        assert config.api.host == "0.0.0.0"
        assert config.api.port == 8000

    def test_default_llm_config(self):
        cfg = LLMConfig()

        assert cfg.provider == "static"
        assert cfg.model == "gpt-4"
        assert cfg.api_key_env == "CEE_LLM_API_KEY"
        assert cfg.embedding_model == "text-embedding-3-small"

    def test_default_tool_config(self):
        cfg = ToolConfig()

        assert cfg.allowed_domains == ["*"]
        assert cfg.rate_limit == 60
        assert cfg.sandbox_enabled is True

    def test_default_policy_config(self):
        cfg = PolicyConfig()

        assert cfg.auto_approve_read is True
        assert cfg.require_approval_write is True
        assert len(cfg.allowed_sections) == 8

    def test_default_persistence_config(self):
        cfg = PersistenceConfig()

        assert cfg.storage_dir == "cee_storage"
        assert cfg.state_file == "cee_state.json"
        assert cfg.auto_save is True

    def test_default_observability_config(self):
        cfg = ObservabilityConfig()

        assert cfg.verbose_logging is False
        assert cfg.export_metrics is True

    def test_default_api_config(self):
        cfg = APIConfig()

        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.debug is False


class TestFromDict:
    def test_from_dict_complete(self):
        data = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                "api_key_env": "MY_API_KEY",
                "embedding_model": "text-embedding-3-large",
                "embedding_api_key_env": "MY_EMBED_KEY",
            },
            "tools": {
                "allowed_domains": ["example.com"],
                "rate_limit": 30,
                "timeout_seconds": 60.0,
                "max_output_size": 50000,
                "sandbox_enabled": False,
            },
            "policy": {
                "auto_approve_read": False,
                "require_approval_write": True,
                "max_patch_size": 50,
                "allowed_sections": ["memory", "goals"],
            },
            "persistence": {
                "storage_dir": "my_storage",
                "state_file": "state.json",
                "events_file": "events.jsonl",
                "snapshot_interval": 50,
                "auto_save": False,
            },
            "observability": {
                "verbose_logging": True,
                "breakpoints": ["step1", "step2"],
                "export_metrics": False,
                "metrics_interval_seconds": 5.0,
            },
            "api": {
                "host": "127.0.0.1",
                "port": 9000,
                "debug": True,
                "cors_origins": ["http://localhost"],
            },
            "metadata": {"env": "test"},
        }

        config = CEEConfig.from_dict(data)

        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.llm.api_key_env == "MY_API_KEY"
        assert config.tools.allowed_domains == ["example.com"]
        assert config.tools.rate_limit == 30
        assert config.tools.sandbox_enabled is False
        assert config.policy.auto_approve_read is False
        assert config.policy.max_patch_size == 50
        assert config.persistence.storage_dir == "my_storage"
        assert config.persistence.auto_save is False
        assert config.observability.verbose_logging is True
        assert config.observability.breakpoints == ["step1", "step2"]
        assert config.api.host == "127.0.0.1"
        assert config.api.port == 9000
        assert config.api.debug is True
        assert config.metadata == {"env": "test"}

    def test_from_dict_partial(self):
        data = {"llm": {"provider": "anthropic"}}

        config = CEEConfig.from_dict(data)

        assert config.llm.provider == "anthropic"
        assert config.llm.model == "gpt-4"
        assert config.tools.rate_limit == 60
        assert config.api.port == 8000

    def test_from_dict_empty(self):
        config = CEEConfig.from_dict({})

        assert config.llm.provider == "static"
        assert config.tools.rate_limit == 60

    def test_from_dict_missing_sections(self):
        data = {"api": {"port": 3000}}

        config = CEEConfig.from_dict(data)

        assert config.api.port == 3000
        assert config.llm.provider == "static"

    def test_from_dict_metadata(self):
        data = {"metadata": {"key": "value", "nested": {"a": 1}}}

        config = CEEConfig.from_dict(data)

        assert config.metadata["key"] == "value"
        assert config.metadata["nested"]["a"] == 1


class TestFromYaml:
    def test_from_yaml_valid_file(self, tmp_path):
        yaml_content = """
llm:
  provider: openai
  model: gpt-4o
tools:
  rate_limit: 120
api:
  port: 9000
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        config = CEEConfig.from_yaml(str(yaml_file))

        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.tools.rate_limit == 120
        assert config.api.port == 9000

    def test_from_yaml_missing_file(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            CEEConfig.from_yaml("/nonexistent/config.yaml")

    def test_from_yaml_pathlib(self, tmp_path):
        yaml_content = "llm:\n  provider: anthropic\n"
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        config = CEEConfig.from_yaml(yaml_file)

        assert config.llm.provider == "anthropic"


class TestFromJson:
    def test_from_json_valid_file(self, tmp_path):
        data = {
            "llm": {"provider": "openai", "model": "gpt-4o-mini"},
            "api": {"port": 7000},
        }
        json_file = tmp_path / "config.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        config = CEEConfig.from_json(str(json_file))

        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o-mini"
        assert config.api.port == 7000

    def test_from_json_missing_file(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            CEEConfig.from_json("/nonexistent/config.json")

    def test_from_json_pathlib(self, tmp_path):
        data = {"tools": {"rate_limit": 10}}
        json_file = tmp_path / "config.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")

        config = CEEConfig.from_json(json_file)

        assert config.tools.rate_limit == 10


class TestToDict:
    def test_to_dict_contains_expected_keys(self):
        config = CEEConfig()
        d = config.to_dict()

        assert "llm" in d
        assert "tools" in d
        assert "policy" in d
        assert "persistence" in d
        assert "observability" in d
        assert "api" in d

    def test_to_dict_llm_values(self):
        config = CEEConfig()
        d = config.to_dict()

        assert d["llm"]["provider"] == "static"
        assert d["llm"]["model"] == "gpt-4"
        assert d["llm"]["api_key_env"] == "CEE_LLM_API_KEY"

    def test_to_dict_tools_values(self):
        config = CEEConfig()
        d = config.to_dict()

        assert d["tools"]["allowed_domains"] == ["*"]
        assert d["tools"]["rate_limit"] == 60
        assert d["tools"]["timeout_seconds"] == 30.0

    def test_to_dict_serializable(self):
        config = CEEConfig()
        d = config.to_dict()

        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_to_dict_roundtrip(self, tmp_path):
        original = CEEConfig.from_dict({
            "llm": {"provider": "openai"},
            "api": {"port": 9999},
        })

        d = original.to_dict()
        restored = CEEConfig.from_dict(d)

        assert restored.llm.provider == "openai"
        assert restored.api.port == 9999


class TestSaveYaml:
    def test_save_yaml_creates_file(self, tmp_path):
        config = CEEConfig()
        output_path = tmp_path / "output.yaml"

        result = config.save_yaml(str(output_path))

        assert result == str(output_path)
        assert output_path.exists()

    def test_save_yaml_content(self, tmp_path):
        config = CEEConfig.from_dict({"api": {"port": 5555}})
        output_path = tmp_path / "config.yaml"

        config.save_yaml(output_path)

        content = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert content["api"]["port"] == 5555

    def test_save_yaml_creates_parent_dirs(self, tmp_path):
        config = CEEConfig()
        output_path = tmp_path / "nested" / "dir" / "config.yaml"

        config.save_yaml(output_path)

        assert output_path.exists()


class TestSaveJson:
    def test_save_json_creates_file(self, tmp_path):
        config = CEEConfig()
        output_path = tmp_path / "output.json"

        result = config.save_json(str(output_path))

        assert result == str(output_path)
        assert output_path.exists()

    def test_save_json_content(self, tmp_path):
        config = CEEConfig.from_dict({"llm": {"provider": "anthropic"}})
        output_path = tmp_path / "config.json"

        config.save_json(output_path)

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["llm"]["provider"] == "anthropic"

    def test_save_json_creates_parent_dirs(self, tmp_path):
        config = CEEConfig()
        output_path = tmp_path / "deep" / "path" / "config.json"

        config.save_json(output_path)

        assert output_path.exists()


class TestEnvironmentOverrides:
    def test_llm_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("CEE_LLM_API_KEY", "test-key-123")

        config = CEEConfig()
        assert config.llm.get_api_key() == "test-key-123"

    def test_llm_api_key_fallback_to_openai(self, monkeypatch):
        monkeypatch.delenv("CEE_LLM_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key-456")

        config = CEEConfig()
        assert config.llm.get_api_key() == "openai-key-456"

    def test_llm_api_key_custom_env_name(self, monkeypatch):
        monkeypatch.delenv("CEE_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("MY_CUSTOM_KEY", "custom-key")

        config = CEEConfig.from_dict({"llm": {"api_key_env": "MY_CUSTOM_KEY"}})
        assert config.llm.get_api_key() == "custom-key"

    def test_embedding_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("CEE_EMBEDDING_API_KEY", "embed-key")

        config = CEEConfig()
        assert config.llm.get_embedding_api_key() == "embed-key"

    def test_embedding_api_key_fallback_to_llm_key(self, monkeypatch):
        monkeypatch.delenv("CEE_EMBEDDING_API_KEY", raising=False)
        monkeypatch.setenv("CEE_LLM_API_KEY", "llm-key-789")

        config = CEEConfig()
        assert config.llm.get_embedding_api_key() == "llm-key-789"

    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("CEE_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config = CEEConfig()
        assert config.llm.get_api_key() is None


class TestLoadConfig:
    def test_load_yaml_file(self, tmp_path):
        yaml_content = "llm:\n  provider: openai\n"
        config_file = tmp_path / "cee_config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert config.llm.provider == "openai"

    def test_load_json_file(self, tmp_path):
        data = {"llm": {"provider": "anthropic"}}
        config_file = tmp_path / "cee_config.json"
        config_file.write_text(json.dumps(data), encoding="utf-8")

        config = load_config(config_file)

        assert config.llm.provider == "anthropic"

    def test_load_default_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = load_config()

        assert isinstance(config, CEEConfig)
        assert config.llm.provider == "static"

    def test_load_discovers_yaml_first(self, tmp_path, monkeypatch):
        yaml_content = "llm:\n  provider: from_yaml\n"
        json_data = {"llm": {"provider": "from_json"}}

        yaml_file = tmp_path / "cee_config.yaml"
        json_file = tmp_path / "cee_config.json"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        config = load_config()

        assert config.llm.provider == "from_yaml"

    def test_load_unsupported_extension(self, tmp_path):
        config_file = tmp_path / "cee_config.toml"
        config_file.write_text("", encoding="utf-8")

        with pytest.raises(ValueError, match="Unsupported config format"):
            load_config(config_file)


class TestConfigImmutability:
    def test_config_is_frozen(self):
        config = CEEConfig()

        with pytest.raises(Exception):
            config.llm = LLMConfig(provider="changed")

    def test_llm_config_is_frozen(self):
        cfg = LLMConfig()

        with pytest.raises(Exception):
            cfg.provider = "changed"

    def test_tool_config_is_frozen(self):
        cfg = ToolConfig()

        with pytest.raises(Exception):
            cfg.rate_limit = 100
