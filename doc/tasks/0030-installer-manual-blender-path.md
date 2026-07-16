# Task 0030: Offer a manual Blender path in the installer

**Status:** proposed
**Created:** 2026-07-16
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:** issue #48

## Context

Issue #48's reporter suggested it directly: when automatic Blender discovery
fails (portable builds, unusual install roots, future store fronts we have
not enumerated), the installer's only answer today is "Install Blender 4.2 or
newer" — even when a perfectly good Blender exists somewhere we did not look.
Steam discovery (PR #51) fixed the largest known gap, but discovery by
enumeration can never be exhaustive. A manual path input is the escape hatch
that keeps every future "installer cannot find my Blender" report solvable by
the user in one step, and it follows the project's CK2P parametrization
principle: simple automatic default, expandable manual override.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] When automatic discovery finds no compatible Blender, the installer
      offers the user a way to provide the path to their `blender.exe`
      instead of failing outright.
- [ ] A provided path is validated the same way discovered ones are (version
      4.2 or newer, executable exists) with an actionable message when it
      does not qualify.
- [ ] The chosen path is honored by install, verify, and uninstall (the same
      shared discovery seam PR #51 introduced), not just by the first step.
- [ ] Automatic discovery remains the default; a user who never needs the
      override never sees extra friction.
- [ ] Regression tests cover the override at the level the installer tests
      already exercise (`tests/test_installer_components.py`).

## Notes

### 2026-07-16 — origin

Suggested by the issue #48 reporter after working around discovery with a
manual `PATH` edit. Recorded during the open-bug triage; not scheduled yet —
priority queue at the time: task 0028 (installer stderr), task 0029 (backend
registration), then this.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
