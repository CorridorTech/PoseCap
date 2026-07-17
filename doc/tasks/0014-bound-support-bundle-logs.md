# Task 0014: Bound support bundle logs

**Status:** done
**Created:** 2026-07-13
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:**
**Board ref:**

## Context

The support bundle is the fastest way for an affected user to share diagnostics,
but an unexpectedly large log directory can make Blender appear stuck or create a
ZIP that is impractical to send. The bundle must remain useful under failure
conditions without reading an unbounded amount of local data.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] The bundle includes only a documented maximum number of log files and bytes.
- [x] A bundle that reaches either limit records the omission in `diagnostics.txt`.
- [x] Existing bounded addon and engine logs remain included when within the limit.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add the bounded-copy policy to `addon/posecap_addon/support.py`.
- [x] Add behavior tests in `tests/addon/test_support.py` for byte and file limits.
- [x] Run the addon tests and full quality gate; record the outcome in Notes.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-13

Fresh-context release review identified the unbounded `*.log*` collection as a
non-blocking robustness concern. It is tracked separately so the 1.0.1 patch can
ship its installer and setup fixes without silently accepting the debt.

### 2026-07-17 — implementation ground

Verified against current code: each log family is already bounded per file
(RotatingFileHandler, 1 MB x 4 — instrumentation.py:78, engine
logging_config.py:28 via config.py:5) but the bundle-level aggregate is not:
`_archive_logs` (support.py:142) globs every `*.log*` with no count or byte
cap. The refactor in PR #68 extracted `_archive_logs` as the exact seam for
the policy; it currently returns nothing, and `diagnostics.txt` is finalized
upstream (support_panel.py:134) and written before logs are archived
(support.py:133-134), so recording omissions requires the helper to return
omission info to the caller (or reordering the writes). Tests: the strict
namelist equality in tests/addon/test_support.py:80-84 must be updated by
any bounding change; no limit/omission tests exist yet.

### 2026-07-17 — implemented

TDD red-green per behavior on `create_support_bundle` (public interface only):

- `test_support_bundle_caps_the_number_of_log_files` — red at 22 == 20, green
  after the file cap in `_archive_logs`.
- `test_support_bundle_caps_the_total_log_bytes` — red (oversized `bravo.log`
  included), green after byte accounting; a later smaller file still fits.
- `test_setup_marker_counts_toward_the_bundle_caps` — fresh-context review
  finding: `SETUP_OK` was archived outside the caps; it now counts and is
  collected first so stray logs cannot crowd it out.
- `test_support_bundle_survives_a_log_vanishing_mid_collection` — review
  finding: a log rotating away mid-collection aborted the whole bundle; a
  per-file `OSError` now degrades to a recorded omission.

Limits are the public documented constants `MAX_LOG_FILES = 20` and
`MAX_LOG_BYTES = 10 MiB` in `support.py`; a healthy install (two rotated
families, 1 MB x 4 each) never reaches them. The Notes ordering problem is
solved by `_archive_logs` returning the omitted count and `diagnostics.txt`
being written after log collection with `_omission_note` appended — no
`support_panel.py` change needed. Existing exact-namelist test stays valid
because the note only appears when something was omitted. Residual accepted
risk: a file growing between `stat` and `write` can exceed the byte budget by
at most one rotation increment.

Gates: ruff check, ruff format --check, pyright Windows and Linux,
lint-imports, pytest (536 passed, 3 skipped) all green locally. Two-axis
fresh-context review (Standards, Spec) run per WORKFLOW §10; both findings
above addressed, no standards findings.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
