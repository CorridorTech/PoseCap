# Task 0001: Scaffold uv workspace, contracts package, and tooling

**Status:** in-progress
**Created:** 2026-06-11
**Owner:** alexandremendoncaalvaro
**Execution:** AFK
**Spec ref:** doc/specs/0001-live-webcam-pose-streaming.md
**Board ref:**

## Context

Every other SPEC-0001 task depends on this one: the workspace layout (ADR-0004), the wire-format contracts (ADR-0003), and the quality tooling (GUIDELINES §7) must exist before core math, engine, or addon code can land. The pose-frame schema fixes the order-based bone contract the POC carried implicitly (the pkl had no bone names — order was the contract, POC `operators/pose.py:142-171`); making it explicit and golden-tested is the single highest-leverage piece of the rewrite. Wheels for `contracts/` and `core/` must be pure-Python (`py3-none-any`) because Blender 4.2 bundles Python 3.11 and 5.x bundles 3.13.

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [x] `uv sync` succeeds from a clean checkout; `uv.lock` committed.
- [x] Workspace members `contracts/`, `core/`, `engine/` exist, each with its own `pyproject.toml`; root `pyproject.toml` declares the workspace.
- [x] `contracts/` defines typed schemas + JSON line codecs for: pose frame (schema_version, seq, captured_at, status ok|no_person, global_orient[3], body_pose[21][3], left_hand_pose[15][3], right_hand_pose[15][3], jaw_pose[3], betas[10], expression[10], transl[3]), job status, and serial frame. Decode validates and raises typed errors on malformed input.
- [x] Golden JSON fixtures pin the pose-frame schema; round-trip encode/decode tests pass.
- [x] `uv run ruff check`, `uv run ruff format --check`, `uv run pyright` (strict on contracts), and `uv run lint-imports` all pass.
- [x] import-linter contracts encode ADR-0001: `contracts/` stdlib-only; `core/` may import stdlib, numpy, `contracts/` only.
- [x] `.gitattributes` with `* text=auto eol=lf` lands; fresh clone produces no CRLF warnings.
- [x] AGENTS.md "Entry points" TODO updated to the real tree.

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [x] Add `.gitattributes` at repo root.
- [x] Root `pyproject.toml`: `[tool.uv.workspace]` members `contracts`, `core`, `engine`; shared `[tool.ruff]`, `[tool.pyright]`, `[tool.importlinter]` config per GUIDELINES §7.
- [x] `contracts/pyproject.toml` + `contracts/src/corridorrig_contracts/` — frame dataclasses, `encode_line()`/`decode_line()` (compact separators, JSONDecodeError → typed error).
- [x] `core/pyproject.toml` + `core/src/corridorrig_core/` — package skeleton and `PoseStream` port placeholder (math lands in task 0002).
- [x] `engine/pyproject.toml` + `engine/src/corridorrig_engine/` — package skeleton.
- [x] `tests/contracts/` — round-trip tests + `fixtures/*.json` golden files.
- [x] Run the full gate locally; commit via /ad-commit (`build:` + `test:` concerns split).
- [x] Update AGENTS.md entry-points line.

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### 2026-06-11

Scaffold implemented on `feat/task-0001-scaffold`. Gates green: ruff clean, format clean, pyright 0 errors (strict on contracts/core), import-linter 2/2 contracts kept, pytest 27/27. Golden fixtures generated from the canonical encoder (sorted keys, compact separators) and pinned byte-for-byte by tests. Frame schema groups SMPL-X arrays in a nested `pose` object, present iff `status` is "ok" — explicit no-person frames per SPEC-0001 R11. `py.typed` markers added so pyright treats workspace packages as typed. Root LICENSE = Apache-2.0 per ADR-0006; the GPL-3.0 addon license lands with task 0004. Pending: fresh-context review (DoD), then status done.

Naming: the plan step said `encode_line()`/`decode_line()`; shipped names are `encode_pose_frame()`/`decode_pose_frame()` (clearer once job-status and serial codecs joined the package). Flagged by the spec-axis review; recorded here instead of rewriting the plan step.

Two-axis review (WORKFLOW §10) ran on the branch: 1 Standards Blocker (encoder accepted status/pose-inconsistent frames — fixed with an invariant guard plus two tests), 2 Standards Concerns (job-state dual representation deduplicated; test helpers converted to pytest fixtures), docstring notes addressed. Spec axis: zero blockers, no scope creep, no missing AC.

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
