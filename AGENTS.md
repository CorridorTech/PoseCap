# AGENTS.md

## Project Overview

PoseCap (clean rewrite of Corridor Digital's "Human Input Device" proof of concept): a Blender plugin that drives SMPL-X body models from live webcam pose estimation (PEAR engine), pelvis-locked — world position is a deferred software problem, and the POC's Arduino rig is dropped from scope. The POC at `C:\Dev\CorridorRig-Original` is read-only reference; this repo replaces it with a tested, layered implementation (addon, engine bridge, installers). Hard constraint: SMPL-X model assets carry the MPI research (non-commercial) license — never commit or redistribute them; the repo is private now but goes public later, so git history must stay license-clean from the first commit (no licensed binary ever committed, even briefly). Commercial production use of the models requires a Meshcapade license, independent of the plugin's own license.

**Stack:** Python >=3.11 (addon runs in Blender's bundled interpreter; engine bridge in a uv-managed venv), Blender >= 4.2 LTS and 5.x (bpy, extension platform), and isolated Pose Backends per ADR-0010/ADR-0011: PEAR (PyTorch, CUDA required, optional installer module) and MediaPipe Lite (CPU, account-free). torch is not a workspace dependency; it ships only inside the PEAR backend payload.
**Entry points:** uv workspace packages `contracts/`, `core/`, `engine/` (src layout, `posecap_*` import names). Engine CLIs: `posecap-engine` (PEAR) and `posecap-mediapipe` (`engine/pyproject.toml [project.scripts]`). The Blender extension lives in `addon/` (`blender_manifest.toml`).

## Setup, Build, Test

```bash
# Install (engine bridge + dev tooling)
uv sync

# Test (single file preferred over full suite)
uv run pytest tests/<file>.py
uv run pytest

# Run before any commit
uv run ruff check .
uv run ruff format --check .
uv run pyright --pythonplatform Windows
uv run pyright --pythonplatform Linux
uv run lint-imports
uv run pytest
```

Quality gates run as: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright --pythonplatform Windows`, `uv run pyright --pythonplatform Linux`, `uv run lint-imports`, `uv run pytest`.

Addon code executes inside Blender's bundled Python: stdlib + `bpy`/`mathutils`/`numpy` only; third-party deps must be vendored in the extension wheel, never uv-installed.

## Quality Gates

See [`GUIDELINES.md`](GUIDELINES.md) §8 for the full reference. Non-negotiable subset:

* Hooks wired via pre-commit; new clones run `uv run pre-commit install` once.
* Pre-commit runs ruff, format check, private-key detection, large-file cap, and licensed-binary blocking.
* Pre-push runs DCO, documentation-link, workflow-security, pyright against explicit Windows and Linux platform stubs, pytest default tags, and import-linter checks.
* CI exposes one stable required check (`CI required`) after DCO, title, Linux/Windows quality, dependency, workflow-security, licensed-binary, and package smoke checks pass.
* Never bypass: no `--no-verify`, no skipped hooks, no deleted failing tests.

## Code Style

See [`GUIDELINES.md`](GUIDELINES.md) §2–§4 for the full reference. Non-negotiable subset:

* ruff is the single formatter and linter; pyright strict on `contracts/`/`core/`; `# type: ignore` only at the `bpy` boundary with reason inline.
* `bpy`, `torch`, `serial`, sockets, filesystem never imported in `contracts/` or `core/` (GUIDELINES §1 dependency rule).
* Wire formats defined once in `contracts/` — never duplicated per consumer.

## Architectural Principles

Binding decisions live in [`doc/adr/`](doc/adr/). Do not reinvent, and do not rely on any digest of that directory: read the ADRs relevant to the layer you are touching (each file carries its own Status).

## Repository Layout

* `contracts/` — wire formats, backend manifests, model-asset checks (stdlib only)
* `core/` — pose math, retarget domain, ports (stdlib + numpy + contracts)
* `engine/` — backend adapters (PEAR, MediaPipe), TCP stream server, CLIs
* `addon/` — Blender extension (bpy boundary; engine launched via subprocess)
* `tests/` — mirrors the source tree per layer; `tools/` — gate and build scripts
* `packaging/` — Windows suite installer and backend payload builds (ADR-0011)
* `assets/` — local test media; licensed model assets are never committed
* `doc/product/`, `doc/specs/`, `doc/tasks/`, `doc/adr/` — product scope, feature specs, task files, decision records
* `doc/guides/`, `doc/reference/`, `doc/workflows.md` — user guides, external reference notes, product flow diagrams; agent workflow rules live in `AGENTS.md` and `GUIDELINES.md`
* `.agents/skills/`, `.claude/` — agentic-docs skill installs for Codex and Claude Code
* Upstream PEAR research code stays out of this repo — the bridge imports it from a pinned external location (ADR-0005); shared-package vendoring strategy in ADR-0004.

## Commit & PR Conventions

See [`GUIDELINES.md`](GUIDELINES.md) §10 for the full reference. Non-negotiable subset:

* PR titles use Conventional Commits; every commit carries a matching DCO `Signed-off-by`; concerns stay atomic (use `/ad-commit`).
* Alê (`@alexandremendoncaalvaro`) is currently the sole code reviewer and merge gate; Dean does not perform technical reviews.
* `main` accepts squash merges only after Alê's review, resolved review threads, and green required CI. GitHub cannot record self-approval, so the merge action records the maintainer decision.
* Never push to `main` directly once a remote exists.

## Security & Privacy

See [`GUIDELINES.md`](GUIDELINES.md) §12 for the full reference. Non-negotiable subset:

* Licensed model assets never committed — gitignored; history must stay publishable.
* `C:\Dev\CorridorRig-Original` is read-only reference material — never modify it.
* `torch.load(..., weights_only=False)` and pickle IPC are banned.
* Report vulnerabilities privately through GitHub; secret scanning, push protection, Dependabot, CodeQL, and Scorecard are repository controls, not optional local conventions.

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

<!-- agentic-managed-skills:start -->

## Skills installed by `agentic`

Generated by `@alexandrealvaro/agentic init`. Do not edit this section by hand — re-running the installer regenerates it. Edit the kit instead: https://github.com/alexandremendoncaalvaro/agentic-development.

| Skill | Invoke | Notes |
| --- | --- | --- |
| `ad-bootstrap` | `/ad-bootstrap` | Generate or audit `AGENTS.md` at the repo root. |
| `ad-philosophy` | _(implicit)_ | Universal agent guardrails (think, decide when grounded, verify done). Auto-loads on non-trivial work. |
| `ad-architecture` | `/ad-architecture` | Generate or audit `ARCHITECTURE.md` at the repo root. |
| `ad-adr` | `/ad-adr` | Draft a new ADR at `doc/adr/NNNN-<slug>.md`. |
| `ad-prd` | `/ad-prd` | Lazy lifecycle owner of `doc/product/PRD.md` (or `doc/product/<slug>.md` multi-product). Layer 3 — product-level scope (target user, problem, success metrics, multi-feature roadmap) that feature specs inherit from. Distinct from `ad-spec` (feature-level). |
| `ad-guidelines` | `/ad-guidelines` | Lazy lifecycle owner of `GUIDELINES.md` (Layer 1 Constitution, full engineering reference). Twelve sections — design principles, code standards, complexity, API, performance, build, static analysis, quality gates, testing, git, documentation, security. Pre-suggested defaults from canon + scan-first detection. |
| `ad-spec` | `/ad-spec` | Draft a feature spec at `doc/specs/NNNN-<slug>.md` (Spec Kit-aligned mandatory sections). Layer 4 of the six-layer artifact stack. References parent PRD (`ad-prd`, Layer 3) for product-scope inheritance. |
| `ad-task` | `/ad-task` | Draft a new task at `doc/tasks/NNNN-<slug>.md`. |
| `ad-audit` | `/ad-audit` | Read-only drift report comparing AGENTS.md / ARCHITECTURE.md / ADRs against the code. |
| `ad-review` | `/ad-review` | Two-axis code review per WORKFLOW §10. Claude Code uses fresh-context subagents; Codex writes an audit trail, reviews inline by default, and ships a reviewer subagent for explicit escalation. |
| `ad-ground` | `/ad-ground` | Four-source pre-implementation research (docs / impl-refs / in-repo / git history) + happy-path synthesis + deviation gate. WORKFLOW §4 + §5. |
| `ad-next` | `/ad-next` | State survey + prioritized next-action recommendations across the six-layer artifact stack. Read-only navigation aid (`flutter doctor` pattern). |
| `ad-archive` | `/ad-archive` | Hard-delete completed plan files (tasks / specs / PRDs / superseded ADRs) into git history. ADR-accepted requires absorption proof. |
| `ad-spike` | `/ad-spike` | Staged spike with golden fixtures per WORKFLOW §14. Discovery + fixture + pipeline-with-gates + two-layer evaluation, when the *technique* is uncertain across multiple plausible approaches. |
| `ad-tdg` | `/ad-tdg` | Outcome-based prompting per WORKFLOW §9. Ground truth pair + Test Dependency Map + three approaches + single-criterion selection, when the technique is known but the implementation strategy is uncertain. |
| `ad-tdd` | `/ad-tdd` | Test-Driven Development per WORKFLOW §16. Red-green-refactor as deterministic LLM guardrail. Five phases — confirm regime, plan, tracer bullet, incremental loop, refactor. Tests verify behavior through public interfaces. Horizontal slicing rejected. |
| `ad-domain` | `/ad-domain` | Lazy lifecycle owner of `CONTEXT.md` (Layer 2 — ubiquitous language per Evans 2003). Captures canonical project-specific nouns with aliases-to-avoid, relationships, and flagged ambiguities. Single-context or `CONTEXT-MAP.md` multi-context. |
| `ad-grill` | `/ad-grill` | Interview-before-research grilling session — one question at a time with recommendation, codebase-first, sharpens vocabulary against `CONTEXT.md`, captures terms via `ad-domain` and decisions via `ad-adr` (three-criteria rule). Upstream of `ad-ground`. |
| `ad-deepen` | `/ad-deepen` | Surface deepening opportunities using WORKFLOW §8 vocabulary (Module / Interface / Depth / Seam / Adapter / Leverage / Locality). Three phases — explore, present numbered candidates with deletion-test framing, grill the chosen one. Pairs with `ad-audit`. Profile-scoped to `team` and `mature` only. |
| `ad-diagnose` | `/ad-diagnose` | Disciplined diagnosis loop for hard bugs and performance regressions per WORKFLOW §15. Five phases — build a feedback loop (the skill itself), reproduce, hypothesise (3-5 ranked falsifiable), instrument (one variable at a time), fix + regression-test. |
| `ad-commit` | `/ad-commit` | Atomic Conventional Commits with DCO `Signed-off-by` sign-off. Four phases — scope intake, stage-split when concerns mix, draft message in Conventional Commits format, sign + write. Helper posture, not blocker. |
| `ad-pr` | `/ad-pr` | Open a GitHub pull request with a uniform body shape (Summary / Test plan / Links). Four phases — preflight (`gh` auth + branch pushed), scope assembly, draft body, open + report URL. Title format = Conventional Commits. |
| `ad-merge` | `/ad-merge` | Evaluate and merge a GitHub pull request. Four phases — preflight, evaluate (CI / fresh-context review / linked task / unresolved comments / mergeability), decision (CI green = hard gate; others = warnings), merge with auto-detected mode + `--delete-branch`. |
| `ad-handoff` | `/ad-handoff` | Compact current session into a handoff doc in the OS temp dir. Captures live state, references artifacts by path (no duplication), suggests next skills, redacts secrets. Ephemeral by design — never commits to the repo. |
| `ad-subagent` | `/ad-subagent` | Draft a host-specific custom subagent for bounded delegated work — Claude Code `.claude/agents/<name>.md`, Codex `.codex/agents/<name>.toml`. |
| `ad-hooks` | `/ad-hooks` | Scaffold deterministic quality gates per WORKFLOW §11 — pre-commit + pre-push, runner detected from stack signals. |

<!-- agentic-managed-skills:end -->
