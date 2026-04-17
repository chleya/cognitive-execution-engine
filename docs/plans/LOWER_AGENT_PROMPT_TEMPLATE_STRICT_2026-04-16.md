# Strict Prompt Template For Lower-Risk Agents

Use this template when delegating documentation, demo, cleanup, or focused tests.

```text
Repo: F:\cognitive-execution-engine

Mode: bounded support task. Do not change core semantics.

Current canonical state:
- Stage 0 R1-R12 complete.
- Current test baseline: python -m pytest -q -> 61 passed.
- Current demo baseline: python examples\stage0_demo.py runs successfully.
- Core invariant:
  Input compiler structures.
  Planner proposes.
  Policy decides.
  EventLog audits.
  Replay applies only allowed transitions.
  RunArtifact preserves execution evidence.

Before editing:
1. Run python -m pytest -q and record actual count.
2. Read docs\DOCUMENT_STATUS.md.
3. Read docs\plans\CEE_STAGE_0_SUMMARY_2026-04-16.md.
4. Do not use stale task descriptions if they conflict with current files.

Allowed work:
- Documentation updates
- Examples
- README cleanup
- Test README cleanup
- Focused tests that do not require core semantic changes

Forbidden:
- Do not change src\cee_core semantics.
- Do not add LLM integration.
- Do not add database, file persistence, API server, CLI framework, UI, or tool gateway.
- Do not change replay rule.
- Do not change policy rule.
- Do not write "autonomous agent", "self-aware", "digital human", or "model decides".
- Do not claim a stale test count.
- Do not use non-ASCII box drawing or arrows unless the file already requires them.
- Do not introduce mojibake or corrupted text.

Required validation:
- python -m pytest -q
- python examples\stage0_demo.py
- Search docs for stale phrases:
  - "38 passed"
  - "54 passed"
  - "R5 complete"
  - "R6 next"
  - mojibake markers such as "鈥", "鈫", "涓"

If any validation fails:
- Fix only your surface if the cause is yours.
- If the failure is in core semantics, stop and report. Do not patch core.

Final response must include:
- Files changed
- Exact test output
- Exact demo status
- Any stale text removed
- Confirmation that core semantics were not changed
```

