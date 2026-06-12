# AGENTS.md

## Project Overview

PoseCap (clean rewrite of Corridor Digital's "Human Input Device" proof of concept): a Blender plugin that drives SMPL-X body models from live webcam pose estimation (PEAR engine), pelvis-locked — world position is a deferred software problem, and the POC's Arduino rig is dropped from scope. The POC at `C:\Dev\CorridorRig-Original` is read-only reference; this repo replaces it with a tested, layered implementation (addon, engine bridge, installers). Hard constraint: SMPL-X model assets carry the MPI research (non-commercial) license — never commit or redistribute them; the repo is private now but goes public later, so git history must stay license-clean from the first commit (no licensed binary ever committed, even briefly). Commercial production use of the models requires a Meshcapade license, independent of the plugin's own license.

**Stack:** Python 3.11 (addon runs in Blender's bundled interpreter; engine bridge in a uv-managed venv), Blender >= 4.2 LTS (bpy, extension platform), PyTorch + PEAR pose-estimation engine (CUDA required at runtime).
**Entry points:** uv workspace packages `contracts/`, `core/`, `engine/` (src layout, `posecap_*` import names). Engine CLI lands with task 0003; the Blender extension lands with task 0004.

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

Quality gates run as: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run pytest`.

Addon code executes inside Blender's bundled Python: stdlib + `bpy`/`mathutils`/`numpy` only; third-party deps must be vendored in the extension wheel, never uv-installed.

## Quality Gates

See [`GUIDELINES.md`](GUIDELINES.md) §8 for the full reference. Non-negotiable subset:

* Hooks wired via pre-commit; new clones run `uv run pre-commit install --hook-type pre-commit --hook-type pre-push` once.
* Never bypass: no `--no-verify`, no skipped hooks, no deleted failing tests.

## Code Style

See [`GUIDELINES.md`](GUIDELINES.md) §2–§4 for the full reference. Non-negotiable subset:

* ruff is the single formatter and linter; pyright strict on `contracts/`/`core/`; `# type: ignore` only at the `bpy` boundary with reason inline.
* `bpy`, `torch`, `serial`, sockets, filesystem never imported in `contracts/` or `core/` (GUIDELINES §1 dependency rule).
* Wire formats defined once in `contracts/` — never duplicated per consumer.

## Architectural Principles

Binding decisions live in [`doc/adr/`](doc/adr/). Do not reinvent. Six accepted: hexagonal layers + dependency rule (0001), TCP JSON IPC (0002), JSON wire format / pickle ban (0003), uv workspace vendoring (0004), PEAR external + pinned (0005), license split (0006).

## Repository Layout

Planned tree (POC paths in parentheses are reference only):

* `addon/` — Blender extension (POC: `addon/Human_Input_Device/`)
* `engine/` — PEAR bridge: folder watcher, live stream, single inference (POC: `PEAR/{folder_watcher,live_webcam,inference_single}.py`)
* `doc/adr/`, `doc/specs/`, `doc/tasks/` — decision records, feature specs, task files (ad-* kit conventions)
* `.agents/skills/`, `.claude/` — agentic-docs kit v0.17.8-beta.1, profile `mature`
* Upstream PEAR research code stays out of this repo — the bridge imports it from a pinned external location (ADR-0005); shared-package vendoring strategy in ADR-0004.

## Commit & PR Conventions

See [`GUIDELINES.md`](GUIDELINES.md) §10 for the full reference. Non-negotiable subset:

* Conventional Commits + DCO `Signed-off-by`, atomic concerns (use `/ad-commit`).
* Never push to `main` directly once a remote exists.

## Security & Privacy

See [`GUIDELINES.md`](GUIDELINES.md) §12 for the full reference. Non-negotiable subset:

* Licensed model assets never committed — gitignored; history must stay publishable.
* `C:\Dev\CorridorRig-Original` is read-only reference material — never modify it.
* `torch.load(..., weights_only=False)` and pickle IPC are banned.

## Gotchas

Real traps confirmed in the POC; each is a contract the rewrite must honor or deliberately replace via ADR.

* POC engine-to-Blender IPC was file-based (`output_capture/live_pose.pkl` via temp file + `os.replace`, mtime polling) and delivered every pose twice — deliberately replaced by the TCP JSON stream (ADR-0002); do not reintroduce file polling. The lesson carries over: the consumer must tolerate duplicate and partial frames.
* Pose payload `transl` is the camera matrix translation, not true SMPL-X translation; the POC compensates with a 180-degree X rotation (`smplx_import_flip_pear`).
* World position: poses apply pelvis-locked. The POC's Arduino world-input was dropped from scope (Dean, product review) — do not resurrect it; the future approach is software (camera tracking).
* PEAR calls `.cuda()` unconditionally — CPU-only machines crash at runtime regardless of the install-time CPU fallback.
* Blender 5.x changed action slots/channelbags — keyframe code needs version compat branches (POC: `operators/keyframes.py:84-97`).
* POC addon bugs not to replicate: double class unregister on disable, dead unregistered operators (export/animation), webcam enumeration ignoring the engine-path preference, unbounded `modal_log.txt` growth.
* The POC bundles licensed MPI assets (SMPL-X blends in addon `data/`, PEAR asset pack with FLAME/MANO). Never copy files out of `CorridorRig-Original` into this repo — reimplement code, fetch assets from official sources locally.
* POC Record Live MoCap silently records nothing when the Preview toggle is off (insertion nested in the preview branch). The rewrite decouples recording from preview.
* POC live stream threw 6,670 "StructRNA removed" errors when the armature was deleted mid-stream. Validate object references every frame; degrade gracefully.
* The POC's documented `.venv` install path was never proven — all run traces point to a conda env (`pear10`). Treat install scripts as untested until run on a clean machine.
