# Task 0035: Engine batch process verb writes the frame-indexed artifact

**Status:** proposed
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** [doc/specs/0004-offline-video-batch-animation.md](../specs/0004-offline-video-batch-animation.md)
**Board ref:**

## Context

First vertical slice of spec 0004 (ADR-0013 transport decision): given a video
file, the engine processes every source frame exactly once through the
selected backend and writes the frame-indexed artifact plus JobStatus
progress. Demonstrable on its own: run the batch job against a pinned fixture
video and get a schema-valid artifact with one row per source frame — no
Blender involved. The existing frame-source generators already emit
exactly-once ordered frames with a 0-based `seq`
(`test_source_stream_invariants.py` proves it); this slice adds the artifact
wire format in `contracts/`, a file-writer port in `core/`, and the `process`
verb on both backend CLIs, replacing the TCP sink (`serve_once`) with the
file-writer adapter.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Artifact wire format defined in `contracts/` (spec R4): header with
      source path, declared source framerate, frame count, backend identifier,
      protocol version; rows are schema-validated wire-format pose payloads
      keyed by 0-based source frame index; golden JSON fixture pins the format;
      truncated or malformed artifacts fail decode with a typed error.
- [ ] A `process` verb on both backend CLIs (`cli.py`, `mediapipe_cli.py`)
      runs a video through the backend with no wall-clock pacing and writes
      the artifact via a `core/` port + edge adapter (spec R3, R12); the
      240-frame fixture yields exactly 240 rows, indices 0..239 strictly
      increasing, verified by a contract test.
- [ ] No-person frames produce explicit rows (spec R8, engine side).
- [ ] Two consecutive processing runs on the same fixture produce identical
      frame-index sequences (spec success criterion; pose float values are
      model output and out of scope).
- [ ] JobStatus (`contracts/job.py`) written atomically through the job:
      queued, running with monotonically increasing progress, done; decode
      failures and I/O errors land failed with a non-empty reason, and a
      zero-frame video lands failed with an explicit "no frames decoded"
      reason, never an empty done (spec R5, R11 engine side, edge case);
      integration test observes the transitions.
- [ ] The cancellation JobState question (spec Open Questions) is decided
      while this task owns `contracts/job.py`: add a `cancelled` state or
      pin cancel-maps-to-failed-with-distinguishing-reason; recorded in the
      spec's Open Questions resolution so task 0037 consumes the contract
      without reopening it.
- [ ] The variable-frame-rate question (spec Open Questions) is decided with
      a VFR fixture: container-declared average rate versus per-frame
      timestamps; recorded in the spec's Open Questions resolution.
- [ ] The manifest batch-capability question (spec Open Questions) is decided
      and recorded: distinct schema field or protocol-version bump, never an
      overload of the output-channel `capabilities` field; ADR-0013 notes the
      resolution.
- [ ] Artifact default location and naming decided and recorded in the spec's
      Open Questions resolution.
- [ ] Live path unchanged: existing live-path and stream-invariant tests pass
      without modification (spec R12).
- [ ] Engine logs batch processing rate at INFO to the existing bounded logs
      (spec R15).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] TDD the artifact wire format in `contracts/` (golden fixture first),
      mirroring the `frames.py`/`job.py` codec conventions.
- [ ] TDD the file-writer port in `core/` and its adapter at the engine edge;
      writer consumes the existing `frames()` generators.
- [ ] Add the `process` verb to `cli.py` and `mediapipe_cli.py`, wiring
      JobStatus writes around the job lifecycle.
- [ ] Decide and implement the manifest batch-capability declaration; update
      ADR-0013 and the PEAR/MediaPipe manifests.
- [ ] Contract + integration tests against the 240-frame fixtures
      (`tests/fixtures/video`), including corrupt-input, zero-frame, and VFR
      fixtures.
- [ ] Update ARCHITECTURE.md's batch IPC pattern line (today: image file-drop
      only) to cover the video artifact path this task lands (also tracked in
      task 0031's plan).

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — task created

Split from spec 0004 at acceptance. Seam map and pins live in task 0031's
Notes (2026-07-17 implementation map); this slice is the engine/contracts
leg. Determinism criterion covers frame indexing, not pose float values
(model output; eval-tier territory per the spec).

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
