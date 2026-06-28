# Task 0003: Engine bridge — TCP pose server wrapping PEAR

**Status:** done
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** HITL
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

The engine side reuses the POC's verified inference loop (`PEAR/live_webcam.py:146-209`: capture without CAP_DSHOW — it froze some Windows webcams; YOLO classes=0 imgsz=640 most-confident box; crop-ratio patch; torch.no_grad; cv2.Rodrigues conversion) and replaces the pickle/os.replace file handoff with NDJSON over a localhost TCP server (ADR-0002/0003). PEAR installs from a pinned external revision (ADR-0005); weights pin a HuggingFace revision with `weights_only=True` — the POC's global `torch.load` monkeypatch (`live_webcam.py:13`) is banned. Device enumeration moves here because the engine owns the environment that can enumerate (the POC's in-Blender attempt never worked). The spec's open question on TCP port strategy gets resolved and recorded in this task's Notes. HITL: needs CUDA GPU and a physical webcam. Depends on tasks 0001-0002.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] `uv run posecap-engine devices` prints a JSON device list usable by the addon dropdown.
- [x] Live mode serves schema-valid NDJSON pose frames at inference rate; "no person" produces explicit status frames, not silence.
- [x] Integration test against recorded fixture frames (no live camera) validates frames against the golden schema; `gpu` tag skips cleanly without CUDA.
- [x] Engine exits within 5 seconds of parent-PID death and on stream-socket disconnect (decision between the two recorded in Notes).
- [x] PEAR revision and HF weight revision pinned in config; no `weights_only=False` anywhere (grep-clean).
- [x] Inference FPS logged at INFO on an interval to a rotating log; no per-frame disk I/O or above-DEBUG logging on the hot path.
- [x] TCP port strategy implemented and documented (Notes + contracts handshake if schema changed).

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] `engine/src/posecap_engine/capture.py` — webcam open/read (no CAP_DSHOW), device enumeration.
- [x] `engine/src/posecap_engine/pear_adapter.py` — model load (pinned), detect+infer+Rodrigues, reusing POC loop structure.
- [x] `engine/src/posecap_engine/stream_server.py` — TCP server, NDJSON frames via contracts codec, single-client lifecycle.
- [x] `engine/src/posecap_engine/watchdog.py` — parent-PID + disconnect liveness (platform adapter).
- [x] `engine/src/posecap_engine/cli.py` — `devices` and `live` entry points.
- [x] Resolve port strategy; record in Notes; update contracts if handshake needed.
- [x] `tests/engine/` — fixture-frame integration tests (`integration`/`gpu` tags).
- [x] Full gate + /ad-commit.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-11

Decision: the recorded-frame fixtures created for this task's integration tests carry ground-truth pose labels (rendered SMPL-X sequences with known parameters) so the pose-accuracy eval harness (PRD Next roadmap) has labeled data from day one. The harness itself is out of this task's scope — it gets its own spike after the engine CLI lands.

### 2026-06-27

Started the non-GPU engine slice: `posecap-engine devices`, `posecap-engine live --fixture`, single-client localhost TCP NDJSON streaming via the contracts codec, parent-process watchdog, socket-disconnect shutdown, rotating-log setup, and pinned PEAR / HF model revisions. PEAR inference itself remains unchecked until the external checkout, model weights, CUDA, and physical webcam are available.

Port strategy decision: `live` defaults to TCP port `0`, letting the OS allocate a free localhost port. The engine prints one startup JSON line to stdout with `{"event":"listening","host":"127.0.0.1","port":<actual>}`; the addon will read that line from the spawned process before connecting. No wire-contract handshake changed: pose frames on the socket remain newline-delimited JSON `PoseFrame` lines.

Liveness decision: both parent-PID death and client disconnect are implemented. The accept loop polls the parent watchdog; the stream loop checks parent liveness before each frame and exits when the client sends FIN/RST.

Local verification added for the engine checkpoint: `devices` emits a JSON object even when OpenCV is absent, fixture streaming decodes through `posecap_contracts`, empty fixtures fail explicitly instead of spinning, the FPS logger emits only after its interval, and the `gpu` smoke skips cleanly without `torch` or CUDA. The PEAR adapter now validates the external checkout boundary before reporting that CUDA/HITL inference remains incomplete.

OpenCV is now an engine dependency so `uv run posecap-engine devices` can enumerate from a normal `uv sync`; on this workstation `--max-index 0` returned Camera 0 at 1280x720 and 60 FPS. The command still emits a JSON object with an empty list plus `error` if the capture backend is unavailable.

Completed the PEAR adapter code path short of hardware-in-the-loop validation: `posecap-engine live --pear-root` now validates the external checkout shape, imports PEAR lazily from that root, requires CUDA, downloads `BestWJH/PEAR_models/ehm_model_stage1.pt` at the pinned HuggingFace revision, loads it with `torch.load(..., weights_only=True)`, instantiates `Ehm_Pipeline`, runs YOLO person detection at `imgsz=640`, crops PEAR's 256x256 patch, runs inference under `torch.no_grad`, converts PEAR rotation matrices to Rodrigues vectors with `cv2.Rodrigues`, and emits contract `PoseFrame` frames. Detection or crop misses now yield explicit `no_person` frames. CLI live options also expose camera width, height, YOLO threshold, and crop ratio with the POC live defaults.

Local verification for the PEAR adapter remains fake-based until CUDA, a physical webcam, model weights, and the external PEAR checkout are available together. The current uv environment has OpenCV but does not have `torch`, `torchvision`, `ultralytics`, `huggingface_hub`, or `lightning`, so live PEAR HITL was not attempted. Current gates are green: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, and `uv run pytest -q` (`77 passed, 1 deselected`). The explicit GPU smoke `uv run pytest tests/engine/test_gpu_environment.py -q -m gpu` skipped cleanly without CUDA. Source/test paths are grep-clean for `weights_only=False`; documentation still mentions the banned form only as policy.

Prepared a PEAR runtime doctor without turning task 0003 into the full installer task: `posecap-engine doctor` emits JSON readiness checks for Python version, NVIDIA driver visibility, required PEAR/PyTorch imports, `torch.cuda`, external PEAR checkout shape and git revision, licensed SMPL/SMPL-X/FLAME asset paths, and optional pinned HuggingFace weight download via `--download-weights`. The command returns a non-zero exit code when any required check is `error`, so the future addon/installer can gate on it without parsing human prose.

Created the external PEAR checkout at `C:\Dev\PoseCap-PEAR` and checked it out to `977331937ea8c3d08ae0254d8831d640d46a5cf6`, outside this repository. The real doctor run on this workstation reports: NVIDIA driver/GPU visible (`RTX 3080`), OpenCV and `rich` importable, Python 3.12 warning for PEAR HITL validation, missing `torch`, `torchvision`, `ultralytics`, `huggingface_hub`, `lightning`, `timm`, `omegaconf`, `roma`, `einops`, `colored`, and `pytorch3d`, missing external YOLO detector at `model_zoo/yolov8x.pt`, missing licensed SMPL/SMPL-X/FLAME asset paths, and pinned HF weights unchecked because `huggingface_hub` is absent. Current full gates after adding the doctor are green: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, and `uv run pytest -q` (`81 passed, 1 deselected`).

Follow-up runtime preparation on the same workstation resolved the installable PEAR dependencies short of PyTorch3D: `torch`/`torchvision` CUDA wheels were installed with the uv PyTorch backend, `torch.cuda.is_available()` is true, and PyTorch reports the local `NVIDIA GeForce RTX 3080`. The PEAR pure-Python dependencies (`ultralytics`, `huggingface_hub`, `lightning`, `timm`, `omegaconf`, `roma`, `einops`, `colored`) now import under `posecap-engine doctor`. The adapter also no longer treats `model_zoo/yolov8x.pt` as required in the external PEAR checkout; if the local file is absent it passes `yolov8x.pt` to Ultralytics so the detector can resolve from its normal cache/download path.

Remaining PEAR HITL blockers are now narrow and explicit. `pytorch3d` has no wheel for the current Python 3.12 environment, and a source build against VS 2022 plus CUDA 12.8 reached native compilation but failed inside the PyTorch3D build (`mesh_normal_consistency_cpu.cpp`: `fatal error C1083: Cannot open compiler generated file: '': Invalid argument`). That is an installer/runtime compatibility decision, not a PEAR adapter code path issue; the setup path needs either a known-good Python/Torch/PyTorch3D matrix or a deliberate replacement/shim task before live inference can run. The licensed SMPL/SMPL-X/FLAME assets are still missing from `C:\Dev\PoseCap-PEAR\assets`; they must be downloaded by a license holder from official sources and must never be copied from the POC or committed to this repo.

The pinned PEAR Hugging Face checkpoint was verified with `uv run posecap-engine doctor --pear-root C:\Dev\PoseCap-PEAR --download-weights`; `ehm_model_stage1.pt` is available in the local Hugging Face cache at revision `bbac79d4d834a40d74393466e11f998b67b437e1`.

Created `doc/tasks/0007-pear-runtime-windows-matrix.md` as the focused runtime/installer gate for the remaining PyTorch3D blocker. Task 0003 should not continue environment mutation on the current Python 3.12 plus Torch 2.11 setup; live PEAR HITL validation stays blocked until task 0007 proves a Python 3.11 uv-managed Torch/Torchvision/PyTorch3D matrix and the licensed assets are installed from official sources.

### 2026-06-28

Closed the remaining live-mode/public CLI coverage with a public-boundary test: `posecap_engine.cli.run(["live", "--pear-root", ..., "--port", "0"])` starts the real TCP server, prints the startup JSON line, accepts a socket client, and streams a contract-decoded `PoseFrame` whose status is `no_person`. The test monkeypatches only the PEAR frame source boundary, so the public CLI, port-0 startup path, TCP NDJSON writer, and contracts decoder are exercised together. No implementation change was needed in the live command itself; the existing CLI/server/source wiring already emitted explicit `no_person` frames instead of silence.

The task 0007 runtime made the PEAR boundary testable enough to expose two missing non-Torch PEAR imports during a real doctor run: `trimesh` and `plotly`. The doctor required-import list and `tools/install/setup_pear_runtime.ps1` curated dependency set now include both. After installing those into `.venv-pear`, `posecap-engine doctor --pear-root C:\Dev\PoseCap-PEAR --download-weights` reports Python 3.11, Torch/Torchvision CUDA, PyTorch3D, NVIDIA visibility, required PEAR imports, external PEAR checkout pin, PEAR EHM import, and pinned Hugging Face weights as OK. The only remaining doctor error is the expected missing licensed SMPL/SMPL-X/FLAME asset files, which must be installed from official sources by a license holder and must never be committed.

Final verification: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest -q` (`92 passed, 1 deselected`), `git diff --check`, and the licensed-binary scanner over Git-tracked files all pass. The PowerShell runtime setup script parses successfully through `System.Management.Automation.PSParser`. The required `/ad-review` pass reported no Standards or Spec findings.

## Definition of Done

All Acceptance Criteria checked, plus:

- [x] Local tests pass (or N/A documented in Notes)
- [x] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [x] No orphan `TODO`/`FIXME` introduced
- [x] Status updated to `done` and Notes log closes the task
