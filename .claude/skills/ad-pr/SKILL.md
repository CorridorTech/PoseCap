---
name: ad-pr
description: Open a GitHub pull request with a uniform body shape. Four phases — preflight (`gh` auth + branch pushed), scope assembly (commits + diff vs base), draft body (Summary / Test plan / Links), open + report URL. Title format = Conventional Commits, type inferred from the dominant commit type in the range. `gh` CLI soft-fail with install hint. Triggers on "open a PR", "create a pull request", "submit a PR", "gh pr create", "/ad-pr".
summary: Open a GitHub pull request with a uniform body shape (Summary / Test plan / Links). Four phases — preflight (`gh` auth + branch pushed), scope assembly, draft body, open + report URL. Title format = Conventional Commits.
allowed-tools: Read, Bash, Glob, Grep
---

# /ad-pr

Implements ADR-0024 and ADR-0032. Opens a PR via `gh pr create` with a uniform body shape (Summary / Test plan / Links). Helper posture on scope, links, and body drafting — warnings surface without refusing. Hard gate on local quality: the skill refuses to open a PR when pre-push / CI-mirror gates exit non-zero (WORKFLOW §11 — CI failure is a local gate gap). No `--no-verify` symmetric bypass; users who need to open a red draft invoke `gh pr create --draft` directly.

## Step 0 — Confirm regime

Run when:

- One or more atomic commits exist on the current branch ahead of the base (typically `main`).
- The user asks to "open a PR", "submit a PR", "create a pull request".

Route elsewhere when:

- The branch has uncommitted or unsplit work → `/ad-commit` first.
- The user wants to merge an already-open PR → `/ad-merge`.

## Phase 1 — Preflight

Check `gh` is installed and authenticated:

```bash
gh --version
gh auth status
```

If `gh` is missing, surface:

> `gh` CLI not installed. Install: https://cli.github.com/ then run `gh auth login`. This skill cannot open the PR without it.

If `gh auth status` fails, surface the same hint with `gh auth login`. **Soft-fail** — do not silently fall back to `git push` only.

Check the branch is pushed:

```bash
git rev-parse --abbrev-ref @{u}
git rev-list --count <base>..HEAD
```

If no upstream is set or the branch is unpushed, prompt the user:

> Branch not pushed to origin. Run `git push -u origin <branch>` first? (y/n)

If they confirm, run the push and continue.

Detect the base branch:

```bash
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
```

Default to `main` if the call fails.

Run local gates before opening the PR (WORKFLOW §11 — CI failure is a local gate gap). The gate check runs **after** `git push` has landed the branch (so the pre-push hook has already fired once) and **before** `gh pr create` — the goal is to catch the case where a developer skipped the pre-push hook, ran on a different matrix leg than CI, or wired the runner incompletely, and to refuse to open the PR against a red tree:

1. **Detect the pre-push tier.** Read `lefthook.yml`, `.husky/pre-push`, `.pre-commit-config.yaml` (pre-push stage), or `.git/hooks/pre-push` to extract the commands the pre-push hook runs.
2. **Run them explicitly.** Do not rely on `git push` firing the hook — the hook already ran (or will run) on push. Running the same commands here catches gaps *before* the PR opens and burns CI minutes. If no hook runner is detected, fall back to reading `.github/workflows/*.yml` (or the detected CI surface) and run its test / lint / typecheck / build commands locally.
3. **Refuse on red.** If any gate command exits non-zero, refuse to open the PR. Surface: `Pre-push gate <name> failed: <exit-code output>. Fix locally before opening the PR — pushing red-CI diffs burns cloud minutes and normalizes broken main. Rerun /ad-pr after fixing.` Do not offer `--no-verify` or a bypass flag; WORKFLOW §11 is binding.
4. **Warn on absent gates.** If neither a hook runner nor a CI surface exists, surface: `No pre-push or CI config detected — opening PR without a local gate check. Wire /ad-hooks so subsequent PRs get preflight coverage.` Continue.

Matrix awareness: if CI runs a multi-version matrix (e.g., Node 20 + 22) and local runs one version, note the gap in the preflight report but do not refuse — matrix mirroring belongs to `/ad-hooks`, not to every PR open. Refuse only on outright red, not on matrix gaps.

## Phase 2 — Scope assembly

Gather context:

```bash
git log <base>..HEAD --pretty='%h %s'
git diff --stat <base>...HEAD
```

Infer the PR title:

- **Dominant Conventional Commits type** — most frequent type across `<base>..HEAD`. If one commit, use its type / scope / subject directly. If multiple commits and one type dominates, use that. If mixed, surface to the user: "Branch mixes `feat:` + `fix:`. Use which type for the PR title?"
- **Scope** — most common scope across the commits (or empty if inconsistent).
- **Subject** — synthesized from the changes, ≤70 chars, imperative.

Detect back-links:

- Scan commit message bodies for `task-NNNN`, `ADR-NNNN`, `spec-NNNN`, `#<issue>`, `Closes`, `Fixes`, `Per`, `See`.
- Scan changed file paths for `doc/tasks/NNNN-*.md`, `doc/adr/NNNN-*.md`, `doc/specs/NNNN-*.md` — those are the artifacts this PR implements or updates.

## Phase 3 — Draft body

Apply this template:

```
## Summary
- <1-3 bullets — the WHY, not the what>

## Test plan
- [ ] <test 1>
- [ ] <test 2>

## Links
- <task / spec / ADR / issue back-links>
```

Rules:

- **Summary:** explain motivation. The commit list and diff already show the what. 1-3 bullets max.
- **Test plan:** concrete steps a reviewer can run. `npm test`, manual smoke, integration check. Skip the section if there is genuinely nothing to test (a pure docs PR). **Never fabricate test items.**
- **Links:** every detected back-link from Phase 2. Skip the section if there are none. **Never invent links.**

Surface the draft to the user for approval before opening. The user may edit or accept.

## Phase 4 — Open + report

Call `gh pr create` with HEREDOC body:

```bash
gh pr create --title "<type>(<scope>): <subject>" --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...

## Links
- task-NNNN, ADR-NNNN, #issue
EOF
)"
```

Capture the returned PR URL and report it to the user.

If `gh pr create` fails (no GitHub remote, branch already has an open PR, etc.), surface the error verbatim and stop. Do not retry blindly.

## Output contract

The output is an opened PR on GitHub. The skill returns the PR URL.

## Next

- After PR opens and CI starts: monitor via `gh pr checks`.
- When CI is green: `/ad-merge` to evaluate and merge.
- If a fresh-context review is wanted before merge: `/ad-review` (WORKFLOW §10) — the review artifact lands in `.agentic/reviews/` and `ad-merge` checks for it.
- If preflight surfaced "no CI workflow file": `/ad-hooks` (when installed) covers local gates; remote CI is a separate concern outside this skill.
