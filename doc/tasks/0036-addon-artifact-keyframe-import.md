# Task 0036: Addon imports the artifact as explicit-frame keyframes

**Status:** proposed
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** [doc/specs/0004-offline-video-batch-animation.md](../specs/0004-offline-video-batch-animation.md)
**Board ref:**

## Context

Second vertical slice of spec 0004: given a completed artifact file, the
addon writes keyframes on the target armature at explicit scene frame
numbers. Demonstrable on its own: import a fixture artifact in
`blender --background` and find keys at the golden frames. This slice is the
structural fix for the field-reported misalignment — the addon's only
keyframe path today inserts at a playhead advancing under `animation_play`
(`recording.py`, `apply_timer.py`); batch import needs a `frame_set(n)`-driven
writer. The source-index-to-scene-frame mapping is a pure function in `core/`
(deterministic in frame index and declared rates, spec R7), tested without
Blender.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Mapping functions in `core/` implement both mappings (spec R7): default
      scale-source-fps-to-scene (time-preserving, Blender BVH-importer
      convention) and 1:1 frame-to-frame; golden mapping tests pin a known
      fps pair for each, verified without Blender.
- [ ] An explicit-frame keyframe writer drives `frame_set(n)` — never playback
      (spec R6) — with Blender 4.2 LTS and 5.x action-slot compatibility.
- [ ] No-person rows produce no keyframe (spec R8); an all-no-person artifact
      reports zero keyframes written as an explicit outcome, not silence.
- [ ] Import inserts only its own keys; pre-existing keyframes are intact
      after import, verified by an automated count before/after (spec R9).
- [ ] Re-import of the same artifact lands identical keyframe placement; the
      mapping applies at import time from the artifact's recorded source fps,
      so a scene-fps change plus re-import adapts without reprocessing
      (spec R10, edge case).
- [ ] Schema-invalid or truncated artifacts are rejected with an actionable
      error before any key lands; missing target armature errors cleanly
      (spec R11 import side).
- [ ] Imported keys are ordinary keyframes: the existing keyframe manager
      operates on them unchanged (spec R14), covered by a test.
- [ ] An `e2e`-tagged `blender --background` check imports a fixture artifact
      onto the SMPL-X armature and finds keys at the expected scene frames.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] TDD the mapping functions in `core/` (golden fixtures first, both
      mappings, offset handling).
- [ ] TDD the import policy in `core/` (row filtering, no-person skip,
      keyframe-safety contract) behind a port; `bpy` adapter stays thin.
- [ ] Implement the `frame_set`-driven writer in the addon with the 4.2/5.x
      action-slot branch (in-repo resolver: `addon/posecap_addon/keyframe_io.py`;
      POC reference `operators/keyframes.py:84-97` lives in the read-only
      external POC repo, not this tree).
- [ ] Wire the advanced-section re-import operator (artifact file picker).
- [ ] e2e check via `blender --background --python`, plus the
      pre-existing-keyframe count test.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — task created

Split from spec 0004 at acceptance. Depends on task 0035's artifact format
(contracts golden fixture is the interface between the two slices — this
task can start from the pinned fixture as soon as the format lands, without
waiting for the full engine verb).

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
