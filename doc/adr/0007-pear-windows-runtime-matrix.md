# ADR-0007: Use a Python 3.11 cu124 PEAR Windows runtime

**Status:** superseded by [ADR-0016](0016-blackwell-cu128-runtime-matrix.md)
**Note:** a cu128 re-pin is proposed in [ADR-0016](0016-blackwell-cu128-runtime-matrix.md), pending qualification (task 0032)
**Date:** 2026-06-27
**Deciders:** alexandremendoncaalvaro

## Context

The PEAR adapter and `posecap-engine doctor` can now exercise the runtime boundary,
but live hardware validation was blocked by PyTorch3D on Windows. The current
Python 3.12 plus Torch 2.11 environment is not the project target and produced
ad-hoc failures. Task 0007 tested the project-aligned path first: Python 3.11,
uv-managed runtime, Torch/Torchvision 2.4.1/0.19.1, external pinned PEAR, and a
doctor gate. On this workstation, Torch/Torchvision cu124 wheels installed cleanly
and PyTorch reported CUDA on the RTX 3080. PyTorch3D `v0.7.9` failed when built from
uv's deep Git cache path with `mesh_normal_consistency_cpu.cpp`: `fatal error C1083:
Cannot open compiler generated file: '': Invalid argument`. The same PyTorch3D tag
built successfully when cloned into the shorter ignored path `.agentic\p3d` and
compiled with Visual Studio 2022, Torch `2.4.1+cu124`, torchvision `0.19.1+cu124`,
and local CUDA Toolkit `v12.8`. The final doctor report was green for Python,
NVIDIA visibility, Torch CUDA, PEAR imports, PyTorch3D importability, the external
PEAR pin, and pinned Hugging Face weights; the only remaining error was missing
licensed SMPL/SMPL-X/FLAME assets.

## Decision

We will use a Python 3.11 uv-managed PEAR runtime on Windows with Torch
`2.4.1+cu124`, torchvision `0.19.1+cu124`, PyTorch3D `v0.7.9` built from a short
local source checkout, and CUDA Toolkit `v12.8` for the PyTorch3D source build. The
setup script owns this path and writes logs under `.agentic/pear-runtime/`; the
runtime venv and PyTorch3D source checkout stay ignored. `posecap-engine doctor
--download-weights` remains the machine-readable readiness gate, and licensed
SMPL/SMPL-X/FLAME assets remain external to the repository.

## Consequences

* The runtime stays aligned with ADR-0004: uv remains the environment manager, and
  the engine uses Python 3.11 instead of conda/Python 3.9.
* The runtime stays aligned with ADR-0005: PEAR source and licensed assets remain
  external and pinned, never vendored into this repository.
* PyTorch3D source compilation is reproducible through a script-owned short checkout
  instead of uv's deep Git cache path.
* The install path now requires Visual Studio 2022 build tools and CUDA Toolkit
  `v12.8` for the source build.
* Torch's CUDA build is `cu124` while the source-build toolkit is `v12.8`; this
  produced a PyTorch minor-version mismatch warning during the successful build and
  remains a compatibility detail the installer must surface.
* Live PEAR HITL remains blocked until a license holder installs the required
  SMPL/SMPL-X/FLAME assets from official sources.

## Alternatives Considered

* Continue Python 3.12 plus Torch 2.11 — rejected because PyTorch3D had no working
  wheel path and the source-build attempts were ad-hoc environment mutation.
* Build PyTorch3D directly from uv's Git cache — rejected because the deep cache path
  reproduced the Windows `mesh_normal_consistency_cpu.cpp` C1083 failure.
* Require CUDA Toolkit `v12.4` or `v12.1` before continuing — rejected for this
  workstation because `v12.8` is already installed and successfully built PyTorch3D
  against Torch cu124.
* Switch to conda/Python 3.9 — rejected because it conflicts with the project's uv
  and Python 3.11 rules unless a future ADR supersedes this one.
* Replace or shim PyTorch3D — rejected because it changes a scientific dependency
  rather than fixing the installer/runtime path.
