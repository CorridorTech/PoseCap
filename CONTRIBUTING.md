# Contributing to CorridorRig

Thanks for helping build free markerless mocap for Blender. This guide gets you from clone to green tests, and explains the rules that keep the project shippable.

## What you need

Depends on what you want to work on — most contributions need far less than you'd think:

| Working on | Requirements |
|---|---|
| `contracts/`, `core/` (wire formats, pose math — most of the logic) | Any OS, [uv](https://docs.astral.sh/uv/getting-started/installation/), git. No GPU, no Blender, no webcam. |
| `engine/` (PEAR bridge) | Windows 10/11, NVIDIA RTX 30-series or newer, a webcam. |
| `addon/` (Blender extension) | Blender 4.2 LTS or newer (5.x supported). |
| Firmware | Arduino-compatible board + AS5600 encoders + I2C multiplexer (optional hardware path). |

Python itself is managed by uv — you do not need a system Python.

## Setup

```bash
git clone https://github.com/alexandremendoncaalvaro/CorridorRig.git
cd CorridorRig
uv sync
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
uv run pytest
```

If the last command prints all green, you are ready.

## Daily commands

```bash
uv run pytest tests/core/test_rotation.py   # single file while developing
uv run pytest                               # default suite (excludes gpu/e2e/eval tags)
uv run ruff check . && uv run ruff format . # lint + format
uv run pyright                              # types (strict on contracts/core)
uv run lint-imports                         # layer dependency rule
```

The pre-commit hook runs the fast checks on every commit; the pre-push hook runs the full gate. CI runs everything again on Linux and Windows. None of these are skippable — `--no-verify` is not used in this project.

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

- SMPL-X/FLAME/MANO model files or any AI weights (`.npz`, `.pkl`, `.pt`, `.ckpt`, `.onnx`, `.engine`) — these carry restrictive licenses and this repo's history must stay clean. A hook and a CI job both block them.
- Secrets of any kind.

## Branches, commits, pull requests

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, `chore/<topic>`. Never push to `main` directly.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) and carry a DCO sign-off — use `git commit -s` (the `Signed-off-by:` trailer certifies you have the right to contribute the change).
- One concern per commit. A feature and an unrelated fix are two commits.
- PRs need green CI. Reference the task or spec the change implements (`Refs task-0003`).

## Licensing of contributions

The repo is split by package (ADR-0006): the Blender addon is GPL-3.0; `contracts/`, `core/`, `engine/`, and firmware are Apache-2.0. Your contribution lands under the license of the package it touches. Code may flow from the Apache packages into the GPL addon — never the reverse direction.

## Tests

Default-untagged tests are unit tests and must run anywhere. Mark anything that crosses a boundary: `integration` (process/filesystem), `gpu` (needs CUDA — must skip cleanly without it), `e2e` (needs Blender), `slow`, `eval` (accuracy vs golden samples). The default run excludes `gpu`, `e2e`, and `eval`. Wire-format changes that break a golden fixture are breaking changes — say so in the commit.
