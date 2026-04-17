## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: domain-plugin-contracts

# CEE Stage 1F2 Domain Plugin Contracts

## Goal

Turn `domain-pluggable` from a documentation claim into a typed engine
boundary.

## Deliverables

- `DomainRulePack`
- `GlossaryPack`
- `EvaluatorPlugin`
- `ConnectorSpec`
- `DomainPluginPack`
- `DomainPluginRegistry`
- `domain_data` as the first explicit state extension surface

## Result

CEE now has:

- a fixed core state trunk
- a general primitive layer
- a typed domain extension boundary

without introducing:

- dynamic plugin loading
- framework dependency injection
- external connectors
- live evaluator execution

## Validation

```text
python -m pytest -q
158 passed, 2 skipped
```

## Boundary Notes

- `domain_data` is patchable, but still goes through reducer and policy
- plugins are contracts, not active code loaders
- connectors are declarations, not live connections
- evaluators are metadata contracts, not executing evaluators
