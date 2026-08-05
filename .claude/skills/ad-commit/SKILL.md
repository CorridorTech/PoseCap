---
name: ad-commit
description: Atomic Conventional Commits with DCO `Signed-off-by` sign-off. Four phases — scope intake, stage-split when concerns mix, draft message in Conventional Commits format, sign + write. Stage-split is interactive; identity comes from `git config user.name` / `user.email`. No `Co-Authored-By`. Helper posture, not blocker. Triggers on "commit this", "stage and commit", "atomic commit", "Conventional Commit", "sign off", "DCO", "split this commit", "/ad-commit".
summary: Atomic Conventional Commits with DCO `Signed-off-by` sign-off. Four phases — scope intake, stage-split when concerns mix, draft message in Conventional Commits format, sign + write. Helper posture, not blocker.
allowed-tools: Read, Bash
---

# /ad-commit

Implements ADR-0023. Drafts atomic Conventional Commits with DCO `Signed-off-by` sign-off. Helper, not blocker — the senior engineer keeps decision authority.

## Step 0 — Confirm regime

Run when the user wants to land changes as commits and at least one holds:

- Working tree has staged or unstaged changes worth committing.
- User asks for "commit", "stage", "split this commit", "sign off".

Route elsewhere when:

- The user wants to open a PR after committing → continue with `/ad-pr` after this skill finishes.
- The user wants to merge an open PR → `/ad-merge`.
- The diff is unfinished work that should not land yet → say so; do not commit speculatively.

## Phase 1 — Scope intake

Read the working tree:

```bash
git status --short
git diff --staged
git diff
```

Classify concerns. Group changes by:

- **Conventional Commits type** — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `build:`, `ci:`, `perf:`, `style:`, `revert:`.
- **Subsystem** — directory / module the file lives under.
- **Causal relationship** — a mechanical rename and its callers are *one* concern; a `feat:` and an unrelated `fix:` are *two*.

Decision:

- **Single concern** → proceed to Phase 3 (no stage-split needed).
- **Multiple concerns** → present a numbered list of detected concerns and ask the user to confirm the stage-split plan. Format:

  ```
  Detected 3 concerns:
    1. feat(auth): add login flow (src/auth/, test/auth.test.js)
    2. fix(cli): trim trailing newline (src/index.js)
    3. docs(readme): refresh skill table (README.md)

  Proceed concern-by-concern? (y/n, or "bundle them all into one commit")
  ```

When the user says "bundle them" or you are in genuine doubt about whether two changes are one concern or two, surface the call and proceed with their decision. Senior engineer keeps authority.

## Phase 2 — Stage-split (when needed)

For each concern, in user-confirmed order:

1. **Stage exactly the files (or hunks) for this concern.** Use `git add <path>` for whole files. Use `git add -p <path>` when a file holds changes for two concerns and a hunk-level split is needed. **Never `git add -A` / `git add .` when concerns are mixed.**
2. **Verify the stage.** Run `git diff --staged` and confirm only this concern's changes are present.
3. **Draft + write the commit** (Phases 3 + 4 below).
4. Repeat for the next concern.

If a partial-file hunk split is too complex (interleaved changes, refactor + behavior in the same line), surface the call: either accept the bundled commit for that file or ask the user to split the file edit first.

## Phase 3 — Draft message

Apply [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) format:

```
<type>(<scope>?): <subject>

<body — explains WHY when non-obvious; references task/ADR/issue>
```

Subject rules:

- ≤72 chars.
- Imperative mood: "add", "fix", "rename" — not "added" / "adds".
- No trailing period.
- Lowercase after the colon (except proper nouns, acronyms, filenames).
- Scope is optional but recommended: `feat(auth):`, `fix(cli):`, `docs(readme):`.

Body rules:

- Explain **why** the change is needed when non-obvious. The diff already shows what.
- Reference related work: `Closes task-0025`, `Per ADR-0023`, `Fixes #42`.
- Wrap at ~72 chars. Blank line between paragraphs.
- No trailing summary of what the diff shows. No marketing prose.

Type guide:

- `feat:` — new user-visible capability.
- `fix:` — bug fix.
- `chore:` — maintenance (deps, version bump, repo hygiene).
- `docs:` — documentation only.
- `refactor:` — code change that neither fixes a bug nor adds a feature.
- `test:` — tests only.
- `build:` — build system, package manifest, lockfile.
- `ci:` — CI configuration.
- `perf:` — performance improvement.
- `style:` — formatting only (no semantic change).
- `revert:` — reverts a prior commit.

Breaking changes: add `!` after the type/scope and a `BREAKING CHANGE:` footer paragraph.

## Phase 4 — Sign + write

Resolve identity:

```bash
git config user.name
git config user.email
```

If either is unset, **stop and ask the user to configure them.** DCO sign-off requires real attribution; the skill will not invent it.

Append the trailer (always last line, blank line before it):

```
Signed-off-by: <Name> <email>
```

Do **not** add a `Co-Authored-By:` trailer (ADR-0023 §Decision 1 — DCO only).

Write the commit using a HEREDOC so multi-line body content is preserved verbatim:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body paragraph 1>

<body paragraph 2>

Signed-off-by: <Name> <email>
EOF
)"
```

Do **not** pass `--no-verify` or `--no-gpg-sign`. Pre-commit and pre-push hooks run; failures surface and the skill stops so the user can fix the underlying issue.

If a hook fails:

- Investigate the underlying cause. Do not skip the hook.
- Fix the issue, re-stage if needed, and run `git commit` again (create a new commit; do not amend unless the user explicitly asks).

## Output contract

The output is one or more atomic commits on the current branch. Each commit:

- Single concern.
- Conventional Commits format with valid type.
- Subject imperative + ≤72 chars.
- Body explains *why* when non-obvious; references task / ADR / issue when one exists.
- `Signed-off-by: <Name> <email>` trailer.
- No `Co-Authored-By` trailer.
- No skipped hooks.

## Next

- After commits land: `/ad-pr` to open the PR with a uniform body shape.
- After PR is open and CI is green: `/ad-merge` to evaluate and merge.
- If the diff also surfaced a refactor opportunity: `/ad-deepen` (when on `team` / `mature` profile per ADR-0020 §4).
- If a hook failure exposed a recurring drift: `/ad-drift`.
