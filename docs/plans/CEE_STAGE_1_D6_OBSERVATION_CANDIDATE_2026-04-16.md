# CEE Stage 1D6 — ObservationCandidate

## Status

Complete.

## Goal

Introduce the observation boundary between tool results and beliefs.

## Changes

- Added `observations.py`.
- Added `ObservationCandidate`.
- Added `observation_from_tool_result(event)`.
- Added 3 focused tests.

## Semantics

- A successful `ToolResultEvent` can become an `ObservationCandidate`.
- A failed `ToolResultEvent` cannot become an observation.
- Observation carries source tool, call id, content, confidence, and provenance.
- Observation is not a belief.
- Observation does not mutate state.
- No automatic result-to-belief promotion exists.

## Authority Restored

Observation boundary authority.

The system now has an explicit layer between tool output and belief state.

## Explicit Non-Goals

- No belief promotion
- No state patch generation
- No confidence calibration beyond fixed placeholder
- No observation event log yet
- No LLM interpretation of observations

## Validation

```text
python -m pytest -q
132 passed, 2 skipped
```

## Next Candidate Cut

Stage 1D7 should add `ObservationEvent` audit records, still without belief promotion.

