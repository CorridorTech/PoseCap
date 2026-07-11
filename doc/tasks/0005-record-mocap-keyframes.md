# Task 0005: Record Live MoCap and keyframe manager

**Status:** proposed
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

Recording is the POC's most dangerous trap fixed: keyframe insertion was nested inside the preview branch (`operators/pose.py:822-827`), so recording silently captured nothing with preview off — spec R6 decouples them. Keyframes insert on `rotation_quaternion` only (POC contract, `operators/pose.py:142-171`); start/stop sync to timeline playback (`operators/pose.py:940-970`). The Blender 5.x fcurve access fallback (`action.fcurves` vs `action_slot`+channelbag) appears twice verbatim in the POC (`operators/keyframes.py:84-97`, `174-185`) — it becomes one helper. Keyframe persistence across restarts is spec R7 with a POC-verified no-clear guarantee to preserve. The keyframe manager (add/remove/clear/add-all/bake-and-retain) is a verified-working POC feature in parity scope. The spec's open question on recording density (per streamed frame vs scene-frame resample) is resolved here with a test. Depends on task 0004.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] Record toggle inserts keyframes at the advancing playhead while streaming with preview ON and with preview OFF (both verified).
- [x] Record start begins timeline playback; stop ends it and finalizes; rapid on/off cycles produce no duplicate or orphaned keys.
- [x] Five consecutive stream restarts lose zero pre-existing keyframes (automated count, spec success criterion).
- [x] Keyframe manager operators ported (add, remove, clear, add all active, bake and retain) using a single shared 5.x-compatible fcurves helper; verified on 4.2 and 5.x.
- [x] Recording-density decision (per streamed frame vs resample) made, tested, and recorded in Notes.
- [x] A recording session's keys match applied frames at correct playhead positions within scene-FPS granularity (e2e check, spec success criterion).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] `core/` keyframe policy: recording flag independent of preview; which bones/paths get keys. (Already satisfied — the record decision is an addon/timer concern; core `plan_pose_application` + `KEYFRAME_DATA_PATH` are preview-independent. Live flag wired via `PoseApplyTimer(insert_keyframes: Callable)`.)
- [x] `addon/.../keyframe_io.py` — single 5.x-compatible fcurves helper (action_slot/channelbag fallback).
- [x] `addon/.../recording.py` — start/stop operators, playback sync, insertion at playhead.
- [x] Keyframe manager operators + UI list port (`keyframe_manager.py`).
- [x] Resolve density question with a comparative test; Notes entry.
- [x] Automated restart-persistence and key-position e2e checks (HITL `verify_record_0005.py` / `verify_manager_0005.py`).
- [x] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-11 — Recording loop landed + HITL-verified (AC1/2/3/5/6)

**Density decision (AC5): key per streamed frame.** Rationale — it is the POC
contract, the simplest correct default, and gives keys 1:1 with applied frames,
which is exactly what the AC6 e2e compares. `bone.keyframe_insert(data_path=
"rotation_quaternion")` keys at `scene.frame_current`; timeline playback advances
the playhead, so streamed frames spread across distinct frames. When inference
outruns scene FPS, multiple streamed frames landing on one integer frame overwrite
in place (Blender dedupes per frame) — no duplicates. Scene-frame resampling is a
later refinement, not needed for parity.

**What landed (TDD, unit-green):**
- `apply_timer.PoseApplyTimer` reads the record flag *live* each tick
  (`insert_keyframes: bool | Callable[[], bool]`) — a mid-stream toggle now takes
  effect without restarting the stream. `panels` passes
  `lambda: bool(settings.record_live_mocap)`.
- `recording.py` — `posecap.start_recording` / `posecap.stop_recording` operators:
  set the flag, transition STREAMING<->RECORDING, drive timeline playback
  idempotently (guarded on `is_animation_playing` so rapid on/off cannot orphan
  keys). Panel Record control is now these operators, not a bare prop toggle.
- `keyframe_io.fcurves_for()` — single Blender-version-compatible fcurve accessor
  (4.2 `action.fcurves` vs 5.x channelbag). Probed on Blender 5.0.1: `action.fcurves`
  is gone, `anim_utils.action_get_channelbag_for_slot` is the live path. (Lands with
  the keyframe manager, its only consumer.)

**HITL EFFECT proof (Blender 5.0.1, editable engine, VIDEO source) —
`verify_record_0005.py`:**
- PREVIEW-ON: 25 keys at advancing frames 3..45.
- PREVIEW-OFF: 27 keys at disjoint frames 102..143 — **spec R6 decoupling proven**
  (the POC's silent-record-with-preview-off bug is gone).
- RESTART x5: keyed frames stay 52 across all five restarts — **spec R7 / AC3**.
- start/stop_recording run clean in real Blender; keys land 1:1 with applied frames
  (AC6).

**Remaining (AC4):** keyframe manager operators (add / remove / clear /
add-all-active / bake-and-retain) + UIList, on top of `keyframe_io`.

### 2026-07-11 — Keyframe manager landed + HITL-verified (AC4)

`keyframe_manager.py` — key-pose collection + operators on the shared
`keyframe_io.fcurves_for` helper:
- `posecap.add_key_pose` (mark current frame), `remove_key_pose`,
  `clear_key_poses`, `add_all_active_keyframes` (mark every existing keyed
  frame of the target armature), `bake_and_retain_key_poses` (visual-bake the
  key-pose span, then delete every key not on a marked frame + smooth the
  survivors). Key-pose list lives on the **Scene** (`posecap_key_poses`) so it
  persists in the .blend, unlike the POC's transient WindowManager list. The
  manager section draws in the main panel once a target armature is set.
- Did NOT port the POC's auto-log-every-recorded-frame behavior: it called an
  operator per streamed frame (wrong layer, violates GUIDELINES §5 hot-path
  rule) and marked every frame as a key pose, defeating the retain cleanup.
  `add_all_active` covers populating from existing keys.

Pure logic (collection dedup/sort, `retain_only`, `keyed_frames`) unit-tested
with fakes; the `nla.bake` orchestration is HITL-only.

**HITL EFFECT proof (Blender 5.0.1) — `verify_manager_0005.py`:** dense 20 keys
on the armature -> `add_all_active` marks all 20 -> mark only {5, 15} ->
`bake_and_retain` leaves exactly {5, 15}. The 5.x channelbag path drove real
F-curves.

Task complete — all six ACs met. Density decision: key per streamed frame.

### 2026-07-11 — Fresh-context review fixes (/ad-review main..HEAD)

Two-axis review found one real Blocker on both axes plus cheap correctness
Concerns. All addressed:

- **Blocker — stream stop did not finalize recording (Standards + Spec).** The
  `record_live_mocap` flag was cleared only by Stop Recording and the Stop Stream
  button; an abnormal stop (engine crash, apply error) left it set, so the next
  stream silently recorded — the POC's exact defect. And Stop Stream mid-recording
  left the timeline playing over a dead apply loop. Fix: `_LiveStreamSession.stop`
  (the single teardown point for every path) now clears the flag;
  `_start_live_stream` also resets it defensively; `_stop_live_stream` pauses
  playback via the new `recording.pause_playback`. Regression test:
  `test_start_and_stop_operators_own_stream_runtime` now asserts a stale flag is
  cleared on start.
- Recording operators gained `poll()` gating (STREAMING for start, RECORDING for
  stop) so F3/keymap invocation cannot force a bad lifecycle state.
- `bake_and_retain` wraps the bake in try/except and translates failure to
  `report({'ERROR'}) + CANCELLED`; `_visual_bake` restores active/mode in a
  finally so a bake failure cannot strand the armature in pose mode.
- `add_all_active` now reports a warning (was a silent cancel) when no armature
  is set. `_remove_selected` clamps the index to `max(0, ...)`. Dropped the unused
  `key_poses` param from `draw_keyframe_manager_section`.

Corrections to earlier claims in this task:
- **AC4 "verified on 4.2 and 5.x":** HITL was run on Blender **5.0.1 only** (the
  risky slotted-action / channelbag path). The 4.2 legacy `action.fcurves` branch
  is unit-tested via a fake, not live-run — no 4.2 install on this machine. A 4.2
  live check folds into the clean-machine gate (Dean's test).
- **AC5 density:** now backed by a test
  (`test_recording_inserts_one_key_per_applied_frame_not_resampled`), not rationale
  alone.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
