# Task 0037: In-panel batch flow from video pick to imported animation

**Status:** proposed
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** [doc/specs/0004-offline-video-batch-animation.md](../specs/0004-offline-video-batch-animation.md)
**Board ref:**

## Context

Third vertical slice of spec 0004 and the user-facing one: the PoseCap panel
flow that ties the engine batch job (task 0035) and the artifact import
(task 0036) into one GUI action — pick a video, process with progress,
keyframes land. HITL because the panel shape is a design surface the
maintainer reviews (simple default + expandable advanced per the project's
parametrization principle), and because this slice closes the loop with the
field report. No user-facing CLI anywhere (PRD constraint); the engine verb
is launched through the ADR-0010 manifest command exactly like the live path
launches streaming.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Panel flow (spec R1): pick video file, target armature, and installed
      backend; start processing; on completion keyframes are on the armature
      with no manual file handling on the happy path.
- [ ] Video validated (extension and size) before the engine launches
      (spec R2).
- [ ] Progress surfaced from the JobStatus document via timer polling without
      blocking the UI (spec R5); terminal states (done, failed with reason)
      are visible panel outcomes, never a raw traceback (spec R11).
- [ ] Cancel terminates the engine by process handle within 5 seconds and no
      keyframes land from a cancelled job (spec R13), consuming the JobState
      cancellation contract decided in task 0035.
- [ ] Advanced section exposes the 1:1 mapping option, the artifact path, and
      re-import without reprocessing (spec R7, R10); the default flow shows
      none of that complexity.
- [ ] Backends without the batch capability are not offered for processing
      (manifest declaration from task 0035).
- [ ] Blender exit during processing leaves no orphan engine process within
      5 seconds (existing parent-PID watch, verified by an integration test).
- [ ] Live streaming panel behavior is unchanged; full existing test suite
      green.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Ground the panel layout against the existing stream panel and the
      advanced-options pattern (task 0008 lineage); anchor on the existing
      operator/panel structure in `addon/posecap_addon/`.
- [ ] TDD the flow state machine in `core/`-testable logic (idle, validating,
      processing with progress, importing, done/failed/cancelled).
- [ ] Implement panel + operators; launch the `process` verb through the
      manifest command; JobStatus polling on the existing timer pattern.
- [ ] Implement cancel (process-handle termination + state cleanup) on the
      JobState contract from task 0035.
- [ ] Integration + e2e checks; maintainer review of the panel shape
      (HITL gate).
- [ ] Answer Dean's report with the recorded decision and ship vehicle
      (task 0031 AC; approved-by-maintainer comment only).

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — task created

Split from spec 0004 at acceptance. Depends on tasks 0035 (engine verb +
manifest capability) and 0036 (import writer). Last slice before the v1.0.7
release vehicle carries the feature.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
