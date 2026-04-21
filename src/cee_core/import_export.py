"""CEE state and event import/export capabilities.

Provides standardized formats for:
1. Exporting execution artifacts
2. Importing execution history
3. Sharing state between CEE instances
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .world_state import WorldState
from .event_log import EventLog
from .events import Event
from .persistence import StateStore


EXPORT_FORMAT_VERSION = "1.0.0"


@dataclass(frozen=True)
class ExportManifest:
    """Manifest for CEE export package."""
    version: str = EXPORT_FORMAT_VERSION
    export_timestamp: str = ""
    source_name: str = ""
    state_count: int = 0
    event_count: int = 0
    domain_name: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.export_timestamp:
            object.__setattr__(self, "export_timestamp", datetime.now().isoformat())


@dataclass(frozen=True)
class ExportPackage:
    """Complete CEE export package."""
    manifest: ExportManifest
    state: Dict[str, Any]
    events: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON."""
        return json.dumps(
            {
                "manifest": {
                    "version": self.manifest.version,
                    "export_timestamp": self.manifest.export_timestamp,
                    "source_name": self.manifest.source_name,
                    "state_count": self.manifest.state_count,
                    "event_count": self.manifest.event_count,
                    "domain_name": self.manifest.domain_name,
                    "metadata": self.manifest.metadata or {},
                },
                "state": self.state,
                "events": self.events,
                "metadata": self.metadata or {},
            },
            indent=indent,
            default=str,
        )

    def save_to_file(self, file_path: str | Path) -> str:
        """Save to file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        
        return str(path)

    @classmethod
    def from_json(cls, json_str: str) -> "ExportPackage":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        
        manifest_data = data.get("manifest", {})
        manifest = ExportManifest(
            version=manifest_data.get("version", EXPORT_FORMAT_VERSION),
            export_timestamp=manifest_data.get("export_timestamp", ""),
            source_name=manifest_data.get("source_name", ""),
            state_count=manifest_data.get("state_count", 0),
            event_count=manifest_data.get("event_count", 0),
            domain_name=manifest_data.get("domain_name", ""),
            metadata=manifest_data.get("metadata", {}),
        )
        
        return cls(
            manifest=manifest,
            state=data.get("state", {}),
            events=data.get("events", []),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_file(cls, file_path: str | Path) -> "ExportPackage":
        """Load from file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())


class ImportExportManager:
    """Manages import/export operations."""
    
    def __init__(self, state_store: Optional[StateStore] = None):
        self.state_store = state_store
    
    def export_execution(
        self,
        state: WorldState,
        event_log: EventLog,
        *,
        source_name: str = "cee_instance",
        domain_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExportPackage:
        """Export current execution state and events."""
        events = [e.to_dict() if hasattr(e, 'to_dict') else {} for e in event_log.all()]
        
        manifest = ExportManifest(
            source_name=source_name,
            state_count=1,
            event_count=len(events),
            domain_name=domain_name,
            metadata=metadata or {},
        )
        
        return ExportPackage(
            manifest=manifest,
            state=state.to_dict(),
            events=events,
            metadata=metadata or {},
        )
    
    def import_execution(self, package: ExportPackage) -> Dict[str, Any]:
        """Import execution state and events."""
        result = {
            "status": "succeeded",
            "state_restored": False,
            "events_imported": 0,
            "warnings": [],
        }
        
        if package.manifest.version != EXPORT_FORMAT_VERSION:
            result["warnings"].append(
                f"Version mismatch: expected {EXPORT_FORMAT_VERSION}, got {package.manifest.version}"
            )
        
        if self.state_store is not None:
            ws = WorldState.from_dict(package.state)
            self.state_store.save_world_state(ws)
            result["state_restored"] = True
        
        result["events_imported"] = len(package.events)
        
        return result
    
    def export_to_file(
        self,
        state: WorldState,
        event_log: EventLog,
        file_path: str | Path,
        **kwargs,
    ) -> str:
        """Export to file."""
        package = self.export_execution(state, event_log, **kwargs)
        return package.save_to_file(file_path)
    
    def import_from_file(self, file_path: str | Path) -> Dict[str, Any]:
        """Import from file."""
        package = ExportPackage.from_file(file_path)
        return self.import_execution(package)
    
    def get_export_info(self, file_path: str | Path) -> Dict[str, Any]:
        """Get information about export file."""
        package = ExportPackage.from_file(file_path)
        return {
            "file_path": str(file_path),
            "file_size_bytes": os.path.getsize(file_path),
            "manifest": {
                "version": package.manifest.version,
                "export_timestamp": package.manifest.export_timestamp,
                "source_name": package.manifest.source_name,
                "state_count": package.manifest.state_count,
                "event_count": package.manifest.event_count,
                "domain_name": package.manifest.domain_name,
            },
            "state_keys": list(package.state.keys()),
            "event_types": list(set(e.get("event_type", "unknown") for e in package.events)),
        }
