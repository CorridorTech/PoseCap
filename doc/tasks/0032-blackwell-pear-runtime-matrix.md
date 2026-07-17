# Task 0032: Qualify a Blackwell-capable PEAR runtime matrix

**Status:** proposed
**Created:** 2026-07-17
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:** issue #49

## Context

The PEAR backend pins Torch `2.4.1+cu124`, whose compiled CUDA kernels end at
`sm_90`. Every RTX 50 (Blackwell, `sm_120`) machine is therefore locked out of
PEAR: the GPU is visible but cannot execute the first inference (issue #49,
RTX 5090 field report). The reporter proved the path end to end by hand —
Torch nightly cu128 plus PyTorch3D compiled for `sm_120` gave a working live
PEAR stream on an RTX 5090 — and PyTorch has since shipped official Blackwell
support in stable releases: 2.7.0 is the first stable line with `sm_120`
kernels and official cu128 wheels. The RTX 50 install base only grows; every
month without a qualified matrix widens the locked-out audience of the
consumer-GPU product promise.

The release pipeline already compiles PyTorch3D from source on the release
runner (`tools/install/setup_pear_runtime.ps1`, VS 2022 + CUDA), so a matrix
bump is a re-pin plus requalification, not new infrastructure.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] A grounded matrix decision is recorded: target stable Torch line with
      `sm_120` kernels (candidate: the newest stable verified against
      PyTorch3D), cu12x index URL, and the PyTorch3D version/build that
      compiles against it — with the single-matrix-for-all-GPUs versus
      per-architecture-payload question answered by evidence, not preference.
- [ ] The PEAR payload built from the new matrix passes Doctor and a real
      source-to-TCP inference on a pre-Blackwell qualified GPU (regression:
      the existing RTX 30/40 audience keeps working).
- [ ] The same payload passes Doctor and a real PEAR live stream on an RTX 50
      GPU (Blackwell validation — coordinate the retest with the issue #49
      reporter if no RTX 50 hardware is available in-house).
- [ ] Doctor reports the architecture-compatibility check truthfully for both
      generations (no false "unsupported" on Blackwell, no false success).
- [ ] Issue #49 is answered with the qualified matrix and the release that
      carries it; the issue's remaining-before-close checklist is updated.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [ ] Ground (`ad-ground`) the exact pins: newest stable Torch with `sm_120`
      wheels compatible with PyTorch3D source builds (start at Torch 2.7.0 /
      cu128, check newer stable lines), plus torchvision and the PyTorch3D
      revision; verify cu128 wheels retain pre-Blackwell architectures so one
      matrix serves all supported GPUs.
- [ ] Update the pins (`requirements-torch.lock`, `torchIndexUrl` in
      `packaging/build_installer.ps1`, PyTorch3D reference in
      `tools/install/setup_pear_runtime.ps1`) and rebuild the PEAR payload.
- [ ] Qualification build (workflow_dispatch) and the two-generation
      validation runs; record evidence in Notes.
- [ ] Ship with the next release; answer issue #49.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-17 — task recorded

Prioritized by the maintainer into the v1.0.7 field-driven slice alongside
task 0031 (offline video batch) and tasks 0014/0015 (support bundle).
Evidence base: issue #49 reporter's working hand-built runtime (Torch nightly
cu128 + source-built PyTorch3D on an RTX 5090) and PyTorch 2.7.0 release
notes announcing official `sm_120` stable support with cu128 wheels.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
