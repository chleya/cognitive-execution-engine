# Recovery Playbook

## Purpose

This file is for a weaker follow-up model. When something goes wrong, do not
improvise. Use the matching recovery path below.

## 1. Focused Test Fails

Do this in order:

1. Read the exact failing assertion.
2. Re-open only the file under test and the test file.
3. Check whether the failure is:
   - expected string mismatch
   - count mismatch
   - serialization shape mismatch
   - import error
4. Fix the smallest cause only.
5. Re-run the focused test before touching anything else.

## 2. Full Test Fails But Focused Test Passes

Do this in order:

1. Read the first failing test only.
2. Check whether the change leaked outside allowed files.
3. Look for:
   - import cycle
   - changed event ordering
   - changed artifact schema
   - changed visible counts in docs/tests
4. Fix the first cause before reading later failures.

## 3. Import Cycle Appears

Common safe fix:

1. Move type-only imports behind `TYPE_CHECKING`.
2. Prefer string annotations.
3. Avoid importing runtime-heavy modules at top level if only type hints are needed.
4. Re-run the smallest failing test immediately.

## 4. Docs And Code Disagree

Use this rule:

- code + tests beat docs

Then:

1. verify current behavior by test or example
2. update only the affected docs
3. do not rewrite large docs during a small task

## 5. Scope Starts Expanding

Stop if any change seems to require:

- new authority surfaces
- planner semantics changes
- policy changes
- runtime execution model changes

Then:

1. revert to the last good mental checkpoint
2. note the blocker
3. hand off instead of pushing through

## 6. Unsure About Principles

Read these files in order:

1. `docs/PRINCIPLE_BASELINE_2026-04-16.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `README.md`

## 7. Mandatory Self-Check Before Finalizing

Answer these:

1. Did I change only allowed files?
2. Did I keep execution authority out of the model?
3. Did I keep policy and approval boundaries unchanged?
4. Did focused tests pass?
5. Did full tests pass?

If any answer is no, do not finalize.
