# Task 0007: Validate PEAR Windows runtime matrix

**Status:** done
**Created:** 2026-06-27
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

Task 0003 has the PEAR adapter and `posecap-engine doctor` path in place, but live
hardware validation is blocked by PyTorch3D on Windows. The current Python 3.12 plus
Torch 2.11 environment is not the project install target and should not receive more
ad-hoc mutation. This task selects a small, reproducible runtime matrix before the
broader installer and end-to-end verification work in task 0006, while preserving
ADR-0004's uv workspace rule and ADR-0005's external pinned PEAR boundary.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] A scripted setup path creates or updates a Python 3.11 uv-managed PEAR engine
      runtime without copying PEAR source or licensed assets into this repository.
- [x] The Windows runtime matrix is recorded in ADR-0007: Python 3.11, Torch
      `2.4.1+cu124`, torchvision `0.19.1+cu124`, CUDA Toolkit `v12.8`, and
      PyTorch3D `v0.7.9` built from a short local checkout.
- [x] PyTorch3D installation is owned by the script or doctor workflow, with captured
      logs and actionable failure messages instead of raw compiler output.
- [x] `posecap-engine doctor --pear-root C:\Dev\PoseCap-PEAR --download-weights`
      reports Python 3.11, NVIDIA visibility, Torch CUDA, PEAR import dependencies,
      PyTorch3D importability, pinned PEAR checkout, and pinned Hugging Face weights.
- [x] Missing SMPL/SMPL-X/FLAME assets are reported only as explicit licensed-asset
      failures until a license holder installs them from official sources.
- [x] No `.pkl`, `.npz`, `.pt`, `.ckpt`, `.onnx`, `.engine`, or PEAR checkout files
      are staged in this repository.
- [x] Conda/Python 3.9 and PyTorch3D shim paths remain rejected unless a future ADR
      supersedes ADR-0007.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add a focused runtime setup script under `tools/install/` for the Python 3.11
      uv environment, Torch/Torchvision CUDA wheels, and controlled PyTorch3D install.
- [x] Extend `engine/src/posecap_engine/doctor.py` only as needed to report exact
      Python, Torch, torchvision, CUDA, and PyTorch3D versions in machine-readable JSON.
- [x] Run the script against `C:\Dev\PoseCap-PEAR` with the ADR-0007 matrix and record
      the exact command log in Notes.
- [x] Run the doctor with `--download-weights`; record the JSON summary and identify
      whether the only remaining blocker is licensed assets.
- [x] Draft the required ADR before any conda/Python 3.9 path or PyTorch3D shim lands.
- [x] Feed the validated runtime path into task 0006's installer work once this task
      has a chosen matrix.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-27

Created from the task 0003 handoff and its recorded grounding result: stop random
installation attempts in the current Python 3.12 plus Torch 2.11 environment. The
candidate path stayed aligned with the project rules first: Python 3.11, uv-managed
runtime, Torch/Torchvision 2.4.1/0.19.1, CUDA 12.4 or 12.1, PEAR external at
`C:\Dev\PoseCap-PEAR`, PyTorch3D built or diagnosed through a controlled script, and
`posecap-engine doctor` as the readiness gate. Deviations to conda/Python 3.9 or a
PyTorch3D shim require an ADR before implementation.

Added `tools/install/setup_pear_runtime.ps1` as the controlled Windows setup entry
for the Python 3.11 PEAR runtime. The script creates a dedicated `.venv-pear`
environment, installs PoseCap workspace packages editably, installs the requested
Torch/Torchvision CUDA matrix, installs curated PEAR Python dependencies without
consuming PEAR's older Torch-pinning requirements file, attempts PyTorch3D from the
pinned upstream tag `v0.7.9`, logs to `.agentic/pear-runtime/`, and runs
`posecap-engine doctor --download-weights` at the end. The default venv path is now
gitignored.

Extended `posecap-engine doctor` with a `runtime_versions` check that reports the
exact Python executable/version, Torch version, Torch CUDA build version, torchvision
version, and PyTorch3D version when those modules are importable. The check remains
machine-readable JSON so task 0006's installer can gate on it later.

First controlled CUDA 12.4 script invocation:
`powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\install\setup_pear_runtime.ps1 -Cuda 12.4 -PearRoot 'C:\Dev\PoseCap-PEAR'`.
The script failed before creating or mutating the runtime venv because `cl.exe` is
not available in the current shell. The captured log is
`.agentic\pear-runtime\setup-pear-runtime-cu124-20260627T205034.log`. CUDA 12.1 was
not attempted because the failure is the shared Visual Studio compiler prerequisite,
not a CUDA matrix-specific build result.

Local verification for this slice: the PowerShell script parses successfully, `uv run
ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest
tests/engine/test_doctor.py tests/engine/test_cli.py tests/engine/test_pear_adapter.py
-q` (`17 passed`), and `git diff --check` all pass.

Host prerequisite check: Visual Studio's `VsDevCmd.bat` exists at
`C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat`,
but the installed CUDA Toolkit directories are only `v12.8` and `v12.9`. Before
ADR-0007, the task matrix called for CUDA 12.4 first and CUDA 12.1 as the only
fallback before an ADR-backed runtime policy change.

A diagnostic build then used Torch/Torchvision cu124 wheels and
`CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8`. ADR-0007 now
records this as the Windows runtime matrix.

The first diagnostic run with `CUDA_HOME=v12.8` installed Python 3.11, PoseCap
workspace packages, Torch `2.4.1+cu124`, torchvision `0.19.1+cu124`, and PEAR's
Python dependencies, then failed before native PyTorch3D compilation because
`setuptools` was absent under `--no-build-isolation`. The setup script now installs
`setuptools` and `wheel` before the PyTorch3D build.

The second diagnostic run exposed that `uv venv` refuses to recreate an existing
`.venv-pear` without `--clear`; the setup script now reuses an existing venv when
`Scripts\python.exe` is present.

The third diagnostic run reached native PyTorch3D compilation through uv's Git cache
and failed at `mesh_normal_consistency_cpu.cpp` with `fatal error C1083: Cannot open
compiler generated file: '': Invalid argument`, matching the earlier Windows source
build blocker.

The fourth diagnostic run cloned PyTorch3D `v0.7.9` into the shorter ignored path
`.agentic\p3d` and installed from that local checkout. PyTorch3D built and installed
successfully after 14 minutes 21 seconds. The final doctor JSON reports Python
`3.11.13`, Torch `2.4.1+cu124`, Torch CUDA build `12.4`, torchvision `0.19.1+cu124`,
PyTorch3D `0.7.9`, NVIDIA RTX 3080 visibility, Torch CUDA available, all required
PEAR imports present, external PEAR checkout at revision
`977331937ea8c3d08ae0254d8831d640d46a5cf6`, and pinned Hugging Face weights present.
The only remaining doctor error is missing licensed SMPL/SMPL-X/FLAME assets under
`C:\Dev\PoseCap-PEAR\assets`, which must be installed from official sources and never
committed. Log:
`.agentic\pear-runtime\setup-pear-runtime-cu124-20260627T210234.log`.

Created ADR-0007 to record the runtime matrix that actually built on Windows:
Python 3.11, Torch `2.4.1+cu124`, torchvision `0.19.1+cu124`, CUDA Toolkit `v12.8`,
PyTorch3D `v0.7.9`, and a script-owned short local PyTorch3D checkout. Conda,
Python 3.9, and PyTorch3D shim paths remain rejected unless a future ADR supersedes
ADR-0007.

Git staging check after the diagnostic run: no files are staged; `git status
--short --untracked-files=all` shows no `.pkl`, `.npz`, `.pt`, `.ckpt`, `.onnx`, or
`.engine` files. `.agentic/` and `.venv-pear/` are ignored.

Post-run verification: `uv run ruff check .`, `uv run ruff format --check .`,
`uv run pyright`, `uv run pytest tests/engine/test_doctor.py tests/engine/test_cli.py
tests/engine/test_pear_adapter.py -q` (`17 passed`), `git diff --check`, and the
licensed-binary scanner over visible Git files all pass.

Final verification after ADR-0007 and task 0006/spec linkage: the PowerShell setup
script parses successfully; `uv run ruff check .`, `uv run ruff format --check .`,
`uv run pyright`, `uv run pytest tests/engine/test_doctor.py tests/engine/test_cli.py
tests/engine/test_pear_adapter.py -q` (`17 passed`), `git diff --check`, and the
licensed-binary scanner over visible Git files all pass. A direct doctor run from
`.venv-pear` confirms the ADR-0007 runtime is ready and still reports only missing
licensed SMPL/SMPL-X/FLAME assets as an error. No source `TODO` or `FIXME` markers
were introduced.

### 2026-06-28

Post-review TDD pass grounded the runtime-readiness fixes before implementation. The
doctor gate now verifies required PEAR imports with real `import_module()` calls so a
module found by `find_spec()` but failing at import time reports an actionable error
instead of a false OK. The PEAR live frame source now fails with `CaptureUnavailableError`
after bounded consecutive camera read failures and releases the capture, preventing a
silent infinite loop when OpenCV returns no frames. A broader stream-server thread/queue
redesign was deliberately left out of this GREEN phase; the reviewed blocker was the
`read_rgb() is None` spin, and a concurrency redesign should be its own task if OpenCV
itself blocks inside `read()`. The final pre-merge hardening pass also made the doctor
verify the external PEAR checkout modules, report `find_spec()` discovery failures as
JSON errors, and catch `OSError` from the Torch CUDA check instead of leaking a
traceback.

Task 0003 close-out exposed two additional non-Torch PEAR imports required by the
external EHM pipeline import path: `trimesh` from `utils.graphics_utils` and `plotly`
from `utils.pipeline_utils`. The doctor required-import list and
`tools/install/setup_pear_runtime.ps1` curated dependency set now include both. After
installing them into `.venv-pear`, the direct doctor run reports the Python 3.11
runtime, Torch/Torchvision CUDA matrix, PyTorch3D, PEAR imports, external PEAR pin,
and pinned Hugging Face weights as OK; the only remaining doctor error is missing
licensed SMPL/SMPL-X/FLAME assets.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW Â§10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
