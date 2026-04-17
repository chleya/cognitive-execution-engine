# Handoff Prompt

Use this exact protocol for the next task. Do not skip steps.

## Protocol

1. Read `NEXT_AGENT_START_HERE.md`.
2. Read `handoff_state.json`.
3. Read `TASK_CHECKLIST.md`.
4. Restate:
   - the single current goal
   - execution mode
   - primary files
   - allowed files
   - forbidden scope
   - validation commands
5. Follow the stage gates in order from `handoff_state.json`.
6. Inspect only the files needed for the current goal.
7. Make the smallest possible change.
8. Run focused checks first.
9. If focused checks pass, run the example if required.
10. Run full tests last.
11. If something fails twice, stop and follow `RECOVERY_PLAYBOOK.md`.

## Required Output Format Before Editing

Write this exact structure in your own words:

- Goal:
- Execution mode:
- Primary files:
- Allowed files:
- Forbidden scope:
- Validation:

## Required Output Format Before Final Answer

Write this exact structure in your own words:

- Changed:
- Verified:
- Risks:

## Hard Rules

- Do not broaden the task.
- Treat `handoff_state.json` as the machine-readable source of truth if any handoff docs disagree.
- Do not skip or reorder stage gates.
- Do not expand beyond `primary_files` unless a focused failing check proves it is required.
- Do not change policy semantics unless explicitly told.
- Do not change runtime authority boundaries unless explicitly told.
- Do not treat narration as execution authority.
- Do not trust stale documentation over current tests and code.
