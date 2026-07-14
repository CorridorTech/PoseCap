# Task `0025`: Establish PEAR hand retargeting

**Status:** done
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

PEAR emits SMPL-X hand-pose arrays, but PoseCap's character conversion currently
renames only body joints. A converted Mixamo character therefore cannot receive
finger rotations even though the stream and core application plan contain them.
The gap makes the high-fidelity backend's advertised expressive capture impossible
to verify in the Blender workflow used by the tutorial.

## Acceptance Criteria

- [x] A complete Mixamo skeleton converts its thirty finger bones to PoseCap's
  canonical SMPL-X names without changing the existing body conversion.
- [x] A Mixamo skeleton without a complete pair of hands remains convertible for
  body capture and does not receive a partial, misleading finger mapping.
- [x] A distinct left and right PEAR hand pose crosses the JSON stream and changes
  the corresponding converted finger rotations in a real Blender process.
- [x] The full local quality gate and a fresh-context review pass after the Blender
  acceptance has been observed.

## Plan

- [x] Add the Red retarget-domain behavior for complete and incomplete Mixamo hands.
- [x] Extend the detected Mixamo mapping only when all expected hand bones exist.
- [x] Extend the existing Blender smoke flow with distinct finger rotations through
  TCP, timer, and the converted target armature.
- [x] Run the focused tests, then the full local quality gate and `ad-review`; record
  the observed Blender result in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14

Grounding found that `engine/src/posecap_engine/pear_adapter.py` serializes both
fifteen-joint hand arrays and `core/src/posecap_core/application.py` plans their
rotations, while `core/src/posecap_core/retarget.py` deliberately stops at the
twenty-two body joints. `BpyArmaturePoseWriter` safely ignores a missing pose bone,
which makes the gap silent in a converted Mixamo character. The task therefore
extends the target mapping and its Blender acceptance; face, jaw, and expression
application remain outside this task's scope.

### 2026-07-14

The first domain test failed as expected because automatic Mixamo detection exposed
only body joints. The minimal change derives the canonical thirty hand names from
the shared skeleton table and adds them only when every matching Mixamo source bone
exists. A partial hand intentionally remains body-only.

The PEAR adapter test now proves that two distinct hand rotation matrices become the
correct left and right Rodrigues vectors in the common payload. The Blender 5.0.1
smoke then built a complete Mixamo-style rig, FBX-roundtripped it, selected automatic
conversion, sent distinct hand rotations through NDJSON, and observed the expected
quaternions on `left_index1` and `right_thumb3`. The complete local gate passed:
486 tests passed, three expected skips, plus both Blender E2Es.

The installed PEAR doctor confirms the RTX 3080 runtime, CUDA, external checkout,
and PEAR weight are available. It also reports the official SMPL/SMPL-X/FLAME assets
missing from the current local installation, so live model inference is not claimed
by this task. Those assets must be reinstalled through the official user-owned flow;
the POC copies remain out of bounds.

### 2026-07-14

After the final formatting pass, the local gate was observed green: Ruff lint and
format checks, Windows and Linux Pyright, import-linter, and the full pytest suite
(`486 passed, 3 skipped, 10 deselected`). Blender 5.0.1 also reran the focused smoke
flow (`2 passed`), proving the rotations after a real extension registration,
conversion, socket stream, and timer application. `git diff --check` was clean.

Fresh-context `ad-review` used the complete review packet at
`.agentic/reviews/20260714T172829-working-tree-task-0025.md`: six integral diff
headers, all binding standards, and the complete task/spec/PRD sources. It reported
zero standards findings and zero spec findings. No TODO or FIXME was added.

### 2026-07-14

Closure verification reran the full local gate after the task record was finalized:
Ruff lint and format, both Pyright platform targets, import-linter, and `git diff
--check` passed. `uv run pytest` observed `486 passed, 3 skipped, 10 deselected in
25.14s`; the real Blender 5.0.1 E2E observed `2 passed in 7.63s`.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW section 10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task



