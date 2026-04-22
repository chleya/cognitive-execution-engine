"""Configuration management for CEE.

Provides YAML/JSON configuration loading with environment variable overrides
for all engine components.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "static"
    model: str = "gpt-4"
    api_key_env: str = "CEE_LLM_API_KEY"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key_env: str = "CEE_EMBEDDING_API_KEY"

    def get_api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env) or os.environ.get("OPENAI_API_KEY")

    def get_embedding_api_key(self) -> Optional[str]:
        return os.environ.get(self.embedding_api_key_env) or os.environ.get(self.api_key_env)


@dataclass(frozen=True)
class ToolConfig:
    """Tool execution configuration."""
    allowed_domains: List[str] = field(default_factory=lambda: ["*"])
    rate_limit: int = 60
    timeout_seconds: float = 30.0
    max_output_size: int = 100000
    sandbox_enabled: bool = True


@dataclass(frozen=True)
class PolicyConfig:
    """Policy engine configuration."""
    auto_approve_read: bool = True
    require_approval_write: bool = True
    max_patch_size: int = 100
    allowed_sections: List[str] = field(default_factory=lambda: [
        "memory", "goals", "beliefs", "self_model",
        "policy", "domain_data", "tool_affordances", "meta"
    ])
    event_format: str = "new"


@dataclass(frozen=True)
class PersistenceConfig:
    """State persistence configuration."""
    storage_dir: str = "cee_storage"
    state_file: str = "cee_state.json"
    events_file: str = "cee_events.jsonl"
    snapshot_interval: int = 100
    auto_save: bool = True


@dataclass(frozen=True)
class ObservabilityConfig:
    """Observability configuration."""
    verbose_logging: bool = False
    breakpoints: List[str] = field(default_factory=list)
    export_metrics: bool = True
    metrics_interval_seconds: float = 10.0


@dataclass(frozen=True)
class APIConfig:
    """Web API configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    api_key_env: str = "CEE_API_KEY"


@dataclass(frozen=True)
class CEEConfig:
    """Complete CEE configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    api: APIConfig = field(default_factory=APIConfig)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CEEConfig":
        """Create config from dictionary."""
        llm_data = data.get("llm", {})
        tools_data = data.get("tools", {})
        policy_data = data.get("policy", {})
        persistence_data = data.get("persistence", {})
        observability_data = data.get("observability", {})
        api_data = data.get("api", {})

        return cls(
            llm=LLMConfig(
                provider=llm_data.get("provider", "static"),
                model=llm_data.get("model", "gpt-4"),
                api_key_env=llm_data.get("api_key_env", "CEE_LLM_API_KEY"),
                embedding_model=llm_data.get("embedding_model", "text-embedding-3-small"),
                embedding_api_key_env=llm_data.get("embedding_api_key_env", "CEE_EMBEDDING_API_KEY"),
            ),
            tools=ToolConfig(
                allowed_domains=tools_data.get("allowed_domains", ["*"]),
                rate_limit=tools_data.get("rate_limit", 60),
                timeout_seconds=tools_data.get("timeout_seconds", 30.0),
                max_output_size=tools_data.get("max_output_size", 100000),
                sandbox_enabled=tools_data.get("sandbox_enabled", True),
            ),
            policy=PolicyConfig(
                auto_approve_read=policy_data.get("auto_approve_read", True),
                require_approval_write=policy_data.get("require_approval_write", True),
                max_patch_size=policy_data.get("max_patch_size", 100),
                allowed_sections=policy_data.get("allowed_sections", [
                    "memory", "goals", "beliefs", "self_model",
                    "policy", "domain_data", "tool_affordances", "meta"
                ]),
                event_format=policy_data.get("event_format", "new"),
            ),
            persistence=PersistenceConfig(
                storage_dir=persistence_data.get("storage_dir", "cee_storage"),
                state_file=persistence_data.get("state_file", "cee_state.json"),
                events_file=persistence_data.get("events_file", "cee_events.jsonl"),
                snapshot_interval=persistence_data.get("snapshot_interval", 100),
                auto_save=persistence_data.get("auto_save", True),
            ),
            observability=ObservabilityConfig(
                verbose_logging=observability_data.get("verbose_logging", False),
                breakpoints=observability_data.get("breakpoints", []),
                export_metrics=observability_data.get("export_metrics", True),
                metrics_interval_seconds=observability_data.get("metrics_interval_seconds", 10.0),
            ),
            api=APIConfig(
                host=api_data.get("host", "0.0.0.0"),
                port=api_data.get("port", 8000),
                debug=api_data.get("debug", False),
                cors_origins=api_data.get("cors_origins", ["*"]),
                api_key_env=api_data.get("api_key_env", "CEE_API_KEY"),
            ),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "CEEConfig":
        """Load configuration from YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML config files. "
                "Install it with: pip install pyyaml"
            )

        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {yaml_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_path: str | Path) -> "CEEConfig":
        """Load configuration from JSON file."""
        import json

        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {json_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key_env": self.llm.api_key_env,
                "embedding_model": self.llm.embedding_model,
                "embedding_api_key_env": self.llm.embedding_api_key_env,
            },
            "tools": {
                "allowed_domains": self.tools.allowed_domains,
                "rate_limit": self.tools.rate_limit,
                "timeout_seconds": self.tools.timeout_seconds,
                "max_output_size": self.tools.max_output_size,
                "sandbox_enabled": self.tools.sandbox_enabled,
            },
            "policy": {
                "auto_approve_read": self.policy.auto_approve_read,
                "require_approval_write": self.policy.require_approval_write,
                "max_patch_size": self.policy.max_patch_size,
                "allowed_sections": self.policy.allowed_sections,
                "event_format": self.policy.event_format,
            },
            "persistence": {
                "storage_dir": self.persistence.storage_dir,
                "state_file": self.persistence.state_file,
                "events_file": self.persistence.events_file,
                "snapshot_interval": self.persistence.snapshot_interval,
                "auto_save": self.persistence.auto_save,
            },
            "observability": {
                "verbose_logging": self.observability.verbose_logging,
                "breakpoints": self.observability.breakpoints,
                "export_metrics": self.observability.export_metrics,
                "metrics_interval_seconds": self.observability.metrics_interval_seconds,
            },
            "api": {
                "host": self.api.host,
                "port": self.api.port,
                "debug": self.api.debug,
                "cors_origins": self.api.cors_origins,
                "api_key_env": self.api.api_key_env,
            },
        }

    def save_yaml(self, path: str | Path) -> str:
        """Save configuration to YAML file."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required. Install with: pip install pyyaml")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

        return str(path)

    def save_json(self, path: str | Path) -> str:
        """Save configuration to JSON file."""
        import json

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        return str(path)


def load_config(config_path: Optional[str | Path] = None) -> CEEConfig:
    """Load configuration from file or use defaults."""
    if config_path is None:
        for path in ["cee_config.yaml", "cee_config.json"]:
            if Path(path).exists():
                config_path = path
                break

    if config_path is None:
        return CEEConfig()

    path = Path(config_path)
    if path.suffix in (".yaml", ".yml"):
        return CEEConfig.from_yaml(path)
    elif path.suffix == ".json":
        return CEEConfig.from_json(path)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")
