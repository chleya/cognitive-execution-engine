"""Domain plugin contracts.

Stage 1F introduces typed domain extension contracts without adding a dynamic
plugin loader or external runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DomainRulePack:
    """A named set of explicit domain rules."""

    name: str
    version: str
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class GlossaryPack:
    """A named domain glossary."""

    name: str
    version: str
    terms: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluatorPlugin:
    """A domain evaluator contract.

    This is metadata only at this stage. It does not execute evaluation logic.
    """

    name: str
    version: str
    target: str
    metrics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectorSpec:
    """A domain connector contract.

    This is a structural connector declaration, not an active external
    connection.
    """

    name: str
    kind: str
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainPluginPack:
    """A bounded domain extension bundle."""

    domain_name: str
    rule_packs: tuple[DomainRulePack, ...] = ()
    glossary_packs: tuple[GlossaryPack, ...] = ()
    evaluators: tuple[EvaluatorPlugin, ...] = ()
    connectors: tuple[ConnectorSpec, ...] = ()
    state_extensions: tuple[str, ...] = ()
    denied_patch_sections: tuple[str, ...] = ()
    approval_required_patch_sections: tuple[str, ...] = ()


@dataclass
class DomainPluginRegistry:
    """In-memory registry for named domain plugin packs."""

    _packs: dict[str, DomainPluginPack] = field(default_factory=dict)

    def register(self, pack: DomainPluginPack) -> None:
        if pack.domain_name in self._packs:
            raise ValueError(f"Domain plugin pack already registered: {pack.domain_name}")
        self._packs[pack.domain_name] = pack

    def get(self, domain_name: str) -> DomainPluginPack | None:
        return self._packs.get(domain_name)

    def list(self) -> tuple[DomainPluginPack, ...]:
        return tuple(self._packs.values())
