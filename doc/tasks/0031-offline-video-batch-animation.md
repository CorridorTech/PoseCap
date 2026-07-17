# Task 0031: Process video files offline into timeline-rate animation

**Status:** proposed
**Created:** 2026-07-16
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:**

## Context

Field report from Dean (2026-07-16, Discord): streaming a pre-recorded video
through the live path (virtual webcam into the realtime engine) and recording
keyframes produces framerate problems. The live pipeline is paced by wall
clock — the engine processes whatever frame is current when inference
finishes, and the addon records keyframes at viewport-apply time — so a video
pushed through it drops frames under load and lands keyframes misaligned with
the Blender timeline rate. Dean's suggestion: decode the video into individual
frames, run every frame through the model offline (batch), and generate a
file the user imports at the current framerate of the Blender timeline.

The live path's contract is explicitly realtime (spec 0001, ADR-0002:
latest-wins TCP stream, duplicates and gaps tolerated); a finite video wants
the opposite contract — every frame exactly once, frame-indexed, no
wall-clock. Today `VideoFileSource` exists in the engine for test fixtures
only and loops at EOF; it is not a user-facing feature. Without this task,
video-to-animation stays squeezed through a transport designed for live
capture, and the framerate mismatch is structural, not tunable.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] A grounded shape decision is recorded (feature spec, plus ADR if the
      transport decision amends or sidesteps ADR-0002): offline batch
      processing versus pacing fixes to the live path, with the tradeoffs
      written down.
- [ ] Processing a video file runs every source frame through the selected
      pose backend exactly once, in source order, with no wall-clock pacing;
      output rows are keyed by source frame index, verified against a fixture
      video with a known frame count.
- [ ] The generated output imports into Blender as keyframes aligned to the
      scene timeline framerate — frame mapping from source fps to scene fps is
      explicit and deterministic, not dependent on processing speed.
- [ ] The live streaming path (spec 0001 contract) is unchanged; existing
      live-path tests stay green.
- [ ] Dean's report is answered with the recorded decision and, once shipped,
      the release that carries it.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Ground (`ad-ground` / `ad-grill`) the shape: engine-side batch CLI
      writing a frame-indexed animation file (candidate: JSONL of the existing
      wire-format payloads keyed by frame index, imported by the addon) versus
      addon-driven frame stepping over the TCP stream; weigh against repairing
      the live path's video pacing (rejected if the realtime contract makes
      exact-once framing structurally impossible). Check the seek/scrub
      reverse-channel note already deferred against ADR-0002.
- [ ] Draft the feature spec (`ad-spec`, doc/specs/0004) with the chosen
      shape; split implementation tasks from it (engine batch mode, addon
      import, UI entry point per the non-technical-user constraint — GUI only,
      no user-facing CLI).
- [ ] Implement per the spec's task split (TDD; fixture video with known frame
      count and golden frame-index mapping).
- [ ] Answer Dean with the decision and ship vehicle.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-16 — report received

Dean (Discord, 19:35): "One other thing I might suggest is separating videos
into individual frames, and then running that through the model rather than
the virtual webcam approach. I am having some framerate issues when streaming
a video in and recording the keyframes. Might be better to just have it
generate a file you can import at the current framerate of your blender
timeline."

Initial read: the suggestion is directionally sound and matches the deferred
video-transport note (loop-only video, seek/scrub would need a reverse
channel amending ADR-0002). Batch processing sidesteps the reverse channel
entirely for the video use case: no realtime transport, so no pacing, no
latest-wins frame drops, and the output is deterministic per frame index.
Live webcam keeps the ADR-0002 stream untouched. The open product decisions
are the output-file contract (format, where it lands, import UX inside the
addon) and how source fps maps to scene fps — those go through the spec.

### 2026-07-16 — ground of the two open product questions

Both questions raised at registration resolve by ground (comparable tools +
Blender platform convention + the project's parametrization principle); they
enter the spec as recommendations, not open forks.

Import UX: comparable tools (Rokoko Video/Vision, DeepMotion, Plask) all
converge on process-video-then-import-animation-file, and the friction they
all share is the file juggling between web tool and Blender. PoseCap already
lives inside Blender, so the recommended shape is one in-panel flow: pick a
video file in the PoseCap panel, process with progress feedback, keyframes
land on the armature — the intermediate frame-indexed file exists as an
artifact (re-import without reprocessing, support diagnostics) but the happy
path never asks the user to touch it. Simple default, advanced section
exposes the artifact and reprocessing options.

Frame-rate mapping: Blender's own BVH importer is the platform convention —
default scales source fps to scene fps (time-preserving), with 1:1
frame-to-frame mapping as the alternative. Recommended default: scale video
fps to scene fps so a 24 fps video lands time-correct on a 30 fps timeline
(Dean's "import at the current framerate of your blender timeline"); 1:1
mapping as an advanced option. Both mappings are deterministic functions of
frame index, never of processing speed.

### 2026-07-17 — implementation map (in-repo ground for the spec)

Full seam map produced for the spec session; load-bearing findings:

- ADR-0002 explicitly keeps file-based exchange "for batch and
  single-capture jobs, where on-disk artifacts are the product" — the batch
  output file is a documented sidestep of the live stream, not an amendment;
  the new ADR records that.
- `contracts/job.py` (`JobStatus`, queued/running/done/failed) was written
  for exactly this batch progress channel, is tested, and has zero consumers
  today — reuse it.
- The source generators already emit every decoded frame exactly once, in
  order, with a 0-based `seq` (pear_adapter/mediapipe_adapter `frames()`);
  `captured_at` wall clock is metric-only. Batch reuses the generators and
  replaces the TCP sink (`serve_once`, cli.py) with a file-writer port —
  port in core, adapter at the edge, wire format in contracts.
- The addon's keyframe write has no explicit-frame path: keys land at the
  playhead advancing under `animation_play` (recording.py, apply_timer.py)
  — the structural root of Dean's framerate complaint. Batch import needs a
  `frame_set(n)`-driven writer; `keyframe_manager.py` tooling then works
  unchanged on the imported keys.
- Per ADR-0010 isolation, `process` is a new subcommand in each backend CLI
  (cli.py and mediapipe_cli.py), launched via the manifest command;
  manifests declare no verb capability today — spec question.
- Test assets ready: fixture videos with pinned exact frame counts
  (tests/fixtures/video, e.g. four 240-frame clips) and
  `test_source_stream_invariants.py` already proves exactly-once ordered
  emission end to end — the template for the batch contract test.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
