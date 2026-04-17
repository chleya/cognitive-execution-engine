"""Domain context contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .domain_plugins import DomainPluginPack, DomainPluginRegistry


@dataclass(frozen=True)
class DomainContext:
    """Explicit runtime domain context.

    A domain context selects a named domain and optionally carries the matching
    plugin pack metadata. It does not dynamically load code.
    """

    domain_name: str
    plugin_pack: DomainPluginPack | None = None


def build_domain_context(
    domain_name: str,
    *,
    registry: DomainPluginRegistry | None = None,
) -> DomainContext:
    """Build a domain context from an optional registry."""

    if not domain_name.strip():
        raise ValueError("domain_name cannot be empty")

    if registry is None:
        return DomainContext(domain_name=domain_name)

    plugin_pack = registry.get(domain_name)
    if plugin_pack is None:
        raise ValueError(f"Unknown domain plugin pack: {domain_name}")
    return DomainContext(domain_name=domain_name, plugin_pack=plugin_pack)
