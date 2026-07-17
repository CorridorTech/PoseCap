# Spec 0004: Offline video batch animation

**Status:** draft
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro

## Context

Field report from Dean (task 0031): streaming a pre-recorded video through the
live path (virtual webcam into the realtime engine) and recording keyframes
produces framerate problems — dropped frames under load and keyframes
misaligned with the Blender timeline. The mismatch is structural, not tunable:
the live pipeline is wall-clock paced with a latest-wins contract (spec 0001,
[ADR-0002](../adr/0002-tcp-json-stream-live-pose.md)) that tolerates duplicates
and gaps, while a finite video wants the opposite contract — every source frame
exactly once, in order, keyed by frame index, with no wall-clock anywhere.
Today `VideoFileSource` exists in the engine for test fixtures only (its
stream ends at EOF; looping is an opt-in `--source-loop` flag);
video-to-animation has no supported path.

Comparable tools (Rokoko Video, DeepMotion, Plask) converge on
process-video-then-import-animation, and the friction they all share is file
juggling between an external tool and Blender. PoseCap already lives inside
Blender, so this feature is one in-panel flow: pick a video, process with
progress feedback, keyframes land on the armature. The intermediate
frame-indexed artifact exists (re-import without reprocessing, support
diagnostics) but the happy path never asks the user to touch it.

Inherits from [PRD](../product/PRD.md): target user (Blender animators,
non-technical — GUI only, no user-facing CLI), keyframe-safety expectations,
and the Pose Backend amendment (any installed backend, per
[ADR-0010](../adr/0010-discover-isolated-pose-backends.md)). The transport
decision — offline batch artifact instead of repairing live-path pacing — is
recorded in [ADR-0013](../adr/0013-batch-video-frame-indexed-artifact.md).

## User Scenarios

- **Scenario 1: Process a video into timeline animation**
  - Given a Pose Backend is installed, an SMPL-X armature is spawned, and the
    user has a video file
  - When the user picks the video in the PoseCap panel and starts processing
  - Then the engine processes every source frame with visible progress, and on
    completion keyframes land on the armature aligned to the scene timeline
    framerate — without modifying any existing keyframes

- **Scenario 2: Source framerate differs from scene framerate**
  - Given a 24 fps video and a 30 fps Blender scene
  - When the user processes the video with the default mapping
  - Then the imported animation preserves real-time duration (a 10-second clip
    spans 10 seconds of timeline), with keyframe placement a deterministic
    function of source frame index — never of processing speed

- **Scenario 3: Frame-to-frame mapping (advanced)**
  - Given the same video and scene
  - When the user selects the 1:1 mapping in the advanced options
  - Then source frame N lands on scene frame N+offset, one keyframe per source
    frame, and the clip plays back at scene rate

- **Scenario 4: Re-import without reprocessing**
  - Given a completed processing run whose artifact file exists
  - When the user imports that artifact from the advanced section
  - Then keyframes land identically to a fresh import of the same artifact,
    with no engine launch and no inference

- **Scenario 5: Processing fails**
  - Given an unreadable, corrupt, or unsupported video file
  - When the user starts processing
  - Then the job reports failed with an actionable message in the panel, no
    keyframes are written, and no engine process remains

- **Scenario 6: Cancel mid-processing**
  - Given a processing run in progress
  - When the user cancels
  - Then the engine process terminates by handle within 5 seconds and no
    keyframes are written

- **Scenario 7: Nobody in frame for a stretch of the video**
  - Given a video where the performer leaves frame for a segment
  - When the user processes and imports it
  - Then the no-person segment produces explicit rows in the artifact and no
    keyframes on import; detection segments before and after land at their
    correct scene frames

## Requirements

### Functional

- R1: User can pick a video file, target armature, and installed Pose Backend
  in the PoseCap panel and start offline processing — the entire flow is GUI;
  no user-facing CLI, script, or manual file handling (PRD constraint).
- R2: The video file is validated (extension and size) before the engine
  touches it, extending the GUIDELINES §12 user-dropped-file boundary to video
  input (§12 lists image files today; the same pattern applies).
- R3: Processing runs every source frame through the selected backend exactly
  once, in source order, with no wall-clock pacing; each output row is keyed
  by 0-based source frame index.
- R4: The output artifact is a frame-indexed file of schema-validated
  wire-format pose payloads (defined in `contracts/`, JSON-based per ADR-0003)
  with a header recording source video path, declared source framerate, total
  frame count, backend identifier, and protocol version.
- R5: Job progress travels through the `JobStatus` document (`contracts/job.py`:
  queued/running/done/failed, atomic replace); the addon surfaces progress and
  terminal states without blocking the Blender UI.
- R6: Import writes keyframes at explicit scene frame numbers (`frame_set`-
  driven), never at a playhead advancing under playback — the structural fix
  for the live-recording misalignment this feature answers.
- R7: Source-index-to-scene-frame mapping is a deterministic function of frame
  index, declared source framerate, and scene framerate. Default: scale source
  fps to scene fps (time-preserving, Blender BVH-importer convention).
  Advanced option: 1:1 frame-to-frame.
- R8: Frames with no person detected are explicit rows in the artifact and
  produce no keyframe on import.
- R9: Import inserts only its own keyframes; no code path clears or overwrites
  animation data outside the keys it writes.
- R10: A completed artifact can be re-imported from the advanced section
  without reprocessing; the happy path never requires the user to locate or
  touch the artifact file.
- R11: Failures surface as typed, actionable panel messages backed by a
  `failed` JobStatus with reason; no raw traceback reaches the user.
- R12: The live streaming path (spec 0001 contract) is unchanged: batch adds a
  file-writer sink beside the TCP sink, reusing the existing exactly-once
  frame-source generators; existing live-path tests stay green.
- R13: The user can cancel a running job; the engine terminates by process
  handle and no keyframes land from a cancelled job.
- R14: Imported keyframes are ordinary keyframes — the existing keyframe
  manager tooling operates on them unchanged.
- R15: The engine logs batch processing rate at INFO on an interval to the
  existing bounded logs; the JobStatus progress fraction advances monotonically
  with processed frames.

### Non-functional

- Deterministic placement: artifact frame indices and imported keyframe
  positions are identical across runs and machines for the same inputs;
  processing speed and hardware never change where a key lands (pose values
  themselves are model output — accuracy tolerance is eval-tier territory,
  out of this spec).
- Streaming decode: memory stays bounded regardless of video length; the video
  is never loaded whole into RAM.
- Blender stays responsive during processing (background job + timer polling,
  matching the live path's no-bpy-off-main-thread rule).
- Mapping and import-policy logic lives in `core/`, unit-tested without
  Blender or GPU; the file writer is a port in `core/` with adapters at the
  edges and the wire format in `contracts/` (ADR-0001 dependency rule).
- Windows, Blender 4.2 LTS minimum with 5.x action-slot compatibility in the
  explicit-frame keyframe writer.
- No realtime latency budget applies; GUIDELINES §5 hot-path rules bind the
  live path, not this batch path.

## Success Criteria

Definitional. Per-criterion progress tracking lives in per-Spec tasks, not here.

- Processing a pinned fixture video (240 frames) yields an artifact with
  exactly 240 rows, frame indices 0..239 strictly increasing, verified by a
  contract test.
- Golden mapping tests pin both mappings: a known source-fps/scene-fps pair
  produces the golden scene-frame list for scale-to-scene, and 1:1 produces
  N+offset; both verified without Blender.
- Two consecutive processing runs on the same fixture produce identical
  frame-index sequences and identical keyframe placement.
- An e2e check (`blender --background`) imports a fixture artifact and finds
  keyframes on the armature at the expected scene frames, and pre-existing
  keyframes intact.
- The full existing live-path test suite passes unchanged with the batch
  feature merged.
- An integration test observes JobStatus transitioning queued → running → done
  with monotonically increasing progress; a corrupt-input fixture lands failed
  with a non-empty message and no artifact rows.
- Cancelling a running job leaves no engine process within 5 seconds and no
  keyframes on the armature, verified by an integration test.

## Edge Cases

- Unreadable, corrupt, or unsupported-codec file — typed failure before or
  during decode; actionable message; no partial import.
- Video decodes to zero frames — failed with an explicit "no frames decoded"
  reason, not an empty done.
- No person detected in the entire video — processing completes; import
  reports zero keyframes written as an explicit outcome, not silence.
- Variable-frame-rate video — declared container rate drives the mapping;
  behavior pinned by a fixture during implementation (see Open Questions).
- Very long video — progress and cancel stay available; memory bounded
  (streaming decode).
- Scene framerate changed after processing — mapping is applied at import time
  from the artifact's recorded source fps, so re-import adapts without
  reprocessing.
- Target armature deleted before import completes — actionable error, no
  partial write left behind.
- Disk full or write failure mid-artifact — failed JobStatus with reason;
  truncated artifact is not importable (schema validation rejects it).
- Blender exits during processing — the engine self-terminates via the
  existing parent-PID watch; no orphan process.
- Backend differences — PEAR (GPU) and MediaPipe (CPU) both satisfy the same
  artifact contract; a backend without batch support is not offered (see Open
  Questions on manifest capability).

## Out of Scope

- Repairing live-path pacing for video input, and any seek/scrub reverse
  channel amending ADR-0002 — the batch artifact sidesteps both (ADR-0013).
- Batch image processing (PRD roadmap item; separate spec, same job-pipeline
  shape).
- Multi-person capture, face/expression channels, world position.
- Export formats (FBX/Alembic) and animation import from external formats
  (AMASS `.npz`).
- Retiming beyond the two defined mappings (no time-remap curves).
- Audio, or audio-synced alignment.
- The non-destructive intermediary armature (task 0034) — separate spec/ADR
  track; this spec writes to the target armature like live recording does.

## Open Questions

- Manifest capability declaration: the existing manifest `capabilities` field
  (ADR-0010) declares output channels, not verbs — how a backend advertises
  batch `process` support (a distinct schema field vs a protocol-version bump;
  do not overload the output-channel field) is resolved alongside ADR-0013's
  acceptance.
- Cancellation state: `JobState` has no `cancelled` value — decide between
  adding one and mapping cancel to `failed` with a distinguishing reason when
  the implementing task touches `contracts/job.py`.
- Artifact default location and naming — recommendation: next to the source
  video with a derived name, advanced section exposes the path; confirm at
  implementation.
- Variable-frame-rate inputs: container-declared average rate versus per-frame
  timestamps — decide with a VFR fixture during implementation.

## Related

- ADRs: [0001](../adr/0001-adopt-hexagonal-architecture.md),
  [0002](../adr/0002-tcp-json-stream-live-pose.md),
  [0003](../adr/0003-json-wire-format-ban-pickle.md),
  [0010](../adr/0010-discover-isolated-pose-backends.md),
  [0013](../adr/0013-batch-video-frame-indexed-artifact.md)
- Tasks: [0031 offline video batch animation](../tasks/0031-offline-video-batch-animation.md)
  (implementation tasks appended as they are created)
- Depends on: [PRD](../product/PRD.md),
  [spec 0001 live webcam pose streaming](0001-live-webcam-pose-streaming.md)
