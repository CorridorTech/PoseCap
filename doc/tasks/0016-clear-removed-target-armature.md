# Task 0016: Clear removed target armatures

**Status:** done
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

- [x] A removed target armature is cleared during the next main-panel redraw.
- [x] No character or keyframe controls are drawn for the stale target.
- [x] The regression is covered through the panel drawing flow.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Clear the invalid target at the panel boundary in `addon/posecap_addon/panels.py`.
- [x] Add a removed-StructRNA main-panel test in `tests/addon/test_ui_state.py`.
- [x] Run the addon tests and full quality gate; record the outcome in Notes.

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


The focused regression test passed, the panel suite passed 52 tests, and the
full quality gate passed 389 tests. The ad-review pass reported zero findings.

### 2026-07-13

Production reports against 1.0.3 exposed that the original implementation
cleared and auto-selected the target by writing Scene properties from
`Panel.draw`. Blender rejects ID writes in that context, so importing an FBX
collapsed the panel into its recovery-only UI. The acceptance outcome remains
the same for Blender's real lifecycle — the stale pointer is cleared before the
next redraw — but the mutation now runs from the persistent
`depsgraph_update_post` handler and `Panel.draw` is strictly read-only.

The regression was reproduced in a visible Blender 5.1.2 session with the real
`X Bot.fbx`, then verified from isolated installs on Blender 4.2.22, 5.0.1, and
5.1.2. Coverage now also includes unique/ambiguous/active armature selection,
manual selection preservation, removed RNA reads, removed scene objects,
handler registration cleanup, FBX delete/reimport, and a draw guard that rejects
Scene or preference writes.

### 2026-07-13 — workflow stress follow-up

Issue #40 and a second field report showed that isolated happy-path coverage was
not enough confidence for release. A new Blender E2E workflow now exercises an
empty scene, conversion/start attempts out of order, FBX import before and after
panel draw, target deletion and reimport, manual selection preservation, 30
create/draw/delete cycles, a factory-file reset, and five addon reload cycles.
Every transition asserts that the full versioned panel remains available and
that exactly one PoseCap depsgraph handler is registered.

The same workflow accepts a local `POSECAP_E2E_FBX` without copying it into the
repository. With `X Bot.fbx`, import, auto-selection, and Mixamo conversion pass
on Blender 4.2.22, 5.0.1, and 5.1.2; the licensed FBX remains outside Git. A
visible Blender 5.0.1 run against the current build independently confirmed the
panel remains complete after import and reports conversion probe error `0.0000`.

The stress probe also found two out-of-order gaps beyond the original blank
panel: Start Stream could be invoked from Blender search before character or
body-model setup. The operator now shares the complete setup gate with the UI,
rejects direct/scripted execution defensively, keeps the engine stopped, and
shows the missing setup step as an actionable status.

The adversarial review found that the first E2E oracle proved only the version
header and absence of the recovery screen, not the complete panel it claimed.
The tightened oracle now requires Start, Stop, Character Setup, and the
state-appropriate conversion control or ready message at every transition. Its
first run correctly failed on the converted-character state until both valid
panel states were modeled; the corrected check passes on all three Blender
versions. The final local gate passed 403 default tests, both platform type
checks, import contracts, lint, and format; the complete pre-commit and pre-push
hook suites also passed.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (ad-review reported zero findings)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
