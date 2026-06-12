# Task 0002: Port pose math to pure-numpy core

**Status:** done
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The POC's pose math is proven by 20k+ successful live loads but lives inside bpy operators. ADR-0001 forbids `mathutils` in `core/`, so the math ports to pure numpy. Load-bearing behaviors that must survive the port, with POC source locations: quaternion sign continuity (`make_compatible` equivalent — prevents 360-degree flips between frames, `utils/pose.py:17-29`), zero-before-apply (the "weird fingers" accumulation fix, `operators/pose.py:109-120`), the 180-degree X flip premultiply for PEAR's camera frame (`operators/pose.py:123-140`), per-limb import filters with their implication rules (arms imply wrist+fingers, `operators/pose.py:81-107`), and the order-based bone mapping (joint index i to joint_names[i+1], hands as trailing blocks, `operators/pose.py:142-171`). Depends on task 0001.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] Axis-angle to quaternion conversion in numpy with sign-continuity against the previous frame's quaternion; test feeds a rotation sequence crossing the flip boundary and asserts no sign pop.
- [x] 180-degree X flip premultiply as a pure function; golden cases verify a known POC input/output pair.
- [x] Per-limb filter produces the same bone whitelist as the POC semantics (table-driven tests covering each toggle and the implication rules).
- [x] Bone-order mapping implemented against the contracts pose-frame arrays; property test asserts every frame index maps to exactly one bone name.
- [x] `PoseStream` port (Protocol) and pose-application policy (which bones, zero-before-apply set, keyframe set) defined in `core/` — consumable by the addon adapter without bpy.
- [x] Coverage of `core/` at or above 90%; pyright strict clean; import-linter green (no bpy/torch/socket/mathutils anywhere in core).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] `core/src/posecap_core/rotation.py` — axis-angle/quaternion ops + sign continuity.
- [x] `core/src/posecap_core/orientation.py` — PEAR flip premultiply.
- [x] `core/src/posecap_core/filters.py` — per-limb whitelist logic with implication table.
- [x] `core/src/posecap_core/skeleton.py` — joint-order mapping vs contracts arrays.
- [x] `core/src/posecap_core/ports.py` — `PoseStream` Protocol + apply-policy types (policy landed in `application.py`).
- [x] `tests/core/` — golden, table-driven, and property tests per criterion.
- [x] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-11

Implemented on `feat/task-0002-core-math` (stacked on task 0001's branch). Modules: `rotation.py` (axis-angle/quaternion, Hamilton product, sign compatibility), `orientation.py` (180-degree X premultiply, zero-rotation passthrough per POC guard), `skeleton.py` (55-name SMPL-X order ported verbatim from POC `model_spec.py:13-29`), `filters.py` (implication rules ported from POC `pose.py:88-107`, including the deliberate pelvis-excluded-under-filter semantic), `application.py` (`plan_pose_application` — the bpy adapter executes plans verbatim; `KEYFRAME_DATA_PATH = "rotation_quaternion"`). Coverage 100% (target 90). Gates: pytest 61/61 total, pyright strict 0 errors, import-linter clean. Orientation fix verified against an independent Rodrigues-matrix composition in tests, not just round-trips. Flip-fix default: `apply_orientation_fix=True` (grounding recommendation — always-on for PEAR with escape hatch).

Two-axis review (WORKFLOW §10): 2 Standards Blockers fixed (mutable exported IDENTITY_QUATERNION constant — now write-protected; zero-norm quaternion divided before the guard, NaN risk on the hot path — now raises PoseCapError). Concerns fixed: plan quaternions write-protected (plans double as next frame's previous_quaternions), right-hand slice closed, PoseCapError base added per GUIDELINES §2.2, GUIDELINES TODO token reworded, golden POC pair hard-coded per AC.

Deliberate deviation, recorded: `quaternion_to_axis_angle` canonicalizes to the short-way representation (w >= 0, angle <= pi). The POC's mathutils path emitted the long-way form past 180 degrees — the same rotation in bigger numbers; nothing downstream observes the difference because all consumers convert back through quaternions with sign compatibility. Task closed: 65 tests, core coverage 100%, all gates green.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
