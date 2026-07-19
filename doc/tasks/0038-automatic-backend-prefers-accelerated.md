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

- [ ] With several ready backends and no explicit selection, Automatic resolves
      to the accelerated backend rather than raising `BackendSelectionError`.
- [ ] An explicit user selection still wins over the Automatic policy and is
      still honored while it remains ready.
- [ ] The sole-ready and no-ready paths keep their current behavior, including
      the diagnostic detail carried by the no-ready error.
- [ ] Resolution stays deterministic regardless of backend discovery order.
- [ ] The Automatic entry's description and the panel's "choose one" hint state
      what actually happens, so the UI stops promising something else.
- [ ] Spec 0002 records the amended rule rather than being contradicted by code.

## Notes

Append-only.

- 2026-07-19: Opened from the maintainer's 1.0.7 qualification test. Grounded in
  the installed manifests on the maintainer's machine: PEAR declares
  `accelerators: ["nvidia-cuda"]` with `body/hands/face`, MediaPipe declares
  `["cpu"]` with `body` only — the rank signal already exists in the contract
  and needs no new field.
