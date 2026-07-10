---
name: ad-hooks
description: Scaffold deterministic quality gates per WORKFLOW.md §11 — pre-commit (lint, format, secret-scan), pre-push (build, unit, integration). Detects the project's stack and recommends a hook runner (Husky / lefthook / pre-commit / native), scaffolds the runner config, and updates AGENTS.md Quality Gates. Use when the user wants to wire hooks, configure pre-commit / pre-push, set up quality gates, prevent --no-verify bypass, or close the WORKFLOW §11 advisory-vs-deterministic gap. Opt-in skill; not auto-installed.
summary: Scaffold deterministic quality gates per WORKFLOW §11 — pre-commit + pre-push, runner detected from stack signals.
---

<background_information>
Scaffolds the deterministic gates `WORKFLOW.md` §11 names. The skill writes config files for a hook runner and updates `AGENTS.md` Quality Gates; it does not execute install scripts. The user runs the runner's one-time bootstrap (`npx husky init`, `lefthook install`, `pre-commit install`) — the skill names the exact command.

Codex auto-trigger on description keywords is less mature than Claude Code's. If auto-invocation does not fire when the user asks about hooks, pre-commit, or quality gates, invoke the skill manually.
</background_information>

<instructions>
Step 0 — confirm the gates the user wants. WORKFLOW §11 names two tiers:
- Pre-commit (fast): lint, format, secret-scan. Runs on every commit. Keep under ~5s; slow pre-commits push devs to `--no-verify`.
- Pre-push (thorough): build, unit tests, integration tests. Runs on every push. Acceptable to be slow.

Confirm both tiers are in scope. If the user wants only one, scaffold only that tier.

Visual / E2E for UI projects (Cypress, Playwright) live in CI, not pre-push. Out of scope.

Step 1 — detect the runner. Read repo signals in this order:
1. Existing runner. `.husky/` → Husky. `lefthook.yml` or `.lefthook.yml` → lefthook. `.pre-commit-config.yaml` → pre-commit. `.git/hooks/` with non-sample scripts → native hooks.
2. Stack signals (if no runner present). `package.json` → recommend Husky or lefthook. `pyproject.toml` → recommend pre-commit. `go.mod` → recommend lefthook. `Cargo.toml` → recommend lefthook. Multiple stacks → recommend lefthook (cross-language by default).
3. No signals. Recommend native `.git/hooks/` only as fallback. Warn the user that native hooks are not portable across clones.

If multiple runners are present, surface the conflict and ask the user before scaffolding. Never silently pick.

Step 2 — recommend the per-stack commands:
- Node: lint = `npm run lint` or `npx eslint .`; format check = `npm run format:check` or `npx prettier --check .`; secret-scan = `gitleaks detect --no-banner`; build = `npm run build` (skip if no script); test = `npm test`.
- Python: lint = `ruff check .`; format check = `ruff format --check .` or `black --check .`; secret-scan = `gitleaks detect --no-banner`; test = `pytest -q`.
- Go: lint = `golangci-lint run`; format check = `gofmt -d .`; secret-scan = `gitleaks detect --no-banner`; build = `go build ./...`; test = `go test ./...`.
- Rust: lint = `cargo clippy -- -D warnings`; format check = `cargo fmt --check`; secret-scan = `gitleaks detect --no-banner`; build = `cargo build`; test = `cargo test`.
- Mixed / other: ask for the per-tier command list. Do not invent.

Offer to swap any default. Confirm before writing.

Step 3 — scaffold the runner config. Write the runner-specific config file:
- Husky: `.husky/pre-commit` and `.husky/pre-push` (shell scripts) + `"prepare": "husky"` in `package.json`. Bootstrap: `npm install`.
- lefthook: `lefthook.yml` at the repo root with `pre-commit` and `pre-push` commands keyed by stage. Bootstrap: `lefthook install`.
- pre-commit: `.pre-commit-config.yaml` with stack-specific hook references. Bootstrap: `pre-commit install` and `pre-commit install --hook-type pre-push`.
- Native: `.git/hooks/pre-commit` and `.git/hooks/pre-push` + a `setup-hooks.sh` script the user runs after every clone (since `.git/` is not committed).

Step 4 — update `AGENTS.md` Quality Gates. Append or refresh the section with: pre-commit gate list, pre-push gate list, runner name + config path, bootstrap command, CI status if known, no-bypass policy. Honor existing managed markers if `ad-bootstrap` already wrote Quality Gates.

Step 5 — mirror CI locally. WORKFLOW §11: "CI failure is a local gate gap." Read the CI config and compare:
1. Detect CI surface in order: `.github/workflows/*.yml`, `.gitlab-ci.yml`, `.circleci/config.yml`, `azure-pipelines.yml`, `.buildkite/pipeline.yml`. If none, note the gap and skip — mirror check has no target.
2. Extract CI commands from `run:` / `script:` steps — test / lint / typecheck / build. Skip checkout, setup, cache, publish.
3. Extract CI matrix — language versions, OS runners, feature flags. These become pre-push matrix requirements when they change the failure surface.
4. Diff against pre-push. For each CI command not covered locally, warn: `CI runs <cmd> — pre-push does not. Add to pre-push or CI will catch what local won't.` For each matrix dimension CI covers that pre-push does not, warn: `CI matrix <dim>=<values>, pre-push runs <value>.`
5. Offer to close the gap. Propose specific edits to the runner config; ask the user before writing (matrix mirroring can be expensive).

Step 6 — tell the user the bootstrap command. Output the exact one-line command the user runs. The skill does not execute it.
</instructions>

<output_contract>
Filesystem changes:
- The runner's config file (`.husky/pre-commit`, `lefthook.yml`, `.pre-commit-config.yaml`, or `.git/hooks/`).
- An updated `AGENTS.md` Quality Gates section.
- For native-hooks fallback: a `setup-hooks.sh` script.

The skill does not execute the runner's install command. The skill does not write CI config. The skill does not configure agent-side hooks (`.claude/settings.json`) — different surface, deferred.

Documentation discipline rules apply at write time:
- No emoji anywhere in scaffolded config or AGENTS.md update.
- No version stamps or DRAFT markers.
- Quality Gates section opens with the operational rule (gates are deterministic) before listing the gates.
- One scope: Quality Gates. No duplication of ARCHITECTURE.md or ADR rationale.
- No commented-out scripts. No orphan TODO / FIXME.
</output_contract>

## Next

- Run the runner's bootstrap command (cited in Step 6 — e.g., `npm install`, `lefthook install`, `pre-commit install`).
- Verify a deliberately-failing edit (e.g., a known lint violation) gets blocked at commit.
- Add a redundant CI gate so contributors cannot bypass via `--no-verify`. WORKFLOW §11 binding.
- `/ad-audit` periodically to confirm hooks stay wired as the project evolves.
