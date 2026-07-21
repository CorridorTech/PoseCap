# ADR-0016: Re-pin the PEAR runtime to a Blackwell-capable cu128 matrix

**Status:** accepted
**Date:** 2026-07-17
**Deciders:** alexandremendoncaalvaro (maintainer)

## Context

The runtime matrix validated by [ADR-0007](0007-pear-windows-runtime-matrix.md)
pins Torch `2.4.1+cu124`, whose compiled CUDA kernels end at `sm_90`. Every
RTX 50 (Blackwell, `sm_120`) GPU is therefore locked out of PEAR: the GPU is
visible but cannot execute the first inference (issue #49, RTX 5090 field
report). The reporter proved the path end to end by hand with a Torch nightly
cu128 plus a source-built PyTorch3D, and PyTorch has since shipped official
`sm_120` support in stable lines starting at 2.7.0. Task 0032's grounded
research (citations in its Notes) selected the newest patched stable line:
the v2.9.1 build scripts pin `TORCH_CUDA_ARCH_LIST` to
`7.0;7.5;8.0;8.6;9.0;10.0;12.0`, so one cu128 wheel natively serves RTX 30
(`sm_86`), RTX 40 (`sm_89` runs `sm_86` binaries), and RTX 50 (`sm_120`).
PyTorch is sunsetting CUDA 12.8 (the cu128 default is replaced by cu130 in
2.11 and leaves the build matrix in 2.12), making 2.9.1 the last patched line
distributing cu128 wheels. Accepted 2026-07-19 on field evidence. The qualification build shipped as
`v1.0.7-win.10`. Blackwell is validated on the published build: the issue #49
reporter retested the published build on an RTX 5090 and reported it "worked out
of the box", independently corroborated by a community Linux installer
contribution (PR #98, not merged) that ran the same version pins
(torch 2.9.1+cu128, torchvision 0.24.1+cu128, PyTorch3D 0.7.9) on a Linux
RTX 5090. That contribution obtained PyTorch3D as a prebuilt third-party wheel
rather than the source build this ADR specifies, so it corroborates the runtime
version matrix on Blackwell, not this ADR's build method; on
Ampere an interleaved A/B on an RTX 3080 ran real source-to-TCP inference on
these pins (see `doc/benchmarks.md`, 2026-07-17).

## Decision

We will re-pin the PEAR runtime to Torch `2.9.1+cu128`, torchvision
`0.24.1+cu128` (the patch-aligned pair per the pytorch/vision compatibility
matrix), and PyTorch3D `v0.7.9` built from source with CUDA Toolkit `v12.8`
— one wheel matrix and one payload for all target GPUs, no per-architecture
splits. The recorded fallback, if the PyTorch3D source build fails against
2.9.1, is Torch `2.7.1+cu128` with torchvision `0.22.1+cu128` (direct
community evidence of PyTorch3D Windows builds on that line). On acceptance
this ADR supersedes ADR-0007.

## Consequences

* RTX 50 users regain PEAR with the same installer flow; RTX 30/40 users
  stay on natively compiled kernels. Blackwell is validated on the published
  build; the pre-Blackwell arm is validated only on a development runtime, and
  task 0032 still carries the packaged-payload run on an RTX 30/40 machine as
  an open criterion.
* The NVIDIA driver floor rises to R570+, and Pascal/GTX 10xx (`sm_6x`)
  drops off (2.9.1 kernels start at `sm_70`); the release notes of the
  release that ships this matrix must state both.
* The source-build toolkit (`v12.8`) now matches the wheel CUDA tag
  (`cu128`), removing the version-mismatch warning ADR-0007 had to surface.
* The matrix is stable but terminal on CUDA 12.8: the next bump is a CUDA 13
  migration with a fresh PyTorch3D revalidation, a new decision when it
  comes due.
* ADR-0007 is superseded by this decision. Its cu124 matrix stays
  reproducible via the runtime setup script's `12.4` wheel-matrix option, which
  is the rollback and triage path for anyone the throughput cost hurts.
* The cost is real and measured, not incidental: pre-Blackwell cards lose about
  32% of live throughput (RTX 3080: 30.25 -> 20.5 NET FPS). Releases carrying
  this matrix must state it, along with the R570 driver floor and the loss of
  Pascal, before a user upgrades.

## Alternatives Considered

* Stay on `2.4.1+cu124` — rejected: it locks the growing RTX 50 install
  base out of the consumer-GPU product promise indefinitely.
* Per-architecture payloads (a cu124 payload for RTX 30/40, a cu128 payload
  for RTX 50) — rejected by evidence, not preference: the 2.9.1 cu128 wheel
  already compiles every target architecture, so a split doubles the build,
  QA, and installer surface for zero capability.
* Torch `2.7.1+cu128` as the primary — rejected as primary because 2.9.1
  carries two more stable lines of fixes on the same CUDA tag; 2.7.1 is
  retained as the recorded fallback with direct community evidence of
  PyTorch3D Windows source builds.
* Torch nightly cu128 (the issue #49 reporter's hand-built path) — rejected:
  nightlies cannot be pinned reproducibly and violate the "known working
  over latest" lockfile rule (GUIDELINES §6).
