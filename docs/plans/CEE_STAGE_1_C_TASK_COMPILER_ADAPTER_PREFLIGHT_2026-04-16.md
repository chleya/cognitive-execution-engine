# CEE Stage 1C Preflight — LLM Task Compiler Adapter

## Status

Canonical.

## Trigger

Stage 0 is closed. The next project question is whether an LLM can be introduced as a constrained cognitive operator without gaining planning, patching, tool, or execution authority.

## Chosen Entry

Stage 1 Option C: LLM task compiler adapter.

## Authority Restored

Input boundary authority.

The LLM may compile raw input into `TaskSpec`. It may not produce plans, state patches, tool calls, or execution decisions.

## Why Bounded

Only the adapter boundary is introduced:

- prompt envelope
- parser
- forbidden field rejection
- fake deterministic compiler for tests

No real model call.

## Forbidden Scope

- No actual LLM API call
- No planner generation by LLM
- No state patch generation by LLM
- No tool calls
- No execution
- No database
- No prompt optimization loop

## Stop Conditions

Stop when:

- valid TaskSpec-like JSON is accepted
- malformed JSON is rejected
- non-object JSON is rejected
- forbidden execution fields are rejected
- invalid kind/risk fields are rejected
- tests pass

