# GUIDELINES.md

Full engineering reference for PoseCap. Distilled non-negotiables live in [`AGENTS.md`](AGENTS.md); system structure lives in [`ARCHITECTURE.md`](ARCHITECTURE.md); individual decisions live in [`doc/adr/`](doc/adr/).

**Project tradeoff statement:** a working install on the first try beats everything — when an engineering choice trades setup simplicity against elegance, performance headroom, or implementation convenience, setup simplicity wins. The POC's environment (source-compiled PyTorch3D, conda-name probing, manual junctions) is the cautionary tale.

## 1. Architecture Binding

Hexagonal, per [`ARCHITECTURE.md`](ARCHITECTURE.md). Operational consequences:

* Dependency rule is testable: `contracts/` imports stdlib only; `core/` imports stdlib + numpy + `contracts/`; `addon/` and `engine/` import inward only. Enforced by import-linter contract in CI once scaffolded — not by review memory.
* New capability lands as: port defined in `core/`, adapter at the edge, wire format in `contracts/`. No third place.
* `bpy`, `torch`, `serial`, sockets, and filesystem APIs never appear in `contracts/` or `core/`. A PR that adds one is rejected regardless of how convenient it is.

## 2. Code Style

### 2.1 Naming

| Element | Convention |
|---|---|
| modules, packages, functions, variables | `snake_case` |
| classes, exceptions, protocols | `PascalCase` |
| constants | `UPPER_SNAKE` |
| Blender operator `bl_idname` | `posecap.<verb>_<noun>` |
| test files | `test_<module>.py`, mirroring the source tree |

* No abbreviations: `connection` not `conn`, `multiplexer` not `mux` (except established domain acronyms: `smplx`, `fps`, `tcp`, `json`).
* The driven skeleton is "armature" or "body model" in code and UI copy — never "rig" (reserved word from the dropped hardware era; avoid it entirely).

### 2.2 Error handling

* Exception hierarchy rooted at one domain base per package (`PoseCapError` in `core/`); adapters raise subclasses, never bare `Exception`.
* `bpy` edge translates domain errors to `Operator.report({'ERROR'}, ...)` + `{'CANCELLED'}`. Engine edge logs structured and writes the job status file. No traceback ever reaches a user-facing surface unformatted.
* No bare `except:`; no `except Exception: pass`. Catch what you can handle; let the rest propagate to the edge.
* Exceptions are for failures, not control flow. Expected absence returns `None` or a typed result, documented in the signature.

### 2.3 Module surface

* Public API of each package is what its `__init__.py` exports; everything else is private by convention (`_prefix` for module-internal helpers).
* Docstrings on public functions state behavior and units (degrees vs radians, meters vs millimeters) — the POC's magic 0.001/0.01 scalars existed because units were undocumented.

## 3. Object Calisthenics

Tier: **moderate**, with `contracts/` and `core/` aiming for strict where practical.

* [x] 1. One level of indentation per method (guideline, cap enforced by §4)
* [x] 2. No `else` keyword — early returns and guard clauses
* [x] 3. Wrap primitives that carry meaning (channel index, COM port, frame timestamp are types/dataclasses in `contracts/`, not loose ints/strings)
* [x] 4. First-class collections (a pose sequence is a class, not a bare list)
* [ ] 5. One dot per line (strict-only; applied opportunistically in `core/`)
* [x] 6. No abbreviations (§2.1)
* [x] 7. Small entities (§4 caps)
* [ ] 8. Max two instance variables (strict-only; exempt in `bpy` PropertyGroups and adapter classes)
* [ ] 9. No getters/setters (strict-only; exempt at `bpy` and dataclass boundaries)

Exemption is structural, not discretionary: rules 8/9 do not apply where `bpy` API shape dictates the class layout.

## 4. Complexity Discipline

* Cognitive complexity ≤15 per function (ruff `C901`).
* Functions: ~50 lines target, 100 hard cap.
* Files: ~200 lines target.
* Max indentation depth 3.
* Exceeding a cap is a refactor trigger, not a waiver request. If a function genuinely cannot shrink (single dispatch table, exhaustive match), a one-line comment states why.

## 5. Performance Standards

Budget (binding, from [PRD](doc/product/PRD.md)): 30 FPS pose application, <100 ms capture-to-viewport latency, RTX-class GPU.

* Hot paths: engine inference loop, addon timer callback, TCP frame decode.
* No per-frame allocations on hot paths — preallocate and reuse numpy buffers; no string formatting, no disk I/O, no logging above DEBUG inside the per-frame path.
* Frame-time instrumentation is mandatory: engine logs inference FPS at INFO on an interval; addon logs apply-time the same way. The latency metric is measured from these stamps, not estimated.
* Regression rule: a change that increases steady-state frame time by more than 10% needs a recorded justification before merge.

## 6. Build System

* Python 3.11, `pyproject.toml` is the source of truth, uv manages everything (`uv sync`, `uv run`). uv workspace: `contracts/`, `core/`, `engine/` as members; the addon is assembled by the extension build script which vendors `contracts/` + `core/` into the wheel.
* `uv.lock` is committed. Dependency additions are PR-visible events, not side effects.
* Setup-simplicity rules (the tradeoff statement, applied):
  * No source-compiled dependencies unless no wheel exists. If unavoidable (PyTorch3D for PEAR), the install script gates it explicitly, reports progress, and fails with a actionable message — never a raw compiler error.
  * Installer must succeed on a machine with nothing but Windows, an NVIDIA driver, and Blender. Everything else is fetched or bundled.
  * Version pins favor "known working" over "latest"; the lockfile is the compatibility statement.

## 7. Static Analysis

| Tool | Role | Config |
|---|---|---|
| ruff | lint + format (single tool, no black/isort) | `[tool.ruff]` in pyproject.toml |
| pyright | type check — strict on `contracts/` and `core/`, standard on `addon/` and `engine/` | `[tool.pyright]` in pyproject.toml |
| import-linter | hexagonal dependency contracts (§1) | `[tool.importlinter]` in pyproject.toml |
| ruff C901 / mccabe | complexity caps (§4) | same ruff config |

`# type: ignore` allowed only at the `bpy` API boundary, with the reason on the same line.

## 8. Quality Gates

Wired via pre-commit (`.pre-commit-config.yaml`; install once with `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`):

* Pre-commit (fast): `ruff check`, `ruff format --check`, private-key detection, large-file cap (5 MB), licensed-binary block (`tools/check_licensed_binaries.py` — no `.npz`/`.pkl`/`.pt`/`.ckpt`/`.onnx`/`.engine` ever staged).
* Pre-push (thorough): `pyright`, `pytest` (default tags), import-linter.
* CI (`.github/workflows/ci.yml`): full gate matrix on Linux and Windows (ruff, format, pyright, import-linter, pytest with a 90% coverage floor on contracts/core), licensed-binary tree scan, and `pip-audit` over the exported lockfile. Runs on every PR and on `main`. `gpu`/`e2e`/`eval` tags stay local until a GPU runner exists.
* Never bypass: no `--no-verify`, no skipped hooks, no deleted failing tests.

## 9. Testing Strategy

* Framework: pytest. Single-file runs preferred during development (`uv run pytest tests/core/test_retarget.py`).
* `contracts/` and `core/` are pure — tested without Blender, GPU, camera, or hardware. High coverage expected (target 90%); this is where the domain logic lives, so this is where the tests live.
* Contract tests pin wire formats: golden JSON fixtures for pose payloads and job status files. A wire-format change that breaks a golden fixture is a breaking change and says so in the commit.
* `engine/` integration tests run against recorded frames (fixture video/images), never a live camera. GPU-dependent tests carry the `gpu` tag and skip cleanly when CUDA is absent.
* `addon/` logic stays thin enough that most of it is tested through `core/`; Blender-dependent smoke tests run via `blender --background --python` and carry the `e2e` tag.
* Tag taxonomy: `unit` (default, untagged), `integration`, `e2e`, `gpu`, `slow`, `eval`. CI selects by tag; the default local run excludes `gpu`, `e2e`, and `eval`.
* `eval` tier — pose-accuracy runs against self-made golden samples (rendered SMPL-X animations with known parameters). Metric-and-tolerance comparison (per-joint position error, joint-angle error, temporal jitter), never exact equality — model output shifts across GPU/driver/torch versions. Baseline first, threshold second: eval runs on demand or nightly and never gates CI before a recorded baseline exists. The engine is evaluated in isolation (frames in, parameters out); the end-to-end Blender layer is a separate, thinner check. Ground-truth data is always self-made — research mocap datasets carry restricted licenses and never enter the repo.
* Tests verify behavior through public interfaces. No test reaches into private state; if it must, the module surface is wrong — fix that instead.

## 10. Git Workflow

* Conventional Commits 1.0.0 + DCO `Signed-off-by` (use `/ad-commit`). No `Co-Authored-By` trailers.
* Branches: `feat/`, `fix/`, `chore/`; `main` is protected once a remote exists — PRs via `/ad-pr`, merge via `/ad-merge`.
* Atomic commits: one concern each. Mixed-concern diffs get stage-split, not bundled.
* Line endings: LF in repo (`.gitattributes` with `* text=auto eol=lf` — to be added with the scaffold).

## 11. Documentation

| File | Scope | Owner skill |
|---|---|---|
| `README.md` | public entry: what, who for, compatibility | manual |
| `AGENTS.md` | distilled operational rules, read every session | `/ad-bootstrap` |
| `GUIDELINES.md` | this file — full engineering reference | `/ad-guidelines` |
| `ARCHITECTURE.md` | binding system patterns | `/ad-architecture` |
| `doc/product/PRD.md` | product scope, metrics, roadmap | `/ad-prd` |
| `doc/specs/` | one feature per spec | `/ad-spec` |
| `doc/tasks/` | work items, checkbox + append-only notes | `/ad-task` |
| `doc/adr/` | one decision per ADR | `/ad-adr` |
| `doc/reference/` | third-party papers and upstream docs | manual |

Discipline: no emoji, no dates in narrative prose, no speculation, definitions and decisions only. Duplication between AGENTS.md and this file is drift — `/ad-audit` flags it.

## 12. Security

* Untrusted inputs and their boundaries: user-dropped image files (extension + size validated before the engine touches them), webcam frames (engine-internal), TCP JSON frames (schema-validated on decode per ARCHITECTURE.md), downloaded model weights (pinned HuggingFace revision, `torch.load(..., weights_only=True)` always — `weights_only=False` is banned).
* Pickle is banned for IPC and persistence. JSON or documented binary formats only.
* `subprocess` calls never use `shell=True`; process teardown by handle/PID, never by window title.
* No secrets exist in this project by design; if one ever appears (API token, license key) it lives in an env var or OS keychain, gitignored, never committed — history is permanent and the repo goes public.
* Licensed model assets never enter the repo (gitignore + planned CI scan). `C:\Dev\CorridorRig-Original` is read-only reference.
* Dependency audit: `pip-audit` against `uv.lock` in CI.
