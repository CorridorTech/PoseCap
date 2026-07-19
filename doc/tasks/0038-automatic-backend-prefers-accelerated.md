# Task 0038: Make the Automatic Pose Backend choose instead of refusing

**Status:** in-progress
**Created:** 2026-07-19
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0002-select-installed-pose-backend.md
**Board ref:**

## Context

Field observation (maintainer, 2026-07-19, during the 1.0.7 qualification): the
Pose Backend dropdown offers "Automatic", but on a machine with both backends
installed the panel still demands a manual pick — "Choose a Pose Backend before
starting capture." That is not a defect against the current contract: spec 0002
says "with one ready backend, PoseCap must select it automatically; with
multiple ready backends, PoseCap must persist and reuse the user's selection",
and `resolve_installed_pose_backend` raises `BackendSelectionError` when several
are ready and nothing is chosen. The Automatic entry's own description says it
plainly: "Use the sole ready installed backend".

The defect is the promise. "Automatic" reads, to an animator, as "the app picks
the right one for me". For anyone who accepts the recommended full install
(PEAR + MediaPipe) it is instead a dead entry whose only effect is a warning —
friction on the default path, for the exact user the PRD says must never need
technical judgement.

The installer already answers the same question in the user's favour: PR #93
preselects PEAR when an NVIDIA driver is present. The panel should speak that
same language rather than contradict it.

Maintainer decision (2026-07-19): give Automatic a real policy — prefer the
accelerated backend, keep the explicit override. This amends spec 0002.

## Decision and rationale

Automatic resolves, among the ready backends, to the one with the strongest
accelerator: `nvidia-cuda` outranks `cpu`. On a full install that is PEAR
(body + hands + face on the GPU); with only MediaPipe ready it is MediaPipe;
with one backend the existing sole-ready path is unchanged.

The rank is read from each backend's declared
`compatibility.accelerators` (`contracts/.../backend_manifest.py`), so the
policy stays pure data-driven logic with no host probing — a backend that
declares a new accelerator slots into the rank without touching the resolver.

Accepted assumption: "PEAR is ready" implies a CUDA-capable machine, because
the installer only offers PEAR when it detects an NVIDIA driver (#93) and
readiness already requires the backend executable to exist. A user who force
installs PEAR on a GPU-less machine and never overrides the dropdown gets a
launch failure instead of a selection warning; the override remains one click
away, and runtime GPU health was already outside spec 0002's readiness model.

## Acceptance Criteria

- [x] With several ready backends and no explicit selection, Automatic resolves
      to the accelerated backend rather than raising `BackendSelectionError`.
- [x] An explicit user selection still wins over the Automatic policy and is
      still honored while it remains ready.
- [x] The sole-ready and no-ready paths keep their current behavior, including
      the diagnostic detail carried by the no-ready error.
- [x] Resolution stays deterministic regardless of backend discovery order.
- [x] The Automatic entry's description and the panel's "choose one" hint state
      what actually happens, so the UI stops promising something else.
- [x] Spec 0002 records the amended rule rather than being contradicted by code.

## Notes

Append-only.

- 2026-07-19: Opened from the maintainer's 1.0.7 qualification test. Grounded in
  the installed manifests on the maintainer's machine: PEAR declares
  `accelerators: ["nvidia-cuda"]` with `body/hands/face`, MediaPipe declares
  `["cpu"]` with `body` only — the rank signal already exists in the contract
  and needs no new field.
- 2026-07-19: Implemented and reviewed with fresh context on both axes.
  Findings closed rather than logged: `preferred_pose_backend` is now exported
  from `__init__.py` (it was module-public but outside `__all__`, breaking the
  package's own export precedent and blocking a direct unit test); it now
  raises `BackendSelectionError` on an empty catalogue instead of letting
  `max` surface a bare `ValueError` at a user-facing edge; the Automatic copy
  no longer says "GPU", because the policy is generic (any non-CPU
  accelerator) and the wording would go stale the day an NPU backend
  registers; and the new panel hint gained tests
  (`tests/addon/test_live_stream_panel.py`) after the Spec reviewer found the
  AC shipping unverified.
- 2026-07-19: Correction to the note below, after an adversarial review. Calling
  the `capture_readiness.py` integration "a thin delegation, risk is low" was
  wrong, and it is exactly the sentence that would stop a reviewer looking
  there. Two real consequences were missed:
  - On a full install with no explicit choice, `body_models_ready_for_selected_backend`
    flips from `True` to `False`. The resolver no longer raises, so it returns
    PEAR, whose installer-written manifest omits `requires_body_models` (the
    contract defaults it to `True`). Onboarding therefore moves from "body
    models ready" to "body models required". This is arguably more honest —
    `can_start_stream` was already `False` in that state, so the checklist and
    the button now agree instead of contradicting — but it is a user-visible
    change that shipped unrecorded and untested.
  - The `except BackendSelectionError` branch in that module carried a distinct
    rule (`any(not requires_body_models)`) that is now unreachable in the
    multi-ready case. Dead code introduced silently.
  `capture_readiness.py` still has no test module; that gap is now a tracked
  follow-up rather than a dismissed one.
- 2026-07-19: Not yet exercised in the real Blender GUI. The change lands after
  the `v1.0.7-win.10` build was cut, so it is NOT in that artifact; shipping it
  needs a fresh build, and the maintainer decides whether it rides 1.0.7 or a
  later release.
