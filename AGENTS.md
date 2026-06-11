# AGENTS.md

## Project Overview

Clean rewrite of Corridor Digital's "Human Input Device" proof of concept: a Blender plugin that drives SMPL-X body models from live webcam pose estimation (PEAR engine) plus a physical Arduino encoder rig supplying world position/rotation. The POC at `C:\Dev\CorridorRig-Original` is read-only reference; this repo replaces it with a tested, layered implementation covering the full pipeline (addon, engine bridge, firmware, installers). Hard constraint: SMPL-X model assets carry the MPI research (non-commercial) license — never commit or redistribute them; the repo is public from day one, so git history must stay license-clean (no licensed binary ever committed, even briefly). Commercial production use of the models requires a Meshcapade license, independent of the plugin's own license.

**Stack:** Python 3.11 (addon runs in Blender's bundled interpreter; engine bridge in a uv-managed venv), Blender >= 4.2 LTS (bpy, extension platform), PyTorch + PEAR pose-estimation engine (CUDA required at runtime), pyserial, Arduino C++ (Wire/I2C).
**Entry points:** <TODO: not yet scaffolded — see Repository Layout for the planned tree>

## Setup, Build, Test

```bash
# Install (engine bridge + dev tooling)
uv sync

# Test (single file preferred over full suite)
uv run pytest tests/<file>.py
uv run pytest

# Run before any commit
uv run ruff check .
uv run ruff format .
uv run pyright
```

<TODO: pyproject.toml not yet scaffolded — first implementation task>

Addon code executes inside Blender's bundled Python: stdlib + `bpy`/`mathutils`/`numpy` only; third-party deps must be vendored in the extension wheel, never uv-installed.

## Quality Gates

Deterministic enforcement — agent cannot skip.

* Pre-commit hook (fast): <TODO: not yet wired — run /ad-hooks after scaffold>
* Pre-push hook (thorough): <TODO: not yet wired>
* CI blocks on: <TODO: not yet wired>
* Never bypass: no `--no-verify`, no skipped hooks, no deleted failing tests.

## Code Style

Only what differs from language defaults.

* ruff is the single formatter and linter; pyright must pass on engine-bridge code.
* Type hints required on all public functions; `bpy` types may use `# type: ignore` only at the Blender API boundary.
* Windows-only mechanisms (process launch/kill, directory junctions, COM ports) live behind platform adapter modules — never inline `os.system`/`shell=True` in domain code.
* IPC and serial wire formats are defined once in a shared contracts module — the POC's three divergent copies of identical preprocessing code is the anti-pattern being fixed.

## Architectural Principles

Binding decisions live in [`doc/adr/`](doc/adr/). Do not reinvent. None recorded yet — record the IPC mechanism, layering, and vendoring decisions as ADRs before implementing them.

## Repository Layout

Planned tree (POC paths in parentheses are reference only):

* `addon/` — Blender extension (POC: `addon/Human_Input_Device/`)
* `engine/` — PEAR bridge: folder watcher, live stream, single inference (POC: `PEAR/{folder_watcher,live_webcam,inference_single}.py`)
* `firmware/` — Arduino encoder-rig sketch (POC: `Arduino/multiplexer_input/`)
* `doc/adr/`, `doc/specs/`, `doc/tasks/` — decision records, feature specs, task files (ad-* kit conventions)
* `.agents/skills/`, `.claude/` — agentic-docs kit v0.17.8-beta.1, profile `mature`
* Vendored upstream PEAR research code stays out of this repo — the bridge imports it from a pinned external location. <TODO: vendoring strategy ADR>

## Commit & PR Conventions

* Commits: Conventional Commits with DCO `Signed-off-by`.
* Branches: `feat/`, `fix/`, `chore/`.
* PRs require: green CI, one review. <TODO: remote not yet created>
* Never push to `main` directly.

## Security & Privacy

* Licensed model assets (SMPL-X `.npz`/`.pkl`, PEAR checkpoints, FLAME/MANO/MHR binaries) are never committed — keep them gitignored; document expected local paths instead.
* `C:\Dev\CorridorRig-Original` is read-only reference material — never modify it.
* PEAR downloads weights from HuggingFace (`BestWJH/PEAR_models`) at first run — pin the revision when wiring the bridge.
* `torch.load(..., weights_only=False)` (a POC global monkeypatch) is forbidden — always load weights with `weights_only=True`.

## Gotchas

Real traps confirmed in the POC; each is a contract the rewrite must honor or deliberately replace via ADR.

* Engine-to-Blender IPC is file-based: `output_capture/live_pose.pkl` written via temp file + `os.replace`, consumer polls mtime on a modal timer. Consumers must tolerate partial and duplicate updates.
* Pose payload `transl` is the camera matrix translation, not true SMPL-X translation; the POC compensates with a 180-degree X rotation (`smplx_import_flip_pear`).
* Arduino protocol: 8 comma-separated floats per CRLF line at 115200 baud, no framing or checksum; unplugged encoders silently repeat their last cumulative value.
* The hardware rig drives only object-level location/rotation of a chosen target object; body pose comes exclusively from the engine. "Rig" in CorridorRig means the physical encoder rig.
* PEAR calls `.cuda()` unconditionally — CPU-only machines crash at runtime regardless of the install-time CPU fallback.
* Blender 5.x changed action slots/channelbags — keyframe code needs version compat branches (POC: `operators/keyframes.py:84-97`).
* POC addon bugs not to replicate: double class unregister on disable, dead unregistered operators (export/animation), webcam enumeration ignoring the engine-path preference, unbounded `modal_log.txt` growth.
