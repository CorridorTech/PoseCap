# Task 0017: Add license-clean E2E fixtures

**Status:** in-progress
**Created:** 2026-07-13
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

Recorded full-body motion is the strongest regression input for the pose pipeline,
but the raw personal recording and third-party FBX characters must not become
unbounded or ambiguously licensed repository assets. This task adds small,
authorized video fixtures with provenance and exercises them through the GPU
source stream and a synthetic Blender armature.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] Three authorized 720p, audio-free personal-motion clips are tracked below 5 MB each with provenance in `tests/fixtures/video/SOURCES.json`.
- [x] Each new clip passes the GPU `live --source` wire-invariant test.
- [x] A Blender E2E creates a synthetic Mixamo-compatible armature, converts it, and applies a streamed pose without a distributed FBX.
- [x] Raw video and X/Y Bot FBX files remain outside the repository history.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add clipped fixtures and their source, consent, and processing record to `tests/fixtures/video/SOURCES.json`.
- [x] Extend `tests/engine/test_source_stream_invariants.py` one fixture at a time.
- [x] Extend `tests/e2e/test_blender_addon_smoke.py` with the procedural character conversion path.
- [x] Run the GPU and Blender E2E checks, then the full quality gate; record the outcome in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-13

Grounded against FFmpeg stream-selection and metadata controls, the existing
license-clean video fixture pattern, the current Blender smoke, and commits
8b54ca8, 208572e, and 500ce21. The raw 68.5-second 1080p recording remains
outside Git; only three 8-second 720p, audio-free excerpts with explicit author
authorization will be versioned. Third-party X/Y Bot FBXs remain local-only.

### 2026-07-13

Created three 8-second 1280x720 30fps clips from the authorized recording:
T-pose/setup, dynamic upper-body gestures, and full-body dance. Every excerpt
contains video only, is below 450 KB, and records its consent and processing in
`SOURCES.json`. The GPU source-stream invariant passed each new fixture
individually and together: 240 decoded frames per clip with valid TCP payloads.

The Blender smoke was extended through a RED-to-GREEN cycle. Its synthetic
Mixamo armature initially lacked parent links, so conversion's shoulder probe
failed as expected. Adding the minimal forearm/hand hierarchy made the public
conversion operator succeed; the subsequent simulated stream applied to the
converted `left_elbow`. The test passes with Blender 5.0.1.

The full GPU source suite passed all six fixtures in 100.04 seconds, and the
Blender conversion smoke passed in 2.49 seconds. Ruff, formatting, Pyright on
Windows and Linux, import-linter, and default pytest also passed. The raw video
was confirmed outside the repository and no X/Y Bot filename appears in the Git
index.

Fresh-context review required a stronger assertion for the converted armature.
The E2E first failed with an identity payload, then passed after the fixture
stream applied a 0.5-radian Z axis-angle to `left_elbow` and asserted the exact
expected quaternion components.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [x] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
