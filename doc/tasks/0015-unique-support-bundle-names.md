# Task 0015: Generate unique support bundle names

**Status:** done
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

- [x] Two bundles requested with the same timestamp receive distinct filenames.
- [x] An existing bundle is never overwritten by a new bundle request.
- [x] The behavior is covered by `tests/addon/test_support.py`.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add collision-safe output creation in `addon/posecap_addon/support.py`.
- [x] Add behavior tests for equal-timestamp bundle requests.
- [x] Run the addon tests and full quality gate; record the outcome in Notes.

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

### 2026-07-17 — implemented

`create_support_bundle` now opens the archive with exclusive create
(`ZipFile(output, "x")`) and retries with a numeric suffix
(`PoseCap-Support-YYYYMMDD-HHMMSS-1.zip`, `-2`, ...) on `FileExistsError`,
making the no-overwrite guarantee atomic at the OS level (also across
processes). The exception-as-retry shape is a deliberate, commented deviation
from GUIDELINES §2.2: a pre-check would reintroduce the check-then-create
race the task exists to fix.

TDD evidence (red proven against the pre-fix code via `git stash`, both new
tests failed there and pass now):

- `test_same_second_bundle_requests_receive_distinct_names` — pins the exact
  `-1` suffix and both files surviving.
- `test_an_existing_bundle_is_never_overwritten` — a pre-existing ZIP at the
  canonical name keeps its bytes; the new bundle lands beside it.
- `test_a_failed_bundle_attempt_leaves_no_broken_bundle_behind` —
  fresh-context review finding: a mid-write failure (for example disk full)
  left a broken ZIP squatting the canonical name; the partial file is now
  removed and the error propagates to the operator's user-facing report.

Gates: ruff check, ruff format --check, pyright Windows and Linux,
lint-imports, pytest (541 passed, 3 skipped) all green locally. Two-axis
fresh-context review run per WORKFLOW §10; the cleanup finding above was
addressed, standards findings were minor and resolved by the deviation
comment (retry loop stays unbounded by design — each attempt increments the
suffix against a finite local directory).

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
