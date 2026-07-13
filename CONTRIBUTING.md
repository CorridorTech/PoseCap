# Contributing to PoseCap

Thanks for helping build free markerless mocap for Blender. This guide gets you from clone to green tests, and explains the rules that keep the project shippable.

## What you need

Depends on what you want to work on — most contributions need far less than you'd think:

| Working on | Requirements |
|---|---|
| `contracts/`, `core/` (wire formats, pose math — most of the logic) | Any OS, [uv](https://docs.astral.sh/uv/getting-started/installation/), git. No GPU, no Blender, no webcam. |
| `engine/` (PEAR bridge) | Windows 10/11, NVIDIA RTX 30-series or newer, a webcam. |
| `addon/` (Blender extension) | Blender 4.2 LTS or newer (5.x supported). |

Python itself is managed by uv — you do not need a system Python.

## Setup

```bash
git clone https://github.com/CorridorTech/PoseCap.git
cd PoseCap
uv sync
uv run pre-commit install
uv run pytest
```

If the last command prints all green, you are ready.

## Daily commands

```bash
uv run pytest tests/core/test_rotation.py   # single file while developing
uv run pytest                               # default suite (excludes gpu/e2e/eval tags)
uv run ruff check . && uv run ruff format . # lint + format
uv run pyright --pythonplatform Windows     # Windows type surface
uv run pyright --pythonplatform Linux       # Linux type surface
uv run lint-imports                         # layer dependency rule
```

The pre-commit hook runs fast source and asset checks on every commit. The pre-push hook also validates DCO sign-offs, documentation links, workflow security, architecture, tests, and explicit Windows/Linux type surfaces. CI repeats those controls and package smoke tests behind the stable `CI required` check. None are skippable — `--no-verify` is not used in this project.

## Know the map before you change it

| Question | Read |
|---|---|
| What is this product, what's in scope | [README](README.md), [doc/product/PRD.md](doc/product/PRD.md) |
| How does feature X work, step by step | [doc/workflows.md](doc/workflows.md) (diagrams) |
| What structure is binding | [ARCHITECTURE.md](ARCHITECTURE.md) + [doc/adr/](doc/adr/) |
| What are the engineering rules | [GUIDELINES.md](GUIDELINES.md) (full) / [AGENTS.md](AGENTS.md) (distilled) |
| What is being worked on | [doc/tasks/](doc/tasks/), [doc/specs/](doc/specs/) |

The one rule that surprises people: the dependency direction is machine-enforced. `contracts/` imports stdlib only; `core/` imports stdlib + numpy + contracts; `bpy`/`torch`/sockets live in adapters at the edge. import-linter fails the build otherwise — design with the grain.

## Never commit

- SMPL-X/FLAME/MANO model files or any AI weights (`.npz`, `.pkl`, `.pt`, `.ckpt`, `.onnx`, `.engine`) — these carry restrictive licenses and this repo's history must stay clean. The pre-commit hook and a CI tree scan both block them; the PR goes red.
- Secrets of any kind.

## Never bypass the model-license gate

The MPI body models are research-licensed: each user must register on the official MPI sites and accept the terms personally. Never add a code path that obtains the models without that user action — no Google Drive or Hugging Face mirrors of the MPI files, no bundling in installers, no anonymous downloads. The setup wizard's credential gate is deliberate; PRs that route around it are rejected.

Documented exception: `smpl_mean_params.npz` is public derived data (origin: SPIN), not gated by MPI, and is pinned by hash in [contracts/src/posecap_contracts/model_assets.py](contracts/src/posecap_contracts/model_assets.py).

This guide summarizes; the normative rules live in [AGENTS.md](AGENTS.md) and [GUIDELINES.md](GUIDELINES.md) §12.

## Branches, commits, pull requests

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`. Never push to `main` directly.
- PR titles follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) and become the final squash-commit title. Intermediate commit subjects may be plain language.
- Every commit carries a matching DCO sign-off — use `git commit -s`. To repair a branch, rebase and sign each commit; do not add one catch-all sign-off commit.
- One concern per commit. A feature and an unrelated fix are two commits.
- Alexandre Mendonça Alvaro (`@alexandremendoncaalvaro`) is currently the sole code reviewer; Dean does not perform technical reviews.
- PRs need green `CI required`, all review threads resolved, and Alê's explicit merge decision. GitHub cannot record approval by the PR author, so maintainer-authored PRs use the merge action as that review record. Reference the task or spec the change implements (`Refs task-0003`).

## Licensing of contributions

The repo is split by package (ADR-0006): the Blender addon is GPL-3.0; `contracts/`, `core/`, and `engine/` are Apache-2.0. Your contribution lands under the license of the package it touches. Code may flow from the Apache packages into the GPL addon — never the reverse direction.

## Tests

Default-untagged tests are unit tests and must run anywhere. Mark anything that crosses a boundary: `integration` (process/filesystem), `gpu` (needs CUDA — must skip cleanly without it), `e2e` (needs Blender), `slow`, `eval` (accuracy vs golden samples). The default run excludes `gpu`, `e2e`, and `eval`. Wire-format changes that break a golden fixture are breaking changes — say so in the commit.
