# Spec 0001: Live webcam pose streaming

**Status:** accepted
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro

## Context

Live streaming is the product's core value: an animator points a webcam at a performer and the SMPL-X armature in the Blender viewport follows in real time. It is the feature the POC most thoroughly proved (10.6 minutes error-free, 20,329 pose loads in the final session) and the one whose POC defects hurt most in production: every pose loaded twice, 6,670 crashes when the armature was deleted mid-stream, recording silently dead when the preview toggle was off, and teardown by window title. This spec is the first vertical slice of the rewrite — it exercises every layer (contracts, core, addon, engine) and validates ADR-0001 through ADR-0004 in one shippable outcome. Without it, nothing else in the MVP matters.

Inherits from [PRD](../product/PRD.md): target user (Blender animators; Corridor artists founding), the 30 FPS / sub-100 ms success metric, and the licensing constraints. Flow diagrams: [doc/workflows.md](../workflows.md) (live streaming sequence, stream lifecycle state machine).

## User Scenarios

- **Scenario 1: Start streaming**
  - Given the engine environment is installed, an SMPL-X armature is spawned, and a webcam is connected
  - When the user selects a camera device and clicks Start Stream
  - Then the engine process launches, the UI passes through Starting into Streaming, and the armature follows the performer in the viewport — without modifying any existing keyframes

- **Scenario 2: Record Live MoCap**
  - Given an active stream
  - When the user toggles Record Live MoCap
  - Then timeline playback starts and pose keyframes are inserted at the advancing playhead; toggling off stops recording and the inserted keyframes remain — regardless of any preview setting

- **Scenario 3: Stop streaming**
  - Given an active stream (recording or not)
  - When the user clicks Stop Stream
  - Then any active recording finalizes, the engine process terminates by handle, and the UI returns to Stopped

- **Scenario 4: Restart preserves keyframes**
  - Given keyframes recorded in a previous stream session
  - When the user starts a new stream
  - Then all previously recorded keyframes are intact

- **Scenario 5: Armature disappears mid-stream**
  - Given an active stream
  - When the target armature is deleted or replaced
  - Then the stream enters a visible warning state without error spam, and selecting a valid target resumes pose application without restarting Blender

- **Scenario 6: Engine dies mid-stream**
  - Given an active stream
  - When the engine process crashes or is killed externally
  - Then the UI reaches Stopped with a reported reason within 5 seconds

- **Scenario 7: Blender exits during stream**
  - Given an active stream
  - When Blender quits or is killed
  - Then the engine process self-terminates within 5 seconds (no orphans)

## Requirements

### Functional

- R1: User can select the capture device from a dropdown enumerated by the engine bridge (which owns the environment that can enumerate; fixes the POC's broken in-Blender enumeration).
- R2: Addon spawns the engine by process handle and connects to its TCP pose stream with bounded retry; connect timeout lands in Stopped with a reported reason.
- R3: Poses travel as newline-delimited JSON frames conforming to the `contracts/` schema (ADR-0003), validated on decode.
- R4: A background client thread feeds a latest-wins slot; a main-thread timer consumes it. No `bpy` access off the main thread.
- R5: Pose application supports per-limb import filters (arms/hands/fingers/legs, left/right) and the PEAR orientation fix, applied as quaternions to the SMPL-X armature. The orientation fix folds in a user-set Camera Pitch (degrees; the base 180° flip plus the camera tilt share the camera X axis) so a non-level capture camera does not leave the character leaning.
- R6: Record Live MoCap inserts keyframes at the advancing playhead while active, independent of any preview toggle; start begins timeline playback, stop ends it and finalizes.
- R7: No code path in stream start, restart, or apply clears or overwrites animation data outside an active recording's inserts.
- R8: The armature reference is validated every applied frame; an invalid reference transitions to a warning state instead of raising.
- R9: Stop terminates the engine by process handle; the engine watches the Blender PID and self-terminates when it disappears.
- R10: The UI reflects the lifecycle states Stopped, Starting, Streaming, Recording, Reconnecting (state machine in doc/workflows.md) — never a stuck or ambiguous state.
- R11: Frames indicating "no person detected" are explicit in the wire format; the addon holds the last applied pose and shows the idle condition.
- R12: Both processes log frame-time instrumentation (engine inference FPS, addon apply time) at INFO on an interval, to rotating bounded logs.

### Non-functional

- Sustained 30 FPS pose application with p95 capture-to-viewport latency under 100 ms on an RTX 30-series-or-newer GPU (PRD metric).
- No per-frame allocations, disk I/O, or above-DEBUG logging on the hot path (GUIDELINES §5).
- All pose-mapping and keyframe-policy logic lives in `core/`, unit-tested without Blender or GPU; transport sits behind the `PoseStream` port (ADR-0001, ADR-0002).
- Windows 10/11, Blender 4.2 LTS minimum with 5.x action-slot compatibility in keyframe code.

## Success Criteria

Definitional. Per-criterion progress tracking lives in per-Spec tasks, not here.

- A 10-minute continuous stream completes with zero errors in either process log and sustained ≥30 FPS, measured from the R12 instrumentation (POC baseline: 10.6 min clean).
- p95 capture-to-viewport latency under 100 ms across a 10-minute session, measured from frame timestamps stamped at capture and at apply.
- Five consecutive stream restarts lose zero pre-existing keyframes, verified by an automated count before/after.
- Deleting the armature mid-stream produces no unhandled exception and at most one warning-state transition; recovery needs no Blender restart.
- A recording session inserts keyframes for every applied frame at correct playhead positions within scene-FPS granularity, verified by an e2e check.
- Golden-fixture contract tests pin the pose-frame schema; `core/` logic tests pass with no Blender or GPU present.
- After Blender exits, no engine process remains within 5 seconds, verified by process listing in the e2e check.

## Edge Cases

- Webcam absent, disconnected mid-stream, or claimed by another app — engine reports a typed error; UI shows an actionable message, not a stack trace.
- No person in frame (R11) — explicit idle, last pose held; multiple people — single most-confident detection (POC contract).
- TCP port already occupied at engine start — covered by Open Questions (port negotiation).
- Start Stream clicked while already streaming — rejected; UI state unchanged.
- CUDA unavailable or GPU OOM at model load — fails in Starting with an actionable message; never crashes mid-stream from startup causes.
- Inference slower than 30 FPS (weak GPU, large scene) — apply at available rate; latest-wins drops stale frames; no backlog.
- .blend file loaded (load_post) during an active stream — stream stops safely first.
- Recording toggled rapidly on/off — each cycle finalizes correctly; no duplicate or orphaned keyframes.

## Out of Scope

- Photo upload, batch processing, folder watcher (separate specs; Next tier for unproven paths per PRD).
- Arduino hardware input — dropped from the product entirely at product review; no separate spec will exist (supersession note under Open Questions).
- Face, jaw, expression application; root translation from the AI engine (world position is a Later roadmap problem — software camera tracking).
- Multi-camera estimation, non-PEAR backends, Linux support.
- Legacy POC `.pkl` import (pose-import spec territory; converter is a PRD Next candidate).

## Open Questions

- TCP port strategy: fixed default with handshake fallback, OS-assigned port reported through a startup handshake file, or scan-and-bind? Small enough for a spec-time decision before implementation; may warrant a short ADR if it shapes the contracts schema.
- Recording density when inference rate diverges from scene FPS: insert per streamed frame or resample to scene frames? Needs a decision with a test during implementation.
- Cross-process latency measurement: clock source for capture-vs-apply timestamps on one machine (wall clock both sides vs handshake-established offset). Instrumentation design detail; resolve in the implementing task.

  Update at product review: the Arduino hardware input was dropped from the product entirely (Dean's call — too specific to his setup). The Out of Scope line about a separate Arduino spec is superseded: no such spec will exist, and the "hardware rig owns world transform" note no longer applies — world position is now a Later roadmap problem (candidate: camera tracking). This spec's own requirements are unaffected; poses were always pelvis-locked here.

## Related

- ADRs: [0001](../adr/0001-adopt-hexagonal-architecture.md), [0002](../adr/0002-tcp-json-stream-live-pose.md), [0003](../adr/0003-json-wire-format-ban-pickle.md), [0004](../adr/0004-uv-workspace-vendor-shared-packages.md), [0005](../adr/0005-pear-external-pinned-never-vendored.md), [0007](../adr/0007-pear-windows-runtime-matrix.md)
- Tasks: [0001 scaffold + contracts](../tasks/0001-scaffold-workspace-and-contracts.md), [0002 core pose math](../tasks/0002-core-pose-math-and-ports.md), [0003 engine bridge](../tasks/0003-engine-bridge-tcp-pear.md), [0004 addon client](../tasks/0004-addon-live-stream-client.md), [0005 record + keyframes](../tasks/0005-record-mocap-keyframes.md), [0006 installer + e2e](../tasks/0006-installer-and-e2e-verification.md), [0007 PEAR runtime matrix](../tasks/0007-pear-runtime-windows-matrix.md)
- Depends on: [PRD](../product/PRD.md) (accepted scope pending), [poc-verification.md](../reference/poc-verification.md) (evidence baseline)
