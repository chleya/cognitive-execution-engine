## Status: historical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: tool-observation-foundation-review

# CEE Stage 1D10 Tool / Observation Architecture Review

## Goal

Review the Stage 1D tool and observation line before allowing planner-proposed
tool calls.

## Review Verdict

GREEN.

The Stage 1D tool and observation line preserved the intended authority
boundaries.

## Validation At Review Time

```text
python -m pytest -q
141 passed, 2 skipped
```

## Reviewed Surfaces

- `tools.py`
- `tool_runner.py`
- `observations.py`
- `tool_observation_flow.py`
- tool-related tests
- Stage 1D plans D1-D9

## Confirmed Invariants At Review Time

| Invariant | Status |
|---|---|
| Tool declaration is not execution | confirmed |
| Tool call proposal is not execution | confirmed |
| Unknown tool is denied | confirmed |
| Write tool is not executed | confirmed |
| External side-effect tool is not executed | confirmed |
| Read-only runner executes only registered read handlers | confirmed |
| `ToolResultEvent` is audit-only by default | confirmed |
| Tool result does not automatically become observation | confirmed |
| Failed tool result cannot become observation | confirmed |
| `ObservationCandidate` is not a belief | confirmed |
| `ObservationEvent` is audit-only | confirmed |
| Observation promotion creates only `StatePatch` | confirmed |
| Promotion patch still goes through policy and replay | confirmed |
| LLM still cannot produce tool calls | confirmed |
| Planner still cannot produce tool calls | confirmed |

## Key Architecture Result

The following chain became valid in Stage 1D:

```text
ToolCallSpec
-> ToolCallEvent
-> InMemoryReadOnlyToolRunner
-> ToolResultEvent
-> ObservationCandidate
-> ObservationEvent
-> explicit promotion patch
-> policy
-> EventLog
-> replay
-> belief state
```

The following shortcut remained forbidden:

```text
ToolResultEvent
-> beliefs
```

## Remaining Risks At Review Time

- Read-only was developer-declared, not independently verified.
- Tool argument schema existed but was not validated.
- Planner could not yet propose tool calls.
- LLM could not yet propose tool calls.
- No approval fulfillment path existed for write/external tools.
- No conflict resolution existed for promoted observations.

## Historical Note

This review was correct at the time it was written.

It was later superseded by Stage 1E1 and Stage 1E2, where planner-proposed tool
calls were introduced as audited, policy-evaluated contracts.
