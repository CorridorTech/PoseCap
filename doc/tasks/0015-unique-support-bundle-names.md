# Task 0015: Generate unique support bundle names

**Status:** proposed
**Created:** 2026-07-13
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

Two support bundles created within the same second currently resolve to the same
filename, so the later ZIP can replace the earlier evidence. Support artifacts
must preserve each capture attempt until the user chooses what to share.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] Two bundles requested with the same timestamp receive distinct filenames.
- [ ] An existing bundle is never overwritten by a new bundle request.
- [ ] The behavior is covered by `tests/addon/test_support.py`.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] Add collision-safe output creation in `addon/posecap_addon/support.py`.
- [ ] Add behavior tests for equal-timestamp bundle requests.
- [ ] Run the addon tests and full quality gate; record the outcome in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-13

Fresh-context review of release PR 35 found the same-second filename collision.
The finding is non-blocking for the installer and setup patch, but it must be
resolved before support bundles are relied on for repeated captures.

### 2026-07-17 — implementation ground

Verified against current code: the filename is second-granular
(`support.py:131`, `PoseCap-Support-%Y%m%d-%H%M%S.zip`) and the archive
opens with `ZipFile(output, "w")` (`support.py:132`), which truncates an
existing file — two button clicks in the same wall-clock second collide and
the second silently replaces the first (`_write_support_bundle` passes no
timestamp, support_panel.py:122-148). Fix shape: collision-safe path
creation at support.py:131-132 (probe-and-suffix or exclusive-create "x"
with retry); the injectable `timestamp` parameter already used by
tests/addon/test_support.py:65-85 keeps the tests deterministic; the exact-
name assertion at test_support.py:78 stays valid for the no-collision case.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
