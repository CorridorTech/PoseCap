# Task 0040: Cover capture readiness with its own test module

**Status:** proposed
**Created:** 2026-07-21
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0002-select-installed-pose-backend.md
**Board ref:**

## Context

`addon/posecap_addon/capture_readiness.py` decides whether the animator can
start capturing. It is what turns **Start Stream** clickable, and what feeds the
Getting Started checklist rows the user reads before anything else. It has **no
test module**: `tests/addon/` covers the registry, the panel, the timer, the
onboarding text and more, but nothing named for capture readiness.

The gap was recorded during task 0038 and is worth restating, because the first
assessment of it was wrong in an instructive way. Calling the module "a thin
delegation, low risk" is precisely the sentence that stops a reviewer looking —
and two real consequences had already slipped through underneath it. When the
Automatic policy changed, `body_models_ready_for_selected_backend` flipped from
`True` to `False` on a full install with no explicit choice, moving onboarding
from "body models ready" to "body models required"; and the
`except BackendSelectionError` branch kept a rule
(`any(not requires_body_models)`) that the new resolver made unreachable. Both
shipped unrecorded. Neither would have been silent with tests on this module.

Today the animator-facing promise is pinned only indirectly, through the
resolver's own tests. That means a change to readiness logic can keep every
existing test green while making the button lie — either disabled when capture
would work, or enabled into a failure. For a product whose users must never
need technical judgement, the button's honesty is the contract.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] `tests/addon/test_capture_readiness.py` exists and exercises the module
      through its public interface, not its private helpers.
- [ ] Capture-ready is asserted for each registry shape that matters: no ready
      backend, exactly one ready backend, several ready with no explicit
      selection, and several ready with an explicit selection.
- [ ] The body-models dimension is asserted independently of the backend
      dimension, including a backend whose manifest omits
      `requires_body_models` (the contract default).
- [ ] The dead `except BackendSelectionError` rule identified in task 0038 is
      either proven reachable by a test or removed, with the outcome recorded
      in Notes.
- [ ] Mutating any single readiness condition makes at least one new test fail
      (verified by temporarily inverting it, not assumed).
- [ ] The suite runs headless, with no Blender process and no GPU.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Read `addon/posecap_addon/capture_readiness.py` and list its public
      entry points and every branch that changes the button's state.
- [ ] Follow the fake/stub conventions already used in
      `tests/addon/test_backend_registry.py` and
      `tests/addon/test_live_stream_panel.py` rather than inventing a new
      harness.
- [ ] Write `tests/addon/test_capture_readiness.py` covering the registry and
      body-model shapes above.
- [ ] Resolve the dead `except BackendSelectionError` branch: cover it or
      delete it.
- [ ] Verify the suite is meaningful by inverting one readiness condition at a
      time and confirming a failure for each.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-21

Opened from the v1.0.7-win.11 qualification review. Confirmed the gap directly
rather than trusting the earlier note: `tests/addon/` contains nineteen test
modules and none of them is for capture readiness.

The acceptance criterion about inverting conditions is deliberate. A test
module that merely exists would close this task on paper while leaving the same
blind spot, which is the exact failure mode task 0038 recorded.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
