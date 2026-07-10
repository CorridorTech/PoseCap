# Task 0006: Installer and end-to-end success-criteria verification

**Status:** proposed
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The project tradeoff statement (GUIDELINES: a working install on the first try beats everything) gets its proof here. The POC's documented install path was never proven — every run trace points to Dean's conda env `pear10`, not the `.venv` the installers create (doc/reference/poc-verification.md). This task ships an installer that is actually tested on a clean machine, and closes SPEC-0001 by measuring its success criteria with the instrumentation built in tasks 0003/0004. The spec's latency-clock open question (cross-process timestamp source) is resolved here. HITL: requires a clean Windows machine and an RTX-class GPU. Depends on tasks 0003-0005.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] On a clean Windows machine (no dev tooling): installer run to working live stream in 15 minutes or less, documented step-by-step in Notes (PRD metric).
- [ ] Doctor check reports: GPU visible, model paths found, engine starts, TCP port free — each with an actionable failure message.
- [ ] Environment setup fetches PEAR at the pinned revision and weights at the pinned HF revision; failure modes produce actionable messages, never raw tracebacks.
- [ ] SMPL-X model acquisition documented (official MPI/Meshcapade sources, local path config); nothing licensed enters the repo or installer artifacts.
- [ ] 10-minute continuous stream: zero errors in both logs, sustained at or above 30 FPS (spec success criterion; measured numbers recorded in Notes).
- [ ] p95 capture-to-viewport latency under 100 ms over the same session; clock-source decision recorded in Notes (spec open question).
- [ ] After Blender exit, no engine process within 5 seconds (spec success criterion).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] `tools/install/` — environment installer (uv bootstrap, sync, PEAR fetch at pin, ADR-0007 PEAR runtime matrix, gated PyTorch3D source build).
- [ ] Doctor command (engine CLI subcommand) per workflows.md install flow.
- [ ] Latency measurement: resolve clock-source question; implement timestamp comparison tooling over the instrumentation logs.
- [ ] Clean-machine install run; document timings and friction in Notes; fix what failed; repeat until criterion passes.
- [ ] 10-minute measured session; record FPS/latency/error numbers in Notes.
- [ ] Full gate + /ad-commit; flip SPEC-0001 toward shipped when all spec criteria measure green.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-27

Task 0007 introduced `tools/install/setup_pear_runtime.ps1` and ADR-0007 as a
workstation-validated Windows PEAR runtime candidate for the installer work: Python 3.11,
Torch/Torchvision cu124, CUDA Toolkit v12.8 for the PyTorch3D source build,
PyTorch3D v0.7.9 from a short local checkout, external pinned PEAR, and
`posecap-engine doctor --download-weights` as the readiness gate. The clean-machine
installer in this task should consume that path after ADR acceptance instead of
inventing a new runtime matrix.

### 2026-07-09

Grounded the installer shape against the proven CK2P pattern (`C:\Dev\CK2P\packaging\`),
which Ale asked this installer to mirror. Direct mapping:

* **Inno Setup template + PowerShell renderer** (`corridorkey2.iss.template` +
  `build_installer.ps1`): one template, offline/online flavors via preprocessor;
  online flavor refused by the build script until a `distribution_manifest.json`
  reports hosted packs as `ready`. PoseCap starts offline-only the same way.
* **Runtime bundle** (`build_runtime_bundle.ps1`): CPython embeddable (pinned) +
  hash-verified wheel set from the lockfile, laid out app-local so no system
  Python or PATH dependence. PoseCap equivalent bundles the ADR-0007 matrix
  (torch/torchvision cu124, PyTorch3D 0.7.9). PyTorch3D has no official Windows
  wheel — build once on the workstation, bundle the built wheel with a recorded
  sha256, so clean machines never need CUDA Toolkit or MSVC.
* **Models pack** (`build_models_pack.ps1` + sha256 manifest): CK2P bundles a
  verified models pack after a field failure with hand-assembled folders.
  PoseCap split: PEAR weights — check redistribution license first; if not
  redistributable, installer fetches at pinned HF revision with sha256
  verification at install time (doctor already gates this). SMPL-X — never
  bundled, never fetched; documented manual acquisition only (ADR-0006).
* **Version single-source + output naming**: `PoseCap_v<ver>-win.<n>_Windows_<flavor>_Setup.exe`,
  spanned setup if payload exceeds the 4.2 GB single-exe limit (CK2P hit this).
* **Post-install gate**: `posecap-engine doctor` is the install-and-it-works
  check, mirroring CK2P's doctor-checked models install.
* **Blender extension**: `tools/build_extension.py` already produces the zip; the
  installer places it and points the user at Blender's install-from-disk flow.

Suggested layout mirroring CK2P: `packaging/build_installer.ps1`,
`packaging/build_runtime_bundle.ps1`, `packaging/installer/posecap.iss.template`,
`packaging/installer/distribution_manifest.json`, output in `packaging/dist/`.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
