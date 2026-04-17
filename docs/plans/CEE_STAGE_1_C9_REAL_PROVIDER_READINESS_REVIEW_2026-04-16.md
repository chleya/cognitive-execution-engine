# CEE Stage 1C9 — Real Provider Readiness Review

## Status

Complete.

## Goal

Decide whether the project is ready to add a real LLM provider implementation after the provider boundary, audit boundary, redaction policy, and TaskSpec-only parser are in place.

## Verdict

Conditionally ready.

The project is ready to add one real provider transport only if it follows the constraints below. It is not ready for broad provider abstraction, streaming, tool calling, agentic provider loops, or provider-owned planning.

## Current Protection Stack

| Layer | Status | Protection |
|---|---|---|
| `LLMProvider` protocol | complete | Provider-neutral request/response boundary |
| `EnvironmentLLMProvider` | complete | Env-var gate and injected transport |
| `ProviderBackedTaskCompiler` | complete | Provider output enters parser only |
| `parse_llm_task_response` | complete | Rejects plans, patches, tools, execution fields |
| compiler audit | complete | requested/succeeded/rejected events |
| provider audit | complete | requested/succeeded/failed metadata |
| audit redaction | complete | raw input hashed by default |
| replay boundary | complete | only allowed transitions mutate state |

## Allowed Next Cut

One provider transport may be added if:

- It implements the existing `ProviderTransport` callable.
- It is placed outside runtime/planner/policy modules.
- It uses `EnvironmentLLMProvider`.
- It is env-key gated.
- Its tests are skipped by default if no key is present.
- Unit tests use fake/mocked transport and require no network.
- Integration tests are explicit and opt-in.
- Full model output is not audited by default.

## Forbidden In First Real Provider Cut

- No streaming
- No tool calling
- No JSON mode dependency without parser validation
- No provider-specific objects in runtime
- No provider retry loop
- No provider fallback chain
- No planner generation
- No patch generation
- No direct state mutation
- No autonomous loop

## Required Environment Contract

The first real provider must document:

```text
CEE_LLM_PROVIDER=<provider-name>
CEE_LLM_MODEL=<model-name>
CEE_LLM_API_KEY=<secret>
CEE_LLM_TIMEOUT_SECONDS=<number, default 30>
```

Provider-specific env vars may exist, but runtime must only depend on the provider-neutral boundary.

## Required Test Contract

### Unit Tests

Must pass without network:

- transport builds provider request correctly
- missing env key fails closed
- fake response reaches `TaskSpec`
- forbidden response fields are rejected
- provider error is audited

### Integration Tests

Must be skipped by default:

```text
pytest.mark.integration
skip if CEE_LLM_API_KEY is missing
```

Integration test may assert only:

- provider returns text
- parser either accepts valid `TaskSpec` or rejects safely
- no tool calls / patch / plan bypass occurs

## Audit Requirements

Provider request audit may include:

- request id
- provider name
- model name if known
- timeout
- prompt role

Provider success audit may include:

- request id
- provider name
- model name
- response length

Provider audit must not include by default:

- full raw input
- full prompt
- full model output
- API key
- provider raw response object

## Real Provider Candidate Ranking

| Candidate | Fit | Notes |
|---|---|---|
| Local deterministic/mock provider | safest | Already covered by tests; useful for demos |
| Local HTTP model server | medium | Needs timeout and integration skip discipline |
| OpenAI provider | possible | Must use official SDK/docs and env-gated integration tests |
| Multi-provider registry | not ready | Too much abstraction before one provider is proven |

## Stage 1C9 Decision

The next implementation can be `Stage 1C10: first real provider transport skeleton`.

Recommended scope:

- implement one provider transport module
- keep unit tests network-free
- add one skipped integration test
- no runtime changes except importing optional provider factory if necessary

## Validation

No code changes required.

Current baseline remains:

```text
python -m pytest -q
95 passed
```

