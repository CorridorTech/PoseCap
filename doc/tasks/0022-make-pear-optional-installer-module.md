# Task `0022`: Make PEAR an optional installer module

**Status:** done
**Created:** 2026-07-14
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0003-select-windows-backend-modules.md
**Board ref:**

## Context

The Windows installer still checks NVIDIA and installs the full PEAR runtime before
PoseCap Base can exist. This task proves the suite-installer lifecycle with the one
backend that already works: Base becomes fixed, PEAR becomes optional, and install,
repair, and explicit removal preserve the validated PEAR behavior. MediaPipe and MHR
must not enter this slice.

## Acceptance Criteria

- [x] The generated Windows installer exposes fixed `base` and optional `pear`
  components through Recommended and Custom setup types.
- [x] Installing Base without PEAR installs and verifies the Blender extension and
  registry support without running NVIDIA, CUDA, PEAR, weight, or licensed-model
  checks.
- [x] Selecting PEAR installs the same pinned Python, Torch, PEAR, weights, doctor,
  and launch-command behavior as the current bootstrap and atomically writes its
  manifest.
- [x] Installed inventory records Base and PEAR versions, owned paths, and manifest
  state without credentials, tokens, or licensed assets.
- [x] Repairing a selected PEAR component preserves a healthy runtime; explicitly
  removing PEAR deletes only PEAR-owned runtime and manifest state and leaves Base
  usable.
- [x] Upgrade coverage migrates the current monolithic PEAR layout without duplicate
  environments or a stale backend manifest.
- [x] Generated-script and filesystem lifecycle tests cover Base-only, Base plus PEAR,
  repair, explicit PEAR removal, interrupted state, and malformed inventory.

## Plan

- [x] Run `ad-ground` against official Inno component lifecycle documentation,
  CorridorKey suite references, current PoseCap installer patterns, and both git
  histories; record the happy path and deviations in Notes.
- [x] Use `ad-tdg` to choose the installed-inventory and component-handler shape by one
  explicit criterion before editing the installer.
- [x] Add generated Inno regression tests RED for fixed Base and optional PEAR.
- [x] Split the monolithic bootstrap into Base and PEAR component handlers while
  preserving existing PEAR install behavior.
- [x] Add inventory, repair, explicit removal, upgrade, and failure-isolation behaviors
  one test at a time through `ad-tdd`.
- [x] Run the complete local gate and a two-axis `ad-review` before handoff.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-14

Created after the maintainer chose the CorridorKey-style suite pattern: one visible
installer, one fixed Base, and optional isolated Pose Backend modules. PEAR is the
first lifecycle tracer because its current runtime is already validated.

Ground completed before implementation across all four required sources:

- official Inno Setup documentation establishes `[Types]`, `[Components]`, the
  `fixed` component flag, component-conditioned entries, and custom setup as the
  native happy path;
- CorridorKey Runtime provides the validated implementation reference in
  `scripts/package_suite_installer_windows.ps1`: one suite executable, a fixed
  base, optional components, an installed inventory, and deselection-aware
  cleanup;
- PoseCap currently has one Inno template and one monolithic PowerShell bootstrap,
  with Blender installation occurring only after the NVIDIA/PEAR path;
- PoseCap history (`d862990`, `f2640f5`, `6b8b9c1`) requires retaining the light
  online installer, deterministic repair, and automatic runtime discovery, while
  CorridorKey history (`56534f9`, `9947538`, `cfc5fb1`) shows the incremental
  payload/inventory/lifecycle sequence that made the suite pattern reliable.

Happy path: Recommended selects fixed Base plus PEAR for backward compatibility;
Custom keeps Base fixed and lets PEAR be omitted. A thin bootstrap coordinates
separate Base and PEAR handlers, and a filesystem-only lifecycle handler owns the
atomic inventory and explicit deselection cleanup. Base never evaluates PEAR
prerequisites. PEAR continues to use the validated legacy paths in this slice so
existing addon/model-setup discovery does not regress; backend manifests provide
the isolation seam for later modules.

Documented deviation from the CorridorKey cleanup reference: removing PEAR deletes
its app-local Python, virtual environment, and backend manifest, but preserves the
`pear` data tree because it can contain separately licensed, user-acquired models.
That retained data is recorded separately from installer-owned executable paths.

`ad-tdg` decision: the ground-truth Base-only pair is `base=true, pear=false` ->
Blender extension verified, no NVIDIA/CUDA/PEAR/model actions, inventory contains
only ready Base, and no PEAR manifest. The Base+PEAR pair is `base=true, pear=true`
-> the existing pinned PEAR pipeline completes, its manifest is atomic, and both
components are ready in inventory. The Test Dependency Map is the rendered Inno
template, thin coordinator, independent Base/PEAR handlers, and filesystem-only
lifecycle script, exercised by `tests/test_packaging_config.py` plus subprocess
filesystem tests. Three approaches were weighed: a flag inside the monolith,
separate PowerShell handlers, and Pascal-owned lifecycle logic. The single
selection criterion was deterministic behavior testable without GPU, Blender, or
an installer UI. Separate PowerShell handlers won: they isolate prerequisites and
make lifecycle state executable in temporary directories while keeping Inno as the
selection surface.

Focused pre-change baseline observed: `27 passed` for packaging configuration,
addon support, and backend registry tests.

### 2026-07-14 — implementation and verification closeout

The installer now exposes Recommended (`base` + `pear`) and Custom (`base` fixed,
`pear` optional) through one compiled Inno executable. The former bootstrap is a thin
coordinator over independent Base, PEAR, and filesystem-lifecycle handlers. Base has
no backend prerequisite references; PEAR retains the validated pins, doctor, model
guidance, launch command, and atomic manifest.

Inventory transitions atomically through `installing` and `ready`. Base becomes ready
before PEAR begins, so an optional-component failure remains repairable without
misrepresenting Base. Same-version healthy PEAR repair preserves the environment;
upgrade reuses the legacy paths without creating a second environment. Base-only
deselection removes PEAR executable payloads and registration, including a
pre-registry monolithic install, while preserving the separately licensed `pear` data
tree.

The two-axis `ad-review` record is
`.agentic/reviews/20260714T144017Z-working-tree.md`. Its two Task-0022 findings were
fixed with regression tests. Its broader release finding — external selected payloads
and SHA-256 verification from Spec 0003/ADR-0011 — is intentionally not represented
as solved locally; Task 0023 owns the immutable hosting and clean-machine proof.

Observed verification: the rendered Inno template compiled successfully with Inno
Setup 6; all four PowerShell scripts parsed under Windows PowerShell 5.1; ruff check
and format, Pyright Windows and Linux, import-linter, Markdown links, and
`git diff --check` passed. The full suite passed with `431 passed, 9 deselected`.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
