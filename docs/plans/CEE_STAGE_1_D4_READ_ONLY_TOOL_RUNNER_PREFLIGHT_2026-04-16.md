# CEE Stage 1D4 — Read-Only Tool Runner Preflight

## Status

Canonical.

## Goal

Define the boundary for a future read-only tool runner before implementing any tool execution.

## Trigger

Stage 1D now has:

- `ToolSpec`
- `ToolCallSpec`
- `ToolCallEvent`
- `ToolResultEvent`

The next risk is accidentally treating tool execution as state authority. This preflight prevents that.

## Core Rule

Tool result is observation, not belief.

```text
ToolResultEvent
→ ObservationCandidate
→ evidence/policy gate
→ optional StatePatch
```

Never:

```text
ToolResultEvent
→ direct belief mutation
```

## Read-Only Definition

A tool is read-only only if all conditions hold:

- It does not modify external systems.
- It does not send messages.
- It does not write files.
- It does not update databases.
- It does not trigger jobs.
- It does not mutate remote state.
- It does not incur irreversible side effects.
- It only returns data needed for observation.

Examples:

| Tool | Classification | Reason |
|---|---|---|
| local document search | read-only | reads local indexed content |
| project status query | read-only | reads existing state |
| HTTP GET to public docs | read-only with network risk | no write, but external dependency |
| send email | external_side_effect | communicates externally |
| create ticket | write | mutates external system |
| update database row | write | mutates state |

## Required Future Objects

Before implementing a runner, define:

### `ToolRunner`

Executes only tools whose policy verdict is `allow`.

### `ObservationCandidate`

Represents data returned by a tool.

Required fields:

- `source_tool`
- `call_id`
- `content`
- `confidence`
- `provenance`

### `ObservationEvent`

Audit record for observation candidate.

### `promote_observation_to_patch()`

Separate policy-gated function that turns observation into a candidate `StatePatch`.

## Allowed First Implementation Scope

The first runner implementation may support only:

- in-memory deterministic tools
- no network
- no filesystem writes
- no subprocess
- no database
- no external APIs

## Forbidden In First Runner Cut

- No write tools
- No external side-effect tools
- No HTTP client
- No subprocess
- No shell command tools
- No automatic belief promotion
- No LLM-generated tool calls
- No planner-generated tool calls

## Stop Conditions

Stop implementation if:

- a tool needs credentials
- a tool touches network
- a tool writes anywhere
- a result is being directly inserted into `beliefs`
- an LLM is allowed to choose tool arguments

## Acceptance Criteria For Future D5

The read-only runner implementation is acceptable only if:

- unknown tool is denied before runner
- write tool is not executed
- external side-effect tool is not executed
- read tool returns `ToolResultEvent`
- `ToolResultEvent` does not mutate state
- observation promotion requires a separate explicit step

## Current Validation

No code change in this preflight.

Baseline:

```text
python -m pytest -q
120 passed, 2 skipped
```

