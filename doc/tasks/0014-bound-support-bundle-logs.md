# Task 0014: Bound support bundle logs

**Status:** proposed
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

- [ ] The bundle includes only a documented maximum number of log files and bytes.
- [ ] A bundle that reaches either limit records the omission in `diagnostics.txt`.
- [ ] Existing bounded addon and engine logs remain included when within the limit.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] Add the bounded-copy policy to `addon/posecap_addon/support.py`.
- [ ] Add behavior tests in `tests/addon/test_support.py` for byte and file limits.
- [ ] Run the addon tests and full quality gate; record the outcome in Notes.

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

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
