---
name: ad-hooks
description: Scaffold deterministic quality gates per WORKFLOW.md §11 — pre-commit (lint, format, secret-scan), pre-push (build, unit, integration). Detects the project's stack and recommends a hook runner (Husky / lefthook / pre-commit / native), scaffolds the runner config, and updates AGENTS.md Quality Gates. Use when the user wants to wire hooks, configure pre-commit / pre-push, set up quality gates, prevent --no-verify bypass, or close the WORKFLOW §11 advisory-vs-deterministic gap. Opt-in skill; not auto-installed in the universal set.
summary: Scaffold deterministic quality gates per WORKFLOW §11 — pre-commit + pre-push, runner detected from stack signals.
allowed-tools: Read, Write, Glob, Bash
---

# /ad-hooks

Scaffolds the deterministic gates `WORKFLOW.md` §11 names. The skill writes config files for a hook runner and updates `AGENTS.md` Quality Gates; it does not execute install scripts. The user is responsible for the runner's one-time bootstrap (e.g., `npx husky init`, `lefthook install`, `pre-commit install`) — the skill says exactly which command to run.

## Step 0 — Confirm the gates the user wants

`WORKFLOW.md` §11 names two tiers:

* **Pre-commit (fast):** lint, format, secret-scan. Runs on every commit. Slow pre-commits push devs to `--no-verify`; keep it under ~5s.
* **Pre-push (thorough):** build, unit tests, integration tests. Runs on every push. Acceptable to be slow; the cost is paid less often than commit.

Confirm both tiers are in scope for this project. If the user wants only one tier, scaffold only that tier — do not add gates the user did not ask for.

Visual / E2E for UI projects (Cypress, Playwright, Claude in Chrome) are mentioned by §11 but live in CI, not pre-push. Out of scope for this skill.

## Step 1 — Detect the runner

Read the repo signals in this order:

1. **Existing runner.** `.husky/` → Husky present. `lefthook.yml` or `.lefthook.yml` → lefthook present. `.pre-commit-config.yaml` → pre-commit present. `.git/hooks/` with non-sample scripts → native hooks present.
2. **Stack signals (if no runner present).** `package.json` → Node-rooted; recommend Husky (most common in Node ecosystem) or lefthook (cross-language fit). `pyproject.toml` → Python-rooted; recommend pre-commit. `go.mod` → Go-rooted; recommend lefthook. `Cargo.toml` → Rust-rooted; recommend lefthook. Multiple stacks → recommend lefthook (cross-language by default).
3. **No signals.** Recommend native `.git/hooks/` only as fallback. Warn the user that native hooks are not portable across clones (every contributor has to run a setup script).

If multiple runners are present, surface the conflict and ask the user before scaffolding. Never silently pick.

## Step 2 — Recommend the per-stack commands

For the chosen runner, propose the per-tier command set:

* **Node (`package.json` present):** lint = `npm run lint` (fall back to `npx eslint .` if no `lint` script); format check = `npm run format:check` (fall back to `npx prettier --check .`); secret-scan = `gitleaks detect --no-banner` (cite the install instruction); build = `npm run build` (skip if no script); test = `npm test`.
* **Python (`pyproject.toml` present):** lint = `ruff check .`; format check = `ruff format --check .` or `black --check .`; secret-scan = `gitleaks detect --no-banner`; test = `pytest -q`.
* **Go (`go.mod` present):** lint = `golangci-lint run`; format check = `gofmt -d .`; secret-scan = `gitleaks detect --no-banner`; build = `go build ./...`; test = `go test ./...`.
* **Rust (`Cargo.toml` present):** lint = `cargo clippy -- -D warnings`; format check = `cargo fmt --check`; secret-scan = `gitleaks detect --no-banner`; build = `cargo build`; test = `cargo test`.
* **Mixed / other:** ask the user for the per-tier command list. Do not invent.

Offer to swap any default. Confirm before writing.

## Step 3 — Scaffold the runner config

Write the runner-specific config file. Below are the canonical shapes; adapt to the user's tier choices.

**Husky** — `.husky/pre-commit` and `.husky/pre-push` (shell scripts). Plus a `prepare` script in `package.json` (`"prepare": "husky"`). User runs `npm install` once to bootstrap.

**lefthook** — `lefthook.yml` at the repo root with `pre-commit` and `pre-push` commands keyed by stage. User runs `lefthook install` once.

**pre-commit (pre-commit.com)** — `.pre-commit-config.yaml` referencing the canonical hooks for the stack (e.g., `pre-commit/mirrors-eslint`, `psf/black`, `astral-sh/ruff-pre-commit`). User runs `pre-commit install` and `pre-commit install --hook-type pre-push`.

**Native `.git/hooks/`** — `.git/hooks/pre-commit` and `.git/hooks/pre-push` plus a `setup-hooks.sh` script the user runs after every clone (since `.git/` is not committed). Document the setup-script invocation in `AGENTS.md`.

## Step 4 — Update `AGENTS.md` Quality Gates section

Append (or refresh, if a Quality Gates section already exists) the following content:

```
## Quality Gates

Deterministic enforcement — agent cannot skip.

- Pre-commit hook (fast): <stack-specific lint, format, secret-scan commands>
- Pre-push hook (thorough): <stack-specific build, unit, integration commands>
- Hook runner: <Husky | lefthook | pre-commit | native>; config at <path>
- Bootstrap: <one-line setup command>
- CI blocks on: <list — skip if CI not yet wired>
- Never bypass: no `--no-verify`, no skipped hooks, no deleted failing tests. WORKFLOW §11 is binding.
```

Honor the existing managed-skills / managed-quality-gates markers if `ad-bootstrap` already wrote a Quality Gates section. The skill refreshes the section in place; user content outside the markers is preserved.

## Step 5 — Mirror CI locally (drift check)

Local gates must mirror what CI runs — same commands, same matrix. WORKFLOW §11: "CI failure is a local gate gap." Read the CI config and compare.

1. **Detect the CI surface.** In order: `.github/workflows/*.yml` (GitHub Actions), `.gitlab-ci.yml` (GitLab CI), `.circleci/config.yml` (Circle), `azure-pipelines.yml` (Azure), `.buildkite/pipeline.yml` (Buildkite). If none, note the gap and stop this step — the mirror check has no target.
2. **Extract CI commands.** Parse the `run:` / `script:` steps from the CI config. Focus on test / lint / typecheck / build invocations; ignore checkout, setup, cache, publish steps.
3. **Extract CI matrix.** Language versions (Node 20 / 22, Python 3.11 / 3.12, Go 1.22, etc.), OS runners (`ubuntu-latest`, `macos-latest`), feature flags. These become the pre-push matrix requirement when they change the failure surface.
4. **Diff against the pre-push tier.** For each CI command not covered by pre-push, warn: `CI runs <cmd> — pre-push does not. Add to pre-push or CI will catch what local won't.` For each matrix dimension CI covers that pre-push does not (e.g., pre-push runs Node 22 only, CI runs 20 + 22), warn: `CI matrix <dim>=<values>, pre-push runs <value>. Failures under <missing-value> will only surface in CI.`
5. **Offer to close the gap.** If gaps exist, propose specific edits to the runner config (extra commands, matrix loop via `Node --version` iteration, feature-flag pass). Ask the user before writing — matrix mirroring can be expensive; the user picks.

The mirror check runs after Step 4 wrote the config, so gap edits layer on top of a working scaffold. If the CI surface is absent, note: "No CI config detected — pre-push is the only gate. Add CI so contributors cannot bypass via `--no-verify` and re-run this skill to re-mirror."

## Step 6 — Tell the user what to run

After writing the config, output exactly the bootstrap command the user must run (e.g., `npm install` for Husky, `lefthook install` for lefthook, `pre-commit install` for pre-commit). The skill does not execute the bootstrap — that is the user's call.

If the user is wiring CI alongside hooks (GitHub Actions / GitLab CI / Circle), point them at the existing `.github/workflows/`, `.gitlab-ci.yml`, or `.circleci/` directory. CI scaffolding is a separate skill's responsibility (deferred — not this one).

## Output contract

Filesystem changes:

- The runner's config file (e.g., `.husky/pre-commit`, `lefthook.yml`, `.pre-commit-config.yaml`).
- An updated `AGENTS.md` Quality Gates section (or appended if absent), naming the runner, the gates wired, the bootstrap command, and the no-bypass policy.
- For the native-hooks fallback only: a `setup-hooks.sh` script the user runs after every clone.

The skill does not execute the runner's install command. The skill does not write CI config. The skill does not configure agent-side hooks (`.claude/settings.json` `Stop` / `PreToolUse` / `PostToolUse`) — that is a different surface; future ADR may cover it.

A narrative document, so the documentation discipline rules apply at write time:

- No emoji anywhere in the scaffolded config or in the AGENTS.md update.
- No version stamps or DRAFT markers.
- The Quality Gates section opens with the operational rule (gates are deterministic) before listing the gates themselves.
- One scope: Quality Gates. Do not duplicate ARCHITECTURE.md or ADR rationale here.
- No commented-out scripts. No orphan TODO / FIXME — every deferred command references a tracked task or GitHub Issue.

## Next

- Run the runner's bootstrap command (cited in Step 6 — e.g., `npm install`, `lefthook install`, `pre-commit install`).
- Verify a deliberately-failing edit (e.g., a known lint violation) gets blocked at commit. The gate is real only when it actually fires.
- Add a redundant CI gate (`.github/workflows/`, GitLab CI, or equivalent) so contributors cannot bypass via `--no-verify`. WORKFLOW §11 binding.
- `/ad-audit` periodically to confirm hooks stay wired as the project evolves.
