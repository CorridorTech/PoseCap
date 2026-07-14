# Spec `0003`: Select Windows Pose Backend modules

**Status:** accepted
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro

## Context

Windows animators need one PoseCap installation experience even when they choose
different combinations of license, account, and hardware requirements. Separate
backend installers would expose implementation boundaries as product complexity;
one combined environment would make an optional backend capable of breaking every
installation. This feature provides one Windows suite installer that coordinates a
fixed PoseCap Base and independently isolated backend components.

## User Scenarios

- **Scenario 1: Install the recommended account-free path**
  - Given a Windows animator runs PoseCap Setup on a machine without NVIDIA
  - When they choose the recommended MediaPipe setup after that backend ships
  - Then Base and MediaPipe are installed without PEAR, MHR, CUDA, or provider-account
    requirements

- **Scenario 2: Preserve the current PEAR workflow**
  - Given an animator chooses the PEAR component
  - When setup completes
  - Then the validated PEAR runtime and manifest are installed and the existing live
    capture workflow remains unchanged

- **Scenario 3: Install any backend combination**
  - Given two or three backend components are available
  - When the animator selects any combination in Custom setup
  - Then only those components are installed and each retains its own environment and
    manifest

- **Scenario 4: Repair or remove one backend**
  - Given Base and multiple backends are installed
  - When the animator reruns setup and repairs or explicitly removes one component
  - Then unaffected backends remain ready and no stale manifest points at removed
    runtime files

## Requirements

### Functional

- The Windows installer must expose one fixed PoseCap Base component and one optional
  component for every implemented Pose Backend.
- Base must install the Blender extension, backend registry support, shared
  diagnostics, and installer inventory without checking NVIDIA, backend accounts, or
  backend models.
- Every backend component must install into its own directory and environment and must
  atomically register exactly one validated backend manifest.
- Setup types may preselect a recommended combination, but Custom must permit any
  available backend combination while Base remains fixed.
- The online installer must download only selected component payloads and must verify
  their pinned SHA-256 values before installation.
- The suite must record installed component versions, owned paths, manifest paths, and
  readiness state without recording credentials or access tokens.
- Rerunning setup must support repair, preserve selected healthy components, and
  explicitly remove deselected backend-owned files and manifests.
- PEAR model-license acceptance and model acquisition must remain a PEAR component
  workflow; selecting or omitting PEAR must not change another backend.
- The addon must auto-select one ready backend and must use its existing selector when
  more than one backend is ready.

### Non-functional

- A failed optional component must produce an actionable component-scoped error and
  must not corrupt inventory for unaffected components.
- Backend payloads, manifests, logs, and inventory must remain free of credentials,
  tokens, and redistributable copies of licensed model assets.
- Generated installer behavior must be regression-tested without requiring Blender,
  CUDA, or backend imports.

## Success Criteria

- A generated installer contains Base plus every implemented backend component, with
  Base fixed and each backend optional.
- A Base-only installation performs no NVIDIA check and leaves no PEAR or MHR runtime
  directory or manifest.
- Selecting PEAR produces the same validated runtime and launch command as the current
  installer.
- Pairwise install, repair, and explicit removal tests preserve every unaffected
  component and leave the installed inventory equal to observed disk state.
- Online packaging fails before release when a selected payload lacks a pinned URL,
  size, or SHA-256 value.
- Clean-machine acceptance observes a GUI-driven install and a ready PoseCap panel
  without requiring terminal commands.

## Edge Cases

- Upgrade from the current monolithic PEAR installer.
- Base is installed with no backend selected.
- A previously installed backend is deselected on repair.
- A backend download or doctor fails after Base is installed.
- A runtime directory is locked by Blender or a backend process.
- Installed inventory is missing, stale, or malformed.
- Two selected backends require conflicting Python or PyTorch versions.
- The user cancels during a multi-component download.

## Out of Scope

- Extending MediaPipe Lite beyond its validated body capability, including finger
  retargeting and its separate Blender acceptance evidence.
- Packaging Linux or macOS installers.
- Redistributing licensed PEAR, SMPL-X, FLAME, MANO, or gated MHR assets.
- Merging backend environments or replacing the TCP JSON PoseStream.

## Open Questions

None. ADR-0011 owns the suite-orchestrator decision; backend-specific setup remains
owned by each backend's implementation task.

## Related

- ADRs: [ADR-0010](../adr/0010-discover-isolated-pose-backends.md),
  [ADR-0011](../adr/0011-use-modular-suite-installer.md)
- Tasks: [Task 0022](../tasks/0022-make-pear-optional-installer-module.md),
  [Task 0023](../tasks/0023-externalize-verified-pear-payloads.md),
  [Task 0024](../tasks/0024-integrate-mediapipe-lite-backend.md),
  [Task 0026](../tasks/0026-qualify-gui-release-backends.md)
- Supersedes / Depends on: [Spec 0002](0002-select-installed-pose-backend.md)
