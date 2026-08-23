# Task `0043`: `Implement binding-map pose compensation`

**Status:** done
**Created:** 2026-08-22
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0005-non-destructive-character-binding.md
**Board ref:**

## Context

The non-destructive binding must drive a character through its original bone
names and local axes. This task delivers the pure, testable part of that
promise: an immutable binding map that compensates streamed SMPL-X rotations
and rewrites a pose-application plan without accessing Blender or changing an
armature. It is the first vertical slice of task 0034 and ADR-0014.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] A pure `core/` binding map pairs each supported SMPL-X joint with its
      target armature bone name and immutable compensation quaternion.
- [x] Applying the map rewrites planned rotations to the original target names,
      composes compensation in the documented quaternion order, and leaves an
      unbound plan unchanged.
- [x] Clear-bone and previous-quaternion bookkeeping use the mapped target
      names, so the adapter never requires the character's bones to be renamed.
- [x] Unit tests cover identity, non-identity, missing-map, filtering, and
      immutability behavior without Blender or a GPU.

## Plan

Concrete sequential steps. Reference file paths where applicable.

- [x] Add the first failing behavior test in `tests/core/test_binding.py`.
- [x] Implement the binding-map value objects and plan transformation in
      `core/src/posecap_core/`.
- [x] Thread the optional map through `plan_pose_application` and preserve the
      existing unbound path.
- [x] Run focused core tests and the required quality gates; append measured
      results to Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-08-22 — completed pure binding-map slice

Added immutable `BoundBone` and `PoseBinding` values in `core`, plus a pure
plan rewrite that sends rotations and reset bookkeeping to each rig's original
bone names. The transform is `neutral ⊗ compensation ⊗ source ⊗
compensation⁻¹`; the inverse is applied to writer history before sign
continuity, so the existing live writer can retain target-named state.

The tests cover identity and non-identity compensation, omission of unmapped
joints, filtering, target-named previous-frame continuity, and defensive
immutability. They do not invoke Blender, mutate an armature, or require a
GPU. The Blender setup/persistence/UI slice remains Task 0034.

Measured verification: focused core suite 18 passed; full suite 611 passed,
38 skipped, 11 deselected; ruff, format, Windows/Linux pyright, import-linter,
and `git diff --check` passed. Review: `.agentic/reviews/20260822T-binding-map-pose-compensation.md`.

### 2026-08-22 — reopened: rest-delta proof still required

Further grounding against Blender's `Bone.convert_local_to_pose` contract and
Rigify's rest-delta conversion showed that a complete binding must account for
the source and target rest matrices together with the parent pose chain. The
current per-bone quaternion map proves the runtime seam, mapped names, reset
pose, and history conversion, but has not proven equivalence for a non-T target
under that parent-relative matrix model. The task is reopened until a Blender
golden fixture establishes the calculation; the parent task remains the source
of the end-to-end acceptance criteria.

### 2026-08-22 — rest-delta compensation proven in Blender

`spikes/0001-rest-delta-pose-binding/` ran headlessly on official Blender
5.2.0 LTS with a generated two-bone source and target chain whose rest axes
are deliberately different. The cached compensation is the source and target
**accumulated** rest-orientation delta, `target_rest⁻¹ ⊗ source_rest`; the
live map applies it as `compensation ⊗ source ⊗ compensation⁻¹`.

The fixture measured a maximum orientation error of `1.79e-7` for pelvis and
child, versus `0.626`/`0.635` for direct quaternion copying. Changing only the
parent rotation left the compensated child rotation unchanged (`0.0`
variance). A connected child has a `0.582` positional difference because
Blender preserves its chain head; position is intentionally outside the
pelvis-locked pose contract.

Added `compensation_from_rest_orientations` to `core`. The Blender boundary
must pass accumulated orientations expressed in the same frame, including the
target armature object's rotation; it remains responsible for reading Blender
matrices. Focused binding tests: 7 passed. Full local gate: ruff and format,
Windows/Linux pyright, import-linter, and pytest (614 passed, 38 skipped, 11
deselected) passed. The end-to-end binding setup, persistence, and UI remain
in parent task 0034.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task

### 2026-08-22 — task closed

The pure binding-map vertical slice is complete and reviewed. The follow-up
review records the Blender rest-delta evidence and the pure construction API;
the parent task owns all remaining Blender setup, persistence, and end-to-end
character-family work.
