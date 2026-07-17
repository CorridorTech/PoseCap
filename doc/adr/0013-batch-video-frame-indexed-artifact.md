# ADR-0013: Process video offline into a frame-indexed artifact file

**Status:** proposed
**Date:** 2026-07-17
**Deciders:** alexandremendoncaalvaro

## Context

ADR-0002 moved live pose delivery to a localhost TCP stream with a latest-wins
slot: duplicates and gaps are tolerated by contract, and delivery is paced by
wall clock. That contract is correct for a live camera and structurally wrong
for a finite video file — pushing a video through the live path (virtual
webcam) drops frames under load and lands keyframes misaligned with the
Blender timeline, as reported from the field (task 0031). A finite video needs
every source frame exactly once, in source order, keyed by frame index, with
no wall-clock anywhere in the pipeline.

ADR-0002 already anticipated this split: "File-based exchange remains for
batch and single-capture jobs, where on-disk artifacts are the product." The
engine's frame-source generators already emit every decoded frame exactly
once, in order, with a 0-based sequence number; `contracts/job.py` defines a
tested, currently unconsumed `JobStatus` progress document. What is missing is
the batch job itself and its output contract.

A deferred product note also hangs on this decision: video seek/scrub through
the live stream would need a reverse control channel amending ADR-0002.

## Decision

Video-to-animation runs as an offline batch job that writes a frame-indexed
artifact file, sidestepping the live stream entirely — this is the file-based
exchange ADR-0002 reserved for batch jobs, not an amendment to it.

* The engine gains a batch job (a `process` verb on each backend CLI, launched
  through the ADR-0010 manifest command) that reuses the existing exactly-once
  frame-source generators and replaces the TCP sink with a file-writer sink —
  port in `core/`, adapter at the edge, wire format in `contracts/`.
* The artifact is a file of schema-validated wire-format pose payloads keyed
  by 0-based source frame index (JSON-based per ADR-0003), with a header
  recording source path, declared source framerate, frame count, backend
  identifier, and protocol version.
* Progress travels through the `JobStatus` document (`contracts/job.py`),
  written via temp file plus atomic rename; the addon polls it from a timer.
* The addon imports the artifact by writing keyframes at explicit scene frame
  numbers (`frame_set`-driven), mapping source frame index to scene frame as a
  deterministic function of the declared rates — never of processing speed.
* The live path is untouched: same stream, same contract, same tests.

Feature-level behavior, mappings, and edge cases are specified in
[spec 0004](../specs/0004-offline-video-batch-animation.md).

## Consequences

* Framerate alignment becomes deterministic: keyframe placement is a pure
  function of frame index and declared rates, so the field-reported drift
  class cannot occur on this path.
* The seek/scrub reverse channel stays unnecessary for the video use case;
  ADR-0002 remains unamended and the live hot path keeps its no-disk-I/O rule.
* The artifact doubles as a re-import and support-diagnostics surface —
  processing and import decouple, so a processed video can be re-imported at a
  different scene framerate without re-running inference.
* On-disk artifacts return for batch (as ADR-0002 reserved): the writer must
  handle disk-full and partial-write failures, and schema validation must
  reject truncated artifacts on import.
* The manifest `capabilities` field (ADR-0010) declares output channels, not
  verbs; advertising batch support requires a distinct manifest schema
  addition or a protocol-version bump — not an overload of the output-channel
  field — resolved with this ADR's acceptance.
* Two sinks (TCP, file) now sit behind the same frame-source seam — the
  two-adapters rule makes the seam real rather than hypothetical.

## Alternatives Considered

* Repair live-path pacing for video input — rejected: the latest-wins contract
  makes exactly-once delivery structurally impossible without breaking the
  realtime contract for the live camera, the feature the product exists for.
* Addon-driven frame stepping over the TCP stream (addon requests frame N,
  engine responds) — rejected: requires the reverse control channel amending
  ADR-0002, couples the realtime transport to batch semantics, and keeps
  wall-clock delivery in a path that does not need a transport at all.
* Reuse the live TCP stream for batch delivery with backpressure — rejected:
  the stream's latest-wins slot is the exact mechanism that drops frames;
  replacing it per-mode forks the transport contract per consumer.
* Deliver the batch result in memory (addon reads engine stdout) — rejected:
  loses the re-import and diagnostics artifact, and stdout framing is fragile
  under logging (same grounds as ADR-0002's rejection of stdout transport).
