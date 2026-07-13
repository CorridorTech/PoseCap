# Task 0016: Clear removed target armatures

**Status:** in-progress
**Created:** 2026-07-13
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

Blender can remove an armature while the PoseCap panel remains open. The panel
already avoids a redraw exception, but it should also clear the stale target so
later sections consistently return the user to the setup state.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] A removed target armature is cleared during the next main-panel redraw.
- [ ] No character or keyframe controls are drawn for the stale target.
- [ ] The regression is covered through the panel drawing flow.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] Clear the invalid target at the panel boundary in `addon/posecap_addon/panels.py`.
- [ ] Add a removed-StructRNA main-panel test in `tests/addon/test_ui_state.py`.
- [ ] Run the addon tests and full quality gate; record the outcome in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-13

Fresh-context review of release PR 35 found that graceful detection did not yet
clear the stored pointer. The issue is tracked separately to keep the validated
installer patch focused.

### 2026-07-13

The panel-redraw regression was reproduced with a target object whose Blender
RNA `type` access raises `ReferenceError`. Before the fix, the stale pointer
survived the redraw and the Keyframe Manager was still rendered. The panel now
clears that pointer before continuing its normal auto-selection flow; the new
behavior test and the full quality gate pass.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
