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

### 2026-07-12

Built and exercised `PoseCap_v1.0.0-win.4_Windows_Setup.exe` from an empty
`%LOCALAPPDATA%\PoseCap` on the development workstation. The bootstrap completed
in about 105 seconds and produced `SETUP_OK`; the app-local Python 3.11 runtime,
Torch cu124, bundled wheels, pinned PEAR checkout, Hugging Face weights, engine
executable, and Blender 5.0 extension all passed their installation checks. The
licensed SMPL/SMPL-X/FLAME assets remained absent from the new install as required.

The installed engine passed `doctor` against the license-holder's external PEAR
asset directory and produced an `ok` SMPL-X pose frame from `Ale-PoseCAp.mp4`.
A Blender background smoke imported `X Bot.fbx`, auto-selected its sole armature,
converted the Mixamo skeleton with probe error `0.0000`, resolved the installed
runtime paths, and created a support bundle containing diagnostics and setup logs.

This is component-level and integrated smoke evidence, not completion of this
task's clean-machine E2E criteria: the machine still had development tooling, the
video stream was not started through the Blender panel and observed applying to
the X Bot in the same run, and the 10-minute FPS, p95 latency, restart, and orphan
process criteria were not measured. Those acceptance checkboxes remain open.

The panel now displays the installer build label (for example `1.0.0-win.4`),
auto-persists the fixed per-user runtime when detected, auto-selects an unambiguous
armature, consolidates rotating addon/engine logs with setup logs, and creates a
local support ZIP. These behaviors were added with focused regression tests; the
build-label correction followed an observed RED to GREEN TDD cycle.

### 2026-07-12 — Integrated video-to-armature E2E

After the component smoke above, a single Blender 5.0 background run exercised the
production operator path end to end: import `X Bot.fbx`, auto-select and convert its
Mixamo armature, call PoseCap `Start Stream` with `Ale-PoseCAp.mp4`, launch the
newly installed engine, receive its TCP pose frame, execute the addon timer, observe
the `left_elbow` matrix change, and call `Stop Stream`. The run printed
`POSECAP_E2E_OK version=1.0.0-win.4 source=video target=Armature`.

The first harness attempt is intentionally not counted: it raised because the test
used a nonexistent `mathutils.Matrix.is_equal` method while Blender still returned
process exit code zero. The corrected harness verifies both the explicit success
marker and the bone-matrix effect. This closes the single-run video-to-armature
integration gap noted above, but does not close the clean-machine, interactive GUI,
10-minute performance, latency, restart, or orphan-process acceptance criteria.

### 2026-07-12 — Repair install regression and final package

Installing `win.5` over the existing runtime exposed a non-interactive repair bug:
`uv venv` waited for confirmation when the target venv already existed, leaving the
hidden installer stuck at "Create engine virtual environment". The test processes
were terminated, a RED packaging contract was added, and the bootstrap now invokes
`uv venv --clear` as documented by uv for deterministic replacement.

`PoseCap_v1.0.0-win.6_Windows_Setup.exe` was then built from the reviewed source and
installed over the existing `win.5` state. The repair completed with exit code zero
in 27 seconds, proving the prompt was removed. A subsequent single-run Blender E2E
again imported and converted X Bot, streamed the test video through the installed
engine, observed pose application, and printed
`POSECAP_E2E_OK version=1.0.0-win.6 source=video target=Armature`. The version came
from the installed `installer_manifest.json`, proving the panel/support build label
matches the setup package rather than a hard-coded extension version.

### 2026-07-12 — Patch release candidate 1.0.1

The patch bump updates the workspace packages and Blender extension to `1.0.1`;
the installer build label resets to `1.0.1-win.1`. The first candidate exposed an
upgrade-only failure: the fixed install directory retained `1.0.0` wheels beside
the new `1.0.1` wheels, so uv rejected duplicate distributions. The bootstrap
failed but Inno's `[Run]` entry still returned setup exit code zero, creating a
false-success install with no engine executable.

Two RED-to-GREEN packaging contracts now protect the upgrade path. Inno
`[InstallDelete]` removes old versioned wheels and extension ZIPs before copying
the new payload. The bootstrap runs through Pascal `Exec` with
`ewWaitUntilTerminated`; a nonzero child result raises a setup exception instead
of reaching a successful Finish state.

The rebuilt `PoseCap_v1.0.1-win.1_Windows_Setup.exe` upgraded the intentionally
contaminated install in 26 seconds, reduced the wheel directory from both 1.0.0
and 1.0.1 payloads to only 1.0.1 plus PyTorch3D, completed the bootstrap and
extension verification, and returned exit code zero. The installed package then
passed the video-to-X-Bot E2E with
`POSECAP_E2E_OK version=1.0.1-win.1 source=video target=Armature`. Final candidate
SHA-256: `46F2AF38B3F6324E77E9CC71F3EED63F512AEA68927F8BE42E840A22B5CA293F`.

### 2026-07-13 — Pre-release fresh-context review

The fresh-context review found that the installer accepted the first Blender on
`PATH` without verifying the supported version, panel redraw could replace a
manually selected unconverted armature, and support operators did not translate
all Blender/ZIP failures into user-facing errors. Regression tests were observed
RED before each correction and GREEN afterward. The installer now probes every
candidate, ignores Blender versions older than 4.2, and chooses the newest
supported installation. Capture remains locked until the selected armature has
the complete PoseCap bone convention, while auto-selection only runs when no
valid manual target exists. Support actions now report failures through the
Blender operator boundary instead of leaking tracebacks.

The workstation has a hypervisor but Windows Sandbox is not installed; querying
or enabling the optional feature requires elevation. The empty-`LOCALAPPDATA`
run remains an installation-state simulation on a development workstation, not
proof of the clean-machine acceptance criterion. The clean VM/Sandbox, ten-minute
FPS and latency session, Doctor failure-path matrix, and orphan-process checks
remain open and must not be claimed in the patch release notes.

The reviewed source rebuilt
`PoseCap_v1.0.1-win.1_Windows_Setup.exe` with SHA-256
`E1F3743AB4F3549109EDFCD55FED02301057BD37D4A94C04594DCC06B8D9E36A`.
An in-place repair completed with exit code zero, selected Blender 5.0.1 after
the new version probe, installed and listed the extension, retained only the
1.0.1 PoseCap wheels, and preserved the installer build label. The installed
artifact then imported and converted X Bot with probe error `0.0000`, streamed
`Ale-PoseCAp.mp4` through the installed engine, changed the `left_elbow`
rotation, and emitted
`POSECAP_E2E_OK version=1.0.1-win.1 source=video target=Armature`.

The parent-process shutdown probe started Blender and the installed engine as
its child, terminated Blender, and observed the engine exit after 0.233 seconds.
This satisfies the five-second orphan-process criterion on the development
workstation; the clean-machine and ten-minute performance/latency criteria
remain open.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
