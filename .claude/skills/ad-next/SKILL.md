---
name: ad-next
description: Survey the project's state across the six-layer artifact stack and recommend prioritized next actions, modeled on `flutter doctor`. Use when the user asks "what's next", "next step", "where am I", "project status", "doctor", "what should I do", "audit my workflow", or whenever a navigation aid is needed mid-flow. Read-only; complements `ad-drift` (drift detection, a different question). Profile-aware — `poc` suppresses Layer 3 / 4 / 5 noise, `team` / `mature` run the full survey.
summary: State survey + prioritized next-action recommendations across the six-layer artifact stack. Read-only navigation aid (`flutter doctor` pattern).
allowed-tools: Read, Glob, Grep, Bash
---

# /ad-next

Read-only state survey + prioritized next-action recommendations. Mirrors `flutter doctor` shape: layer-by-layer status + concrete fix per finding. Complements `ad-drift` — audit answers "is anything wrong?", next answers "what should I do?".

The skill writes nothing. Output is recommendations the user copies into the next conversation turn or the next CLI invocation.

## Step 0 — Read state

Detect baseline:

* Profile + kit version: read `.claude/agentic-state.json` and `.agents/agentic-state.json` if present. Profile defaults to `team` per ADR-0013 when state file missing or no profile field.
* Filesystem signals at the repo root: `AGENTS.md` / `CLAUDE.md`, `GUIDELINES.md`, `ARCHITECTURE.md`, `DESIGN.md`, `WORKFLOW.md`, `README.md`, `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`, `.husky/` / `lefthook.yml` / `.pre-commit-config.yaml`, `.github/workflows/`, `.git/HEAD` (current branch).
* Meaningful-code signals: non-trivial files under `src/`, `app/`, `lib/`, `test/`, `tests/`, `packages/`, framework entrypoints, or manifests with real scripts/dependencies. Treat only README/LICENSE/gitignore files, agentic state, empty artifact directories, and empty manifests as trivial.
* Durable product-framing signals: PRD, specs, tasks, or README/docs/code that let you summarize the target user, problem, and current product behavior. Framework scaffolds or a few early files without that framing still count as unframed greenfield.
* Per-artifact directories: list `doc/product/`, `doc/specs/`, `doc/adr/`, `doc/tasks/`. Read each file's frontmatter (`Status:`, `Created:`, `Spec ref:` for tasks) but **not** the full body — survey is fast and broad.
* Git state: current branch, commits ahead of `main` (`git rev-list --count main..HEAD`), unpushed commits, working-tree dirtiness.
* Root-doc freshness: inspect headings and references only. If a PRD exists but `AGENTS.md` / `CLAUDE.md` does not reference `doc/product/` / `PRD`, mark the operational guide as possibly stale and recommend refreshing via `/ad-bootstrap` after the product contract.

Do not parse skill bodies. Do not run tests. Do not invoke other skills. The survey is shallow by design.

## Step 1 — Classify scenario before ranking

Layer status is evidence; scenario determines the right next step.

- **Fresh / unframed greenfield:** no durable product framing, even if a framework scaffold or a few early files already exist. This is a product-framing problem, not an `AGENTS.md` problem.
- **Product-framed greenfield:** PRD exists, but no meaningful code yet. This is where `/ad-bootstrap`, `/ad-guidelines`, optional `/ad-design`, then `/ad-spec` become the normal sequence.
- **Brownfield:** meaningful code exists and the scan can summarize the current product behavior. Existing code can supply product and architecture evidence; `/ad-bootstrap` is scan-first here and may precede PRD backfill.
- **Feature planning:** PRD/spec artifacts exist and have downstream gaps (accepted PRD with no specs, accepted spec with no tasks).
- **Implementation in progress:** dirty tree, branch ahead of `main`, in-progress tasks, blocked tasks, or proposed ADRs.
- **Maintenance / install hygiene:** stale kit state, profile/install mismatch, missing expected conditional skills.

If scenarios overlap, report the strongest active scenario in this order: implementation in progress, maintenance/install hygiene, feature planning, product-framed greenfield, brownfield, fresh/unframed greenfield. If code exists but product behavior cannot be summarized, choose fresh/unframed greenfield rather than brownfield.

## Step 2 — Layer-by-layer status

Render six sections in this exact order. For each section, list what is present, what is in flight, what is missing or stale. Use words for status (`present`, `in flight`, `missing`, `stale`) — no emoji.

**Layer 1 — Constitution.**
- `WORKFLOW.md` present? (kit-shipped — should always be there)
- `AGENTS.md` (or `CLAUDE.md`) present?
- `GUIDELINES.md` present?
- `AGENTS.md` missing is not the first greenfield finding when product framing is missing; recommend product discovery / PRD first, then `/ad-bootstrap`.

**Layer 2 — Domain (`CONTEXT.md`).**
- `CONTEXT.md` present at repo root, *or* `CONTEXT-MAP.md` plus per-context `CONTEXT.md` files for multi-context repos? (Lazy-created per ADR-0019 — `missing` is a valid state for projects whose first domain term has not been resolved yet, not a finding to flag in `poc` / `solo`.)
- For each present `CONTEXT.md`, report whether the Language section has at least one term with an `_Avoid_:` line — empty glossary is worse than no glossary.

**Layer 3 — Product (`doc/product/`).**
- `doc/product/PRD.md` present (single-product), *or* `PRODUCT-MAP.md` plus per-product `<slug>.md` files (multi-product)? (Lazy-created per ADR-0027 — `missing` is a valid state at `poc` profile, where PRD is excluded entirely.)
- In fresh/unframed greenfield at solo/team/mature, missing PRD is the primary navigation finding.
- For each present PRD, report `Status` (`draft` / `accepted` / `superseded`) and the count of feature specs whose `Related → PRD` field points at it. Flag PRDs with `Status: accepted` and zero implementing specs — same stuck-state pattern as accepted-spec-with-zero-tasks at Layer 4.

**Layer 4 — Specs (`doc/specs/`).**

For each spec file, report `Status` and the count of tasks whose `Spec ref` field points at it:

```
0001-auth-flow.md (accepted, 0 implementing tasks)
0002-onboarding.md (shipped, 3 tasks done)
```

Flag specs with `Status: accepted` and zero implementing tasks — that is the most common stuck state.

If frontend signals exist, also report `DESIGN.md` as the visual contract. Missing `DESIGN.md` is a recommendation before `/ad-spec` only when frontend tokens/styles exist or the next feature touches UI.

**Layer 5 — Plans / Decisions.**

`ARCHITECTURE.md` — present? Missing architecture is a finding for `team` / `mature` brownfield projects with meaningful system patterns, or when a spec creates load-bearing architectural constraints. It is not the first step in fresh greenfield.

`doc/adr/` — count by status: `proposed`, `accepted`, `deprecated`, `superseded`. Flag any `proposed` ADRs explicitly with their slug — they need a decision.

`doc/tasks/` — count by status: `proposed`, `in-progress`, `blocked`, `done`. List in-progress and blocked tasks with their slugs and `Spec ref`. Flag tasks with no `Spec ref` and no `Board ref` as orphans (no clear scope tie).

**Layer 6 — Code.**
- Branch: `<name>` (`<n>` commits ahead of `main` if applicable).
- Tests: wired? (presence of `npm test` script / `pytest` / `cargo test` / `go test ./...`).
- Hooks: wired? (presence of `.husky/`, `lefthook.yml`, `.pre-commit-config.yaml`, or active `.git/hooks/` scripts).
- CI: wired? (presence of `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/`).

## Step 3 — Cross-cut signals

A few signals do not belong to one layer:

- **Pending fresh-context review.** If branch is ≥1 commits ahead of `main` and no `.agentic/reviews/<ts>-*.md` exists for the current range, flag `ad-review` as a recommendation.
- **Spec ↔ task reciprocity.** Tasks with non-empty `Spec ref` whose target spec does not exist → orphan task. Specs with `Status: accepted` or `shipped` and zero entries in their `Related → Tasks` list → spec without implementing tasks.
- **Profile vs install state.** Profile says one set of skills; state file lists another. Surface the divergence and recommend `agentic update` or `agentic profile set <name>`.
- **Stale state file.** `kitVersion` in state file ≠ currently-running kit. Recommend `agentic update`.

## Step 4 — Prioritize next actions

Rank findings by workflow leverage, not by document layer number. Return 3–5 concrete invocations, each as a one-line "do X next" with the slug or path that makes the action unambiguous.

Priority heuristic:

1. **Protect active work.** Blocked tasks, proposed ADRs blocking implementation, dirty/ahead branch needing `/ad-review`, stale state that makes installed skills unreliable.
2. **Fresh / unframed greenfield.** For solo/team/mature, recommend `/ad-grill-me` when the product ask is fuzzy or `/ad-prd` when it is clear; then `/ad-bootstrap`. Do not recommend `/ad-bootstrap` first, even when a framework scaffold already exists.
3. **Product-framed greenfield.** If PRD exists, recommend `/ad-bootstrap` when `AGENTS.md` / `CLAUDE.md` is missing or stale, then `/ad-guidelines`, optional `/ad-design`, then `/ad-spec`.
4. **Brownfield.** If meaningful code exists and `AGENTS.md` / `CLAUDE.md` is missing, recommend `/ad-bootstrap` scan-first. Then recommend `/ad-guidelines` for standards, `/ad-architecture` for team/mature system patterns, or `/ad-prd` only when product scope is being backfilled or changed.
5. **Feature pipeline gaps.** Accepted PRD without specs → `/ad-spec`; accepted spec without tasks → `/ad-task`; missing research before implementation → `/ad-ground`.
6. **Quality gates and drift.** Mature hooks missing → `/ad-hooks`; orphan tasks/spec mismatches → `/ad-drift`; kit/profile drift → `agentic update` or `agentic profile set <name>`.

If nothing actionable surfaces, say so explicitly — empty output is real signal, not a gap. Phrase: "No urgent next action. Continue current work or invoke `/ad-drift` for a full drift check."

## Step 5 — Profile-aware filtering

Apply per-profile rules at the end so the user sees output matched to their maturity:

- **`poc`:** suppress Layer 3 (Product), Layer 4 (Specs), and Layer 5 (ADRs / tasks) sections entirely if those directories do not exist. Show Layer 1 + Layer 2 + Layer 6 only. Layer 2 (Domain) and Layer 3 (Product) render informationally — `CONTEXT.md` missing and `PRD.md` missing are *not* findings at `poc` (both are lazy-created; PRD is also profile-excluded). Recommendation set: `/ad-grill-me` for fuzzy exploration, `/ad-ground` for research-ready questions, `/ad-spike` when the technique is uncertain, `/ad-drift` for drift, `agentic update` for staleness. Do not recommend `/ad-prd`, `/ad-spec`, `/ad-task`, `/ad-bootstrap`, `/ad-guidelines`, `/ad-architecture`, `/ad-adr`, or `/ad-hooks` unless the user is graduating the project out of `poc`.
- **`solo`:** Layer 3 / Layer 4 / Layer 5 render but ADR / `ARCHITECTURE.md` absence is informational — no "needs action" flag. PRD is universal for real products, but fresh greenfield still starts with product framing before `/ad-bootstrap`; brownfield quick fixes do not need PRD backfill before the fix. Specs are universal; spec-without-tasks remains a real finding. Layer 2 — same lazy-creation rule as `poc`.
- **`team`:** full survey. Default profile. Fresh greenfield still routes through product discovery / PRD before `/ad-bootstrap`; brownfield may bootstrap scan-first from existing code.
- **`mature`:** additionally flag hooks-not-wired louder ("WORKFLOW §11 binding for `mature` profile — `/ad-hooks` recommended"). Keep `/ad-hooks` after product/operational context unless the only finding is missing gates.

## Output contract

A single Markdown message structured as:

```
## ad-next

**Profile:** <name> (kit v<X.Y.Z>)
**Branch:** <name> (<n> commits ahead of main)
**Scenario:** <detected scenario>

### Layer 1 — Constitution
<one-line status per artifact>

### Layer 2 — Domain (CONTEXT.md)
<present / lazy-missing; glossary-empty flag if file exists but has no terms>

### Layer 3 — Product (doc/product/)
<present / lazy-missing; PRD status + implementing-spec count if file exists>

### Layer 4 — Specs (doc/specs/)
<spec list with status + task count, or "no specs"; DESIGN.md status when frontend signals exist>

### Layer 5 — Plans / Decisions
<ADR + task summaries with explicit flags>

### Layer 6 — Code
<branch / tests / hooks / CI status>

### Recommended next (priority)
1. <action> — <one-line reason>
2. <action> — <one-line reason>
...
```

No file written. No state mutation. Recommendations are advisory; the user decides whether to invoke. Cross-references `ad-drift` (drift detection), `agentic update` (kit drift — CLI subcommand, not a skill), `agentic profile` (profile changes — CLI subcommand, not a skill) where they apply.

When the host exposes `AskUserQuestion` and the user follows up with a confirmation question after seeing the recommendations, prefer the structured prompt over inline text.
