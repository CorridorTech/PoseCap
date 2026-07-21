# Task 0042: Build the Linux PyTorch3D wheel in our own pinned environment

**Status:** proposed
**Created:** 2026-07-21
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:**
**Board ref:** PR #98

## Context

PoseCap promised a contributor that this piece is ours, and until it exists his
work cannot land. PR #98 (native Linux installer, @levi-lumin) now consumes a
prebuilt PyTorch3D wheel — but nothing produces one for Linux, so the installer
has nothing to install and the PR cannot merge.

The shape is already settled by how Windows works, not by preference. On
Windows the end user never compiles PyTorch3D: `tools/install/setup_pear_runtime.ps1`
builds it once on the release runner in a pinned environment, and
`packaging/build_pear_payload.ps1` repacks the result as a wheel into the
payload's `wheels/` directory (`repack pytorch3d wheel`). The user's installer
then runs `install_pear.ps1`'s "Install bundled wheels" step. Linux needs the
same division: our pipeline compiles, the user installs a wheel.

The cost of *not* doing this is measured, not hypothetical. Building PyTorch3D
on the end user's machine hit three independent version walls on a current
rolling-release distribution, documented by the contributor on PR #98:

1. **CUDA toolkit mismatch** — `torch.utils.cpp_extension` refuses to compile a
   CUDA extension unless the toolkit's major.minor matches what the torch wheels
   were built against; a system on CUDA 13.3 cannot build against cu128 torch.
2. **Host compiler cap** — CUDA 12.8's nvcc supports host GCC up to 14, and
   `-allow-unsupported-compiler` does not rescue a newer libstdc++ whose headers
   use builtins that frontend cannot parse.
3. **glibc collision** — newer glibc declares `cospi`/`sinpi`/`rsqrt` with an
   exception spec that conflicts with CUDA 12.8's bundled `crt/math_functions.h`.

Every one of those is a property of the user's machine, and every one of them
disappears if the compile happens once in an environment we pin. On top of the
failures, the from-source requirement forces anyone without an existing CUDA
12.8 install to download several GB of toolkit just to satisfy one build step —
on top of the ~2.5 GB of torch cu128 wheels — which is the opposite of what the
Windows user experiences.

The contributor also found the cheap way to pin a toolchain: NVIDIA ships CUDA
12.8 as component `.deb` packages (`cuda-nvcc-12-8`, `cuda-crt-12-8`,
`cuda-cccl-12-8`, `cuda-cudart-dev-12-8`) that extract with `ar`/`tar` without
root into a working nvcc at roughly 38 MB, versus 5 GB for the runfile
installer. He verified it by compiling and running an `sm_120` kernel with it.

Without this task, PoseCap has no Linux story at all: the community did the
installer work and it sits blocked on infrastructure only the maintainer can add.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] A repeatable job in this repository builds PyTorch3D from the pinned
      `v0.7.9` source against `torch 2.9.1+cu128` inside an environment whose
      CUDA toolkit and host compiler versions are pinned by us, not inherited
      from whatever machine runs it.
- [x] The job runs in CI on a clean runner, not on a maintainer's workstation,
      and produces the same wheel filename and layout the Linux payload expects.
- [ ] The wheel is checksummed and shipped inside the Linux PEAR payload, the
      same way `build_pear_payload.ps1` ships the Windows one — no wheel is
      fetched from a third-party host at user-install time. Checksumming is
      done; the payload wiring is not.
- [x] The produced wheel carries the same architecture coverage as the Windows
      matrix (`sm_70` through `sm_120`), verified by inspecting the built
      artifact rather than assumed from the build flags.
- [ ] On a real Linux machine with an NVIDIA GPU, installing the payload that
      carries this wheel passes Doctor and a real source-to-TCP PEAR inference —
      the same bar task 0032 held the Windows payload to.
- [ ] None of the three version walls above can reach an end user: installing
      the Linux payload requires no CUDA toolkit, no pinned host compiler, and
      no compilation on the user's machine.
- [ ] `doc/adr/0016-blackwell-cu128-runtime-matrix.md` states where the wheel is
      built for each supported platform, so the division between "our pipeline
      compiles" and "the user installs" is written down rather than inferred
      from two scripts.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where
applicable.

- [x] Decide the base image and record why: a manylinux-style image pinned to a
      glibc old enough to be broadly compatible and a GCC within CUDA 12.8's
      supported range.
- [x] Provision the pinned CUDA 12.8 toolchain into the image, evaluating the
      contributor's component-`.deb` extraction against the full runfile on size
      and reproducibility.
- [x] Build PyTorch3D `v0.7.9` against `torch 2.9.1+cu128` in that image and
      emit a wheel; mirror the naming and repack behaviour of
      `packaging/build_pear_payload.ps1`.
- [x] Verify the artifact's architecture coverage directly.
- [ ] Wire the job into the release pipeline so a Linux payload is produced and
      checksummed alongside the Windows one.
- [ ] Validate end to end on real Linux hardware — coordinate with the PR #98
      contributor, who has an RTX 5090 on Arch and has already run the installer
      path against a stub wheel.
- [ ] Amend ADR-0016 with the per-platform build location.
- [ ] Unblock PR #98 and say so on the thread.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-07-21

Opened to make good on a commitment already made in public: PR #98's review told
the contributor that the wheel-producing side is ours and that his PR should not
be held hostage to infrastructure that does not exist yet. That promise now has
acceptance criteria instead of living in a comment thread.

The three version walls are recorded here rather than only on the PR, because
they are the evidence for why this task exists at all — if it is ever proposed
again that users compile PyTorch3D themselves, this is the answer.

Deliberately not in scope: whether PoseCap ships a Linux release at all is a
product decision, and this task only removes the technical blocker. The
architecture-coverage criterion is stated as "verified by inspecting the
artifact" on purpose — the Windows matrix was accepted on a build-flag claim
once, and this one should not be.

### 2026-07-21 — first wheel built, architecture coverage proven from the artifact

`.github/workflows/linux-pear-wheel.yml` produced a real wheel on the fourth
dispatch (run `29846134294`, 40m41s, `conclusion: success`):
`pytorch3d-0.7.9-cp311-cp311-linux_x86_64.whl`, sha256
`07500640105e4970dc86a438e2fc3a5a75a2e89588136efa4fc6fb53985870f1`, uploaded as
a 69 MB artifact.

**Architecture coverage was read out of the compiled extension, not the build
flags.** `cuobjdump --list-elf` on `_C.cpython-311-x86_64-linux-gnu.so` inside
the wheel lists cubins for `sm_70`, `sm_75`, `sm_80`, `sm_86`, `sm_90`,
`sm_100` and `sm_120` — the same span the Windows payload carries, Blackwell
included. That is the artifact-level proof this task demanded.

Base image: `quay.io/pypa/manylinux_2_28_x86_64`, pinned by digest. Chosen
because `torch 2.9.1+cu128` ships for Linux as `manylinux_2_28_x86_64`; building
on a newer base (ubuntu-24.04, glibc 2.39) would have made our own wheel the
limiting factor and excluded distributions whose torch installs fine. The
contributor's `.deb`-component extraction was not needed — the NVIDIA `rhel8`
repository serves the pinned 12.8 components directly into this image.

Three dispatches failed first, and each failure is worth keeping:

1. **Toolchain.** NVIDIA's repository is rolling and its current `cccl` package
   *obsoletes* `cuda-cccl-12-8`, so `dnf` refused the version requested by name.
   `--setopt=obsoletes=0` is what keeps the build on the ADR-0016 toolkit. This
   is the same class of wall the contributor hit on his own machine, surfacing
   in package resolution instead of the compiler — evidence for the whole
   premise of this task.
2. **Transitive headers.** `ATen/cuda/CUDAContextLight.h` includes
   `cusparse.h`, so compiling any PyTorch3D CUDA source against torch needs
   cuSPARSE (plus cuSOLVER and cuFFT) even though PyTorch3D never calls them.
3. **`cuobjdump` ships separately from `nvcc`**, and its absence was discovered
   only after a 52-minute compile. Both it and the toolkit version are now
   asserted in the toolchain step, so a missing or drifted toolchain fails in
   about a minute rather than an hour.

Notably, **none of the three version walls that blocked the contributor on his
own machine appeared here** — which is exactly the premise of moving the
compile to our side.

Still open, and not to be mistaken for done: the wheel has never run on a GPU.
Nothing in CI can establish that, since no runner here has an NVIDIA device.
The remaining criteria — payload wiring, real Doctor plus source-to-TCP
inference on Linux hardware, and the ADR-0016 amendment — stay unchecked.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
