# CEE Secret Handling Notice

## Status

Canonical.

## Rule

Provider keys must never be committed to this repository.

Use environment variables only.

## Required Action

If a provider key is pasted into chat, terminal history, logs, screenshots, or documentation, treat it as exposed and rotate it in the provider console.

## Supported Environment Variables

```text
CEE_LLM_PROVIDER=<openai|minimax_anthropic|volcengine_ark>
CEE_LLM_MODEL=<model-name>
CEE_LLM_API_KEY=<secret>
CEE_LLM_BASE_URL=<provider-base-url>
CEE_RUN_LIVE_LLM_TESTS=0
```

## Forbidden

- Do not hardcode keys in Python files.
- Do not place keys in Markdown.
- Do not place keys in examples.
- Do not print keys in logs.
- Do not include keys in `RunArtifact`.
- Do not include keys in provider audit events.

