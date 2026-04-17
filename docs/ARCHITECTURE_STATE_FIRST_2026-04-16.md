# State-Centered Architecture

## Primitive Equation

```text
S(t+1) = reduce(S(t), observation_t, tool_result_t, reflection_t, policy_t)
```

The reducer, not the model, defines valid system evolution.

## Architecture Shape

CEE uses a three-layer architecture:

### Core Layer

Fixed, safety-oriented:

- state graph trunk
- reducer
- policy
- approval
- audit
- replay
- tool contracts

### Cognitive Layer

General primitives:

- observe
- interpret
- hypothesize
- plan
- act
- verify
- reflect
- escalate

### Domain Plugin Layer

Replaceable domain surfaces:

- tool plugins
- glossary packs
- domain rules
- evaluators
- connectors

## Authority Split

| Surface | Owner | Forbidden |
|---|---|---|
| State continuity | `State` and reducer | Chat history as source of truth |
| Tool permission | Policy engine | Model-decided permission |
| High-risk action | Human approval | Silent auto-execution |
| Memory promotion | Evidence gate | Direct model-written memory |
| Audit | Append-only events | Final-answer-only logging |
| Self model | Calibration metrics and config | Persona claims |

## Runtime Loop

1. receive task event
2. load state snapshot
3. compile bounded task
4. select bounded cognitive primitives
5. select bounded next action through deliberation
6. receive candidate plan
7. validate schema
8. evaluate policy
9. execute only allowed actions
10. create observations
11. reduce state
12. append audit events
13. return approved result

## LLM Insertion Points

| Insertion Point | Allowed Output | Cannot Do |
|---|---|---|
| Task compiler | `TaskSpec` | Execute tools |
| Deliberation selector | `ReasoningStep` | Bypass planner or policy |
| Planner | `PlanSpec` | Bypass policy |
| Belief extractor | `BeliefCandidate[]` | Write canonical belief directly |
| Reflection summarizer | `ReflectionCandidate` | Promote procedural rule |
| Narrator | User-facing answer | Invent audit facts |

## Deliberation Boundary

`ReasoningStep` is a bounded runtime contract that sits between `TaskSpec` and
`PlanSpec`.

It may:

- summarize the current task situation
- record missing information
- enumerate a small candidate action set
- select one next action such as `propose_plan` or `request_read_tool`

It may not:

- write canonical state directly
- execute tools directly
- bypass planner, policy, or approval
- replace `PlanSpec` as the execution contract

Its role is to make the next bounded step explicit and auditable, not to create
open-ended model-owned reasoning authority.

## State Shape

The fixed trunk remains:

- `memory`
- `goals`
- `beliefs`
- `self_model`
- `policy`
- `meta`

Future domain layers may extend around this trunk through explicit contracts,
for example:

- `domain_constraints`
- `active_entities`
- `risk_cases`
- `tool_affordances`
