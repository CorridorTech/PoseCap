# Task `0021`: Reconcile optional Pose Backend architecture

**Status:** done
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0002-select-installed-pose-backend.md
**Board ref:**

## Context

The `ad-architecture` audit for Task 0020 found that `ARCHITECTURE.md` still describes
PEAR, CUDA, and Windows as system-wide constraints even though the implemented
manifest boundary makes them properties of one Pose Backend. Audit mode deliberately
does not rewrite an existing binding document. The architecture must be reconciled
only after the maintainer accepts ADR-0010, so current architecture is not silently
superseded by an unaccepted proposal.

## Acceptance Criteria

- [x] ADR-0010 has an explicit maintainer disposition: accepted, amended, or rejected.
- [x] If accepted or amended, `ARCHITECTURE.md` describes the Pose Backend manifest
  boundary, isolated processes, and PEAR-specific CUDA/Windows constraints without
  copying per-decision rationale from the ADR.
- [x] The architecture continues to bind one startup event and TCP JSON PoseStream;
  it does not promise MediaPipe or MHR runtime support before their implementation.
- [x] `ad-architecture`, Markdown-link validation, and documentation drift checks pass.

## Plan

- [x] Present the ADR-0010 decision and the audit drift to the maintainer.
- [x] Apply the maintainer's disposition through the binding documentation workflow.
- [x] Re-run `ad-architecture` and documentation gates.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14 — created from Task 0020 review

The code seam and PEAR tracer are verified. This task contains only the binding-doc
reconciliation that `ad-architecture` audit mode correctly refused to perform.

### 2026-07-14 — maintainer acceptance and closeout

The maintainer explicitly directed acceptance and reconciliation. ADR-0010 is now
accepted. `ARCHITECTURE.md` binds one selected isolated Pose Backend behind the
existing startup event and TCP JSON stream, identifies PEAR's Windows/CUDA constraint
as backend-specific, and states that PEAR remains the only implemented backend. No
MediaPipe or MHR runtime support is represented as shipped.

Post-change verification passed: the architecture audit found none of the stale
PEAR-global wording, Markdown links and `git diff --check` were clean, and the focused
repository-governance suite passed 7 tests.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (documentation gates only; recorded in Notes)
- [x] Code review completed (maintainer disposition plus `ad-architecture` audit)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
