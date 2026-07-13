# Task 0019: Drive Blender E2E timers publicly

**Status:** proposed
**Created:** 2026-07-13
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The live-stream E2E must prove that Blender consumes a TCP pose frame without
depending on private addon state. The current headless harness reaches the
session created by Start Stream to advance its registered timer because it has
no public event-loop driver; this task replaces that seam with a public path.

## Acceptance Criteria

- [ ] The Blender E2E does not access `panels._ACTIVE_SESSION` or invoke a private timer callback.
- [ ] The E2E still proves Start Stream consumes a TCP JSON frame, applies the converted elbow rotation, and Stop Stream returns to Stopped.
- [ ] The focused Blender E2E and default quality gate pass.

## Plan

- [ ] Establish a public Blender background event-loop or test-driver path in `tests/e2e/test_blender_addon_smoke.py`.
- [ ] Replace the private session access while preserving the TCP loopback assertion.
- [ ] Run the focused Blender E2E and required quality gates.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task


