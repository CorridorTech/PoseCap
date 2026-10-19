# ADR-0019: Offer the cu124 matrix as an opt-in PEAR runtime for pre-Blackwell GPUs

**Status:** proposed
**Date:** 2026-10-19
**Deciders:** alexandremendoncaalvaro (maintainer)

## Context

[ADR-0016](0016-blackwell-cu128-runtime-matrix.md) moved PEAR to Torch
`2.9.1+cu128` so RTX 50 GPUs could run it. The cost is measured: on an
RTX 3080 the cu128 matrix sustains 20.53 NET FPS against 30.25 on the cu124
matrix it replaced (`doc/benchmarks.md`, 2026-07-17). Task 0041 records the
maintainer's decision that the 30 FPS target stands, and names a temporary
cu124 payload for RTX 30/40 as a legitimate fallback while the regression is
unrecovered.

Today an RTX 30/40 owner can only recover that throughput by installing
v1.0.6-win.4. That loses every fix and feature shipped since. The developer
runtime script's `12.4` option is not an answer for end users.

Three facts make an in-place switch cheap:

* `requirements-pypi.lock` is byte-identical between v1.0.6-win.4 and the
  cu128 releases, and the engine code is torch-version agnostic. The matrices
  differ only in torch, torchvision, and the PyTorch3D build.
* PyTorch3D only loads under the torch it was compiled against, so the cu124
  matrix needs a cu124 PyTorch3D wheel. The v1.0.6-win.4 PEAR payload, a
  published and hash-pinned release asset, contains exactly that wheel:
  PyTorch3D 0.7.9, cp311, built against `2.4.1+cu124`, 5.6 MB.
* The cu124 matrix is frozen (ADR-0007 is superseded and will not be re-pinned),
  so a frozen, field-proven artifact is the right input, not a fresh build.

## Decision

We will keep cu128 as the default for every GPU, and ship the cu124 matrix as a
user-selected runtime inside the same Windows PEAR payload:

* `packaging/requirements-torch-cu124.lock` pins Torch `2.4.1+cu124` and
  torchvision `0.19.1+cu124`. `packaging/pytorch3d-cu124.lock.json` pins the
  PyTorch3D wheel by the SHA-256 of its v1.0.6-win.4 source archive and of the
  wheel itself. The payload build downloads, verifies, and stages the wheel
  under `wheels/cu124/`.
* `pear_runtime.json` in the install root records a non-default choice. Its
  absence means cu128. `install_pear.ps1` honours it on every install, repair,
  and upgrade.
* `switch_pear_runtime.ps1`, exposed as two Start-menu shortcuts on the PEAR
  component, records the choice and reruns the PEAR handler. If the reinstall
  fails, it restores the previous choice so a repair rebuilds the last working
  runtime.
* cu124 is refused when any GPU reports compute capability 10.x or newer. If
  such a GPU appears after the choice was made, the PEAR handler warns and falls
  back to cu128 instead of failing setup.

## Consequences

* RTX 30/40 owners recover the measured cu124 throughput without downgrading
  and keep every later fix. The default user path is unchanged.
* The PEAR payload grows by 5.6 MB. Release CI compiles nothing extra.
* The payload build depends on the v1.0.6-win.4 release asset staying
  published. A missing or altered asset fails the build loudly via the hash
  pins. If that release must go, re-host the wheel as its own release asset and
  update the pin.
* This partly reverses ADR-0016's rejection of per-architecture payloads: still
  one payload, but two matrices. Every release must keep the cu124 arm
  installable on an RTX 30/40 machine, at minimum through the doctor gate.
* cu124 keeps ADR-0007's driver floor, below R570. Pascal and Turing on cu124
  remain unqualified, and the docs do not promise them.
* Linux is out of scope. Its installer still ships cu128 only.
* This is a bridge. Retire it once task 0041 recovers cu128 throughput on
  pre-Blackwell GPUs, or at the CUDA 13 migration, whichever comes first.

## Alternatives Considered

* Keep pointing RTX 30/40 owners at v1.0.6-win.4: rejected, because it trades
  throughput for every fix since.
* Select the matrix automatically from the detected GPU: deferred. It would
  silently install a runtime the release never qualified on that GPU class, and
  it needs a GPU allowlist. The opt-in switch can grow into this once both arms
  are qualified each release.
* Rebuild PyTorch3D against 2.4.1 in release CI: rejected for now. It doubles
  the slowest release step to reproduce a frozen artifact that already exists
  and is field-proven.
* Publish the cu124 PyTorch3D wheel separately and download it at switch time:
  rejected. It adds a new download path to user machines to save 5.6 MB per
  PEAR install.
