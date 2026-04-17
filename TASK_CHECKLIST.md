# Task Checklist

## Operating Rule

Only do one unchecked item at a time.

## Current Checklist

- [ ] Read `handoff_state.json`
- [ ] Read `NEXT_AGENT_START_HERE.md`
- [ ] Restate the goal, execution mode, primary files, allowed files, forbidden scope, and validation commands
- [ ] Follow stage gates in the declared order
- [ ] Inspect only files required by the active task
- [ ] Make the smallest possible allowed change
- [ ] Add or update focused tests only if code changed
- [ ] Run focused checks
- [ ] Run full test suite
- [ ] Emit a final handoff report or equivalent verification summary
- [ ] Update visible test-count docs only if the count changed

## Completion Rule

The task is complete only when all are true:

- focused tests pass
- full tests pass
- only allowed files were changed
- no authority boundary changed

## Failure Rule

If two consecutive attempts fail on the same issue:

- stop editing
- read `RECOVERY_PLAYBOOK.md`
- switch to diagnosis mode instead of adding more code
