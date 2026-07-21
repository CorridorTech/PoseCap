# Task 0039: Say so when no Pose Backend is installed

**Status:** proposed
**Created:** 2026-07-21
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0002-select-installed-pose-backend.md
**Board ref:** issue #99

## Context

A user with a working machine could not capture, could not see why, and the
panel told them nothing. Issue #99 (`[Bug] MediaPipe backend option missing from
UI in v1.0.7`) is the field evidence: the reporter hand-extracted
`posecap-mediapipe-bootstrap-*.zip` into the install directory — an internal
installer payload, not a supported install path — so no backend manifest was
ever registered. The Pose Backend dropdown then offered only `Automatic`, and
nothing on screen said that zero backends existed or what to do about it. The
reporter spent their own time and ours before we could explain it.

The silence is structural, not a one-off. `_draw_pose_backend_selector` in
`addon/posecap_addon/live_stream_panel.py` draws a hint in exactly two cases:
more than one ready backend with no explicit pick, and malformed manifests
surfaced through `catalog.issues`. An empty registry with no malformed
manifests matches neither branch, so the panel renders the dropdown alone.

Two things then actively mislead. The `Automatic` entry describes itself as
"Let PoseCap pick the best installed backend for this machine"
(`stream_properties.py`), which promises a choice among nothing. And the entry
remains selectable, so the user's reasonable reading is that capture is
configured and something else is broken.

This is the product's own thesis failing: PoseCap's users are editors and
animators who must never need technical judgement, and here the app requires
them to guess. Without this fix the same report recurs for every user whose
backend registration fails for any reason — a partial install, a moved install
directory, a manually unpacked payload.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] With an empty backend registry (no ready backends and no manifest
      issues), the panel states plainly that no Pose Backend is installed,
      rather than rendering the dropdown alone.
- [ ] That message names the supported remedy — running the PoseCap installer
      or its repair entry — instead of describing internal state.
- [ ] The `Automatic` entry stops promising a pick when there is nothing to
      pick; its description and any panel hint agree with what the registry
      actually holds.
- [ ] The existing behaviour for one ready backend, several ready backends,
      and malformed manifests (`catalog.issues`) is unchanged.
- [ ] The empty-registry path is covered by a test in
      `tests/addon/test_live_stream_panel.py` that fails before the change.
- [ ] Nothing in the new path requires the user to open a log file to
      understand what happened.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Write the failing test first in `tests/addon/test_live_stream_panel.py`:
      an empty `PoseBackendCatalog` must produce a labelled message.
- [ ] Add the empty-registry branch to `_draw_pose_backend_selector` in
      `addon/posecap_addon/live_stream_panel.py`.
- [ ] Reword the `Automatic` entry in `addon/posecap_addon/stream_properties.py`
      so it does not claim a pick that cannot exist.
- [ ] Check the onboarding checklist (`addon/posecap_addon/capture_readiness.py`,
      `onboarding.py`) for the same blind spot, so the checklist and the panel
      do not disagree.
- [ ] Verify in real Blender per the standing gate, with the backend registry
      emptied, that the message appears and reads clearly.
- [ ] Reply on issue #99 with the release that carries the fix.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-21

Opened from the v1.0.7-win.11 qualification review. The gap was already
recorded as an untracked follow-up ("panel says nothing when ZERO backends are
registered"); this task gives it an owner. Grounded by reading
`_draw_pose_backend_selector` directly rather than from the issue thread: both
of its guarded branches require a non-empty catalog, which is why the empty
case renders nothing at all.

Related but deliberately out of scope, to keep one scope per task: a Pascal
(`sm_6x`) owner who force-installs PEAR now resolves to it silently, and the
resulting start failure should point back at the dropdown. That is a different
message on a different path and needs its own task.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
