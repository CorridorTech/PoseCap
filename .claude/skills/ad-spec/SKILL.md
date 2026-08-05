---
name: ad-spec
description: Draft a feature-level specification at doc/specs/NNNN-<slug>.md following the kit's six-layer artifact stack (Constitution → Domain → Product → Spec → Plan/Decisions → Code). Adapts GitHub Spec Kit's mandatory sections (User Scenarios, Requirements, Success Criteria) to the kit's documentation discipline. Use when the user wants to write, draft, scaffold, or open a feature spec, feature brief, user stories, or success criteria for one feature multiple tasks will implement. Product-level scoping (PRD, multi-feature roadmap, target user, product success metrics) belongs to `ad-prd` (Layer 3); this skill is feature-level only. Status starts at draft; the file is the binding feature contract once accepted; references parent PRD for product-scope inheritance.
summary: Draft a feature spec at `doc/specs/NNNN-<slug>.md` (Spec Kit-aligned mandatory sections). Layer 4 of the six-layer artifact stack. References parent PRD (`ad-prd`, Layer 3) for product-scope inheritance.
allowed-tools: Read, Write, Glob, Bash
---

# /ad-spec

Drafts `doc/specs/<NNNN>-<short-slug>.md` for one feature. Status lifecycle: `draft` → `accepted` → `shipped` | `superseded by SPEC-NNNN`. Spec is the layer-4 artifact in the kit's six-layer stack — Constitution (`AGENTS.md` + `WORKFLOW.md`) → Domain (`CONTEXT.md`) → Product (`doc/product/PRD.md`) → **Spec (this skill)** → Plan/Decisions (`ARCHITECTURE.md` + `doc/adr/` + `doc/tasks/`) → Code. Multiple tasks implement one spec; ADRs may be driven by spec constraints. The Domain layer (`CONTEXT.md`, ubiquitous language per Evans 2003) is the source of canonical nouns the spec must use; if the spec introduces a new noun, resolve it through `CONTEXT.md` first. The Product layer (`PRD.md`) is the source of target user, product-level success metrics, and cross-feature constraints the spec inherits from; a feature spec whose target user or success metric contradicts the PRD is drift that `ad-drift` flags.

## Step 1 — Determine NNNN and slug

List `doc/specs/`. NNNN = next available 4-digit number after the highest existing (mirrors the ADR and task conventions). If `doc/specs/` does not exist, create it; start at `0001`. Slug: kebab-case, ≤6 words, derived from the feature title.

## Step 2 — Confirm scope

The spec captures **one** feature. If the user's request implies multiple features, ask which one to write first; the others become follow-up specs. A "feature" here is the smallest user-visible outcome that has its own success criteria — not a task (work unit) and not a binding architectural decision (ADR).

## Step 3 — Interview to fill

Ask one question per missing field, in this order. Skip the philosophical questions and the questions whose answers are already obvious from the conversation.

* **Context:** business context first. *Why* the feature exists, the user / constraint / problem it addresses, the cost of *not* building it.
* **User Scenarios:** Given-When-Then for the key flows. Each scenario must be independently testable. Multiple scenarios when the feature has more than one path.
* **Functional Requirements:** testable statements. Plain bullets (no checkbox — Spec is decision-record, not tracking; implementation tracking lives in per-Spec tasks). *"User can sign in with email and password"* — yes. *"Authentication should be secure"* — no, that's not a requirement, it's a hope.
* **Non-functional Requirements:** performance, security, accessibility, observability — only the constraints that bind. Plain bullets. Skip when there are none.
* **Success Criteria:** measurable per `WORKFLOW.md` §1. Plain bullets — pass/fail must be observable, not aspirational. *"Loads in under 2 seconds at p95 over 7 days"* — yes. *"Loads fast"* — no. Per-criterion progress tracking lives in tasks; the Spec carries the criteria definitions and a single `Status:` field per ADR-0030 §1.
* **Edge Cases:** empty inputs, large inputs, concurrent access, missing prerequisites, permission errors. Surface them before code is written, not after a bug report.
* **Out of Scope:** explicit non-goals. Anything readers might assume is in scope but isn't. Prevents scope creep without an audit trail.
* **Open Questions:** deferred decisions. Each becomes a follow-up ADR or an explicit punt with a rationale.
* **Related:** ADRs touched by this spec, tasks implementing it (filled lazily as tasks are created), other specs this one supersedes or depends on.

Status starts at `draft`. Created: today, ISO format. Owner: ask. Do **not** invent values — when the user does not know, leave `<TODO>` and ask.

## Interview UX

When the host exposes `AskUserQuestion`, use it for multi-choice prompts (`Status: draft / accepted / shipped`, owner selection from team members, scope-vs-multiple-features confirmation) and for confirmation gates with non-trivial branching. Inline text questions are an acceptable fallback only when the host lacks a structured-prompt primitive (Codex). One question per gate; do not chain three text questions when one `AskUserQuestion` card lists the options.

## Step 4 — Write the file

Path: `doc/specs/<NNNN>-<short-slug>.md`. Use the template below.

Stop after writing. Do **not** flip status to `accepted` — that requires user review.

## Step 5 — Editing guidance for later turns

When the user later works on the spec, edit the file by:

* Appending to **Open Questions** (close them with the resolution; never delete them).
* Flipping `Status` to `accepted` once the user signs off and tasks start being created.
* Flipping `Status` to `shipped` after release — once all per-Spec tasks complete.
* Flipping `Status` to `superseded by SPEC-NNNN` when a later spec replaces this one.
* Adding `Tasks` entries to `Related` as tasks are created against this spec.

Implementation tracking (per-criterion progress) lives in the per-Spec tasks, **not** in the Spec itself. The Spec is the contract; tasks track its construction.

Never rewrite existing prose — append rationale to **Open Questions** as a resolution paragraph rather than mutating the original requirement text.

## Template — `doc/specs/NNNN-<slug>.md`

````markdown
# Spec `<NNNN>`: `<short imperative title>`

**Status:** `<draft | accepted | shipped | superseded by SPEC-NNNN>`
**Created:** `<YYYY-MM-DD>`
**Owner:** `<name or role>`

## Context

`<Why this feature exists. The user, the constraint, the problem. What would break if this feature did not ship.>`

## User Scenarios

`<Given-When-Then for the key flows. Each scenario independently testable.>`

- **Scenario 1:** `<short title>`
  - Given `<starting state>`
  - When `<action>`
  - Then `<observable outcome>`

## Requirements

### Functional

- `<R1: testable statement>`
- `<R2>`

### Non-functional

- `<perf / security / a11y / observability — only when binding>`

## Success Criteria

Definitional. Measurable conditions; pass/fail observable, not aspirational. Per-criterion progress tracking lives in per-Spec tasks, not here.

- `<criterion 1: measurable, observable>`
- `<criterion 2>`

## Edge Cases

- `<empty input behavior>`
- `<large input / failure modes>`
- `<permission / concurrency / state-restoration cases>`

## Out of Scope

`<Explicit non-goals. Anything readers might assume is in scope but isn't.>`

## Open Questions

`<Deferred decisions. Each becomes an ADR or a documented punt.>`

## Related

- ADRs: `<list with links — written as the spec is accepted>`
- Tasks: `<doc/tasks/NNNN-... — appended as tasks are created>`
- Supersedes / Depends on: `<other spec links if any>`
````

## Output contract

A single new file at `doc/specs/<NNNN>-<short-slug>.md`. Status `draft`. Tasks list empty (filled lazily as tasks land). No existing specs modified. No invented values.

The spec is a narrative document but is exempt from ADR-0008's no-dates rule for the same reason ADRs and tasks are: the `Status` lifecycle and `Created` field are part of the auditability primitive. The remaining documentation discipline rules apply at write time:

- No emoji anywhere in the file.
- `Context` is the business-context-first section — *why* the feature exists before *what* it does.
- One scope: one feature per spec. Multiple features implies multiple specs.
- No speculation. Open Questions go in their named section; everywhere else captures decisions.
- No commented-out requirements or TODO/FIXME — every deferred item references a tracked work item or lives under Open Questions.

## Next

- `/ad-ground` for the four-source research pass before code (WORKFLOW §4 + §5).
- `/ad-task` to break the spec into work units; each task carries a `Spec ref` field pointing back to this file.
- `/ad-adr` if scoping the spec surfaced a binding architectural decision worth recording (one decision per ADR).
- Flip Status to `accepted` once you sign off and tasks start being created. Flip to `shipped` after release.
