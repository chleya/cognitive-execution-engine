## Status: canonical
## Owner: architecture
## Last-Reviewed: 2026-04-16
## Scope: planner-tool-call-boundary-review

# CEE Stage 1E2 Planner Tool Call Architecture Review

## Goal

Review Stage 1E1 after planner-proposed tool calls were added, and confirm that
the new contract does not leak execution authority to the planner or to the
LLM compiler path.

## Review Verdict

GREEN.

Planner-proposed tool calls are now a valid audited contract, but they are not
yet autonomous execution.

## Validation

```text
python -m pytest -q
145 passed, 2 skipped
```

## Reviewed Surfaces

- `planner.py`
- `tools.py`
- `tool_runner.py`
- `tool_observation_flow.py`
- planner-related tests
- Stage 1D plans D1-D10
- Stage 1E1 plan

## Confirmed Invariants

| Invariant | Status |
|---|---|
| Planner may propose tool calls | confirmed |
| Planner-proposed tool call is not execution | confirmed |
| Tool proposals are still audited through `ToolCallEvent` | confirmed |
| Tool proposals are still policy-evaluated through `ToolRegistry` | confirmed |
| Unknown tools are denied | confirmed |
| Write tools are not executed by the read-only runner | confirmed |
| External side-effect tools are not executed by the read-only runner | confirmed |
| `execute_plan()` requires explicit `tool_registry` when tool calls are present | confirmed |
| Missing `tool_registry` fails closed | confirmed |
| Planner still cannot write state except through `StatePatch` + policy | confirmed |
| LLM compiler still cannot propose tool calls | confirmed |
| Provider output still cannot bypass `TaskSpec` parsing | confirmed |
| Tool results still do not automatically become beliefs | confirmed |

## Active Chain

The valid audited chain is now:

```text
TaskSpec
-> deterministic planner
-> PlanSpec(candidate_patches, proposed_tool_calls)
-> policy-evaluated patch transitions
-> policy-evaluated ToolCallEvent
-> optional read-only runner
-> ToolResultEvent
-> ObservationCandidate
-> ObservationEvent
-> explicit promotion patch
-> policy
-> replay
```

## Still Forbidden

The following paths remain forbidden:

```text
LLM output
-> tool_calls
```

```text
ToolResultEvent
-> beliefs
```

```text
Planner tool proposal
-> implicit execution
```

## Remaining Risks

- Tool argument schema is carried structurally but not yet validated.
- Planner tool proposals are deterministic only; no ranking or conflict policy exists.
- No approval fulfillment path exists for write/external tool execution.
- No general orchestrator yet connects planner-proposed tool calls directly to
  the read-only runner.

## Recommended Next Cut

Stage 1E3 should add a deterministic planner-tool execution flow:

- consume planner-proposed read-only tool calls
- require explicit `ToolRegistry` and `InMemoryReadOnlyToolRunner`
- append `ToolCallEvent`
- run only allowed read-only calls
- append `ToolResultEvent`
- optionally produce observations through the existing explicit path

Do not let the LLM compiler generate tool calls in that cut.
