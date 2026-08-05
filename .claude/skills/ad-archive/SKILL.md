---
name: ad-archive
description: Hard-delete completed plan files (tasks Status:done, specs Status:shipped, PRDs Status:superseded, ADRs Status:superseded or deprecated) via `git rm`, leaving git history as the only ledger. Use when the user wants to archive, clean, prune, or sweep finished decision-records out of the working tree. No `CHANGELOG.md`, no `archive/` subdir (both violate kit discipline). Accepted ADRs removable only when the user names them and an absorption check passes — the ADR's substance must be grep-findable in a binding doc (ARCHITECTURE.md / GUIDELINES.md / AGENTS.md / code).
summary: Hard-delete completed plan files (tasks / specs / PRDs / superseded ADRs) into git history. ADR-accepted requires absorption proof.
allowed-tools: Read, Glob, Grep, Bash
---

# /ad-archive

Removes plan files whose decision-record lifecycle is over. Git history retains the content; the working tree stops paying context cost on artifacts the LLM no longer needs to scan.

## Rationale

Decision-record artifacts (`doc/adr/`, `doc/tasks/`, `doc/specs/`, `doc/product/`) carry their lifecycle in a `Status:` frontmatter field. Once an item reaches a terminal state (task `done`, spec `shipped`, PRD `superseded`, ADR `superseded` / `deprecated`), keeping the file in the working tree adds tokens every time an agent globs the directory but adds zero binding force — the work has shipped, the decision has been replaced, or the rationale has been absorbed into a permanent doc.

`/ad-archive` removes them via `git rm`. Three rules anchor the design:

- **No `CHANGELOG.md`, no `archive/` subdirectory.** `WORKFLOW.md` Rule #2 forbids changelogs in narrative documents; an `archive/` subdir still expands under directory globs and defeats the point. Git history is the ledger; `/ad-commit` after `/ad-archive` is the breadcrumb. `git log --diff-filter=D -- doc/adr/` reaches it when needed.
- **Status-driven, not age-driven.** A done task removed two days after completion is fine. An accepted ADR untouched for two years is not a candidate — accepted means binding.
- **Accepted ADRs require absorption proof.** Nygard's tradition treats accepted ADRs as immutable. The kit's lean-tree value justifies removal only when the ADR's substance — not just its slug citation — has been moved into a binding document such that deletion loses no information. The skill enforces this by grepping the named target for the ADR's core claim before allowing `git rm`.

## Step 1 — Discover candidates

Read frontmatter only; do not load full bodies. Build four candidate sets.

**Tasks** (`doc/tasks/NNNN-*.md`): include if `Status: done`. Exclude `proposed`, `in-progress`, `blocked`.

**Specs** (`doc/specs/NNNN-*.md`): include if `Status: shipped`. Exclude `draft`, `accepted`, anything `superseded by SPEC-NNNN` (the supersession chain is information; chain target stays).

**PRDs** (`doc/product/PRD.md` single-product or `doc/product/<slug>.md` multi-product): include if `Status: superseded`. Exclude `draft`, `accepted`.

**ADRs** (`doc/adr/NNNN-*.md`):
- *Auto-include* if `Status: superseded by ADR-NNNN` or `Status: deprecated`. The supersession chain target stays.
- *Do not auto-include* `Status: accepted`. Accepted ADRs require the explicit Step 3 absorption check below.

**Legacy plan docs** (prose files under `doc/` that are not in `adr/`, `tasks/`, `specs/`, `product/`; e.g. `doc/v0.2-cli-plan.md`): present as candidates only when the user explicitly names them. Do not auto-include — these have no `Status:` field, so judgement is required.

## Step 2 — Present the slate

Render one block per category with one line per candidate. Format:

```
### Tasks (done) — 3 candidates
- doc/tasks/0001-dogfood-agents-md.md      done   2026-05-08   "Apply kit to itself..."
- doc/tasks/0002-foundation-and-bootstrap.md  done   2026-05-08   "Foundation + bootstrap skill"
- doc/tasks/0029-skill-summary-frontmatter.md  done   2026-05-10   "Move skill descriptions into per-skill frontmatter"

### Specs (shipped) — 0 candidates
(none)

### PRDs (superseded) — 0 candidates
(none)

### ADRs (superseded / deprecated) — 2 candidates
- doc/adr/0019-domain-language-layer.md   superseded by ADR-0027   2026-05-10
- doc/adr/0024-failed-pattern.md           deprecated               2026-05-11
```

Print a one-line summary tail: `Total: N candidates across M categories. Hard-delete via git rm; git history retains. No CHANGELOG or archive subdir.`

If a category has zero candidates, render the heading and `(none)` — do not skip silently.

If the user named legacy plan docs, render them under their own `### Legacy plan docs (user-named) — N candidates` block.

## Step 3 — Confirm + accepted-ADR absorption gate

Ask the user which categories to sweep. Default phrasing:

> Proceed with all auto-included candidates? Or name a subset (e.g. "tasks only", "tasks + specs", "skip ADR-0019").

If the user wants to also remove one or more `Status: accepted` ADRs, run the absorption check before adding them to the removal set:

For each named accepted ADR:

1. Ask the user where the decision has been absorbed. Required form: `<file>#<section-or-anchor>` or `<file>:<line>` (e.g. `ARCHITECTURE.md#data-flow`, `GUIDELINES.md§Naming`, `src/lib/profiles.js:23`).
2. Extract two-to-four substance keywords from the ADR's title and Decision section (not the slug — substance). Example: ADR-0004 "File-based task tracking" → keywords `file-based`, `task tracking`, `doc/tasks`, `Markdown`.
3. Grep the absorption target for each keyword. Require at least one keyword to match. (Title-derived literal keywords may collide; substance keywords are the test.)
4. If the grep fails: refuse removal. Print:
   > ADR-NNNN absorption not verified. Substance keyword `<X>` not found in `<target>`. Absorb the rationale first (edit the binding doc), then re-run `/ad-archive` and re-name this ADR.
5. If the grep succeeds: add to the removal set, print the matched location as evidence.

Do not silently downgrade the check. The absorption rule is the design's load-bearing constraint — it is the reason hard-delete is safe.

## Step 4 — Execute

Single `git rm` invocation for all confirmed files (one shell call, atomic stage):

```bash
git rm doc/tasks/0001-...md doc/tasks/0002-...md doc/adr/0019-...md
```

Then run `git status --short` and print the staged deletions. Do not commit. Do not push. The user runs `/ad-commit` next to author the message and sign the DCO.

If `git rm` fails on any file (e.g. uncommitted local edits), abort the entire batch, print the error verbatim, and instruct the user to resolve the conflict before re-running.

## Step 5 — Hand off

Print exactly:

```
N file(s) staged for deletion. Git history retains content.
Discoverability: `git log --diff-filter=D --name-only -- doc/`

Next: /ad-commit
Suggested subject: `docs: archive <N> implemented <kind(s)>`
Suggested body: list removed slugs and the binding doc(s) the substance was absorbed into (for accepted-ADR removals).
```

## Output contract

Writes nothing to disk other than `git rm` staging. Never auto-commits. Refuses to remove `Status: proposed | in-progress | blocked | draft | accepted` artifacts except when the user explicitly names an accepted ADR and the absorption check passes. Refuses to create `CHANGELOG.md` or `doc/<kind>/archive/` subdirectories — both violate kit discipline (Rule #2 and the lean-tree value respectively).

## Next

- `/ad-commit` — author the deletion commit (Conventional Commits + DCO sign-off).
- `/ad-next` — re-run the state survey; removed artifacts disappear from Layer 4 / Layer 5 counts.
- `/ad-drift` — confirm no narrative document still cites the removed ADRs by slug as load-bearing context (decoration-citation rule per ADR-0030 §11).
