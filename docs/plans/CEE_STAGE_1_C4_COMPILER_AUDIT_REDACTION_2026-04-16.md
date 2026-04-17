# CEE Stage 1C4 — Compiler Audit Redaction

## Status

Complete.

## Goal

Avoid making raw user input plaintext audit logging the default before a real LLM provider is introduced.

## Changes

- Added `audit_policy.py`.
- Added `CompilerAuditPolicy`.
- Added audit modes:
  - `hash`
  - `plain`
  - `omit`
- `execute_task_with_compiler()` now accepts `audit_policy`.
- Default audit mode is `hash`.
- Added 4 focused tests.

## Semantics

- Default compiler request audit records SHA-256 hash and input length.
- Plain mode records raw input explicitly.
- Omit mode records only the audit mode.
- Unknown mode is rejected.
- Compiler success/rejection events are unchanged.
- Replay remains unaffected because compiler audit events are audit-only.

## Authority Restored

Audit privacy authority.

The system no longer defaults to storing raw user input in compiler request audit events.

## Explicit Non-Goals

- No PII detector
- No semantic summarizer
- No encryption
- No access-control layer
- No external audit store
- No real LLM provider

## Validation

```text
python -m pytest -q
84 passed
```

## Next Candidate Cut

Stage 1C5 should add a real-provider interface stub, not provider integration:

- provider protocol
- request/response envelope
- timeout/error shape
- no network call

