---
name: ad-task
description: Draft a new task tracking file at doc/tasks/NNNN-<short-slug>.md, using a checkbox-toggle + append-only-Notes format optimized for LLM editing. Use when the user wants to create, draft, scaffold, or open a task, ticket, work item, or backlog entry tracked in the repo. Status starts at proposed; the file is the source of truth, not a board.
summary: Draft a new task at `doc/tasks/NNNN-<slug>.md`.
allowed-tools: Read, Write, Glob, Bash
---

# /ad-task

Drafts `doc/tasks/<NNNN>-<short-slug>.md` for one tracked task. Format chosen so status changes via single checkbox toggles and Notes is append-only — cheap, reviewable, idempotent edits.

## Step 1 — Determine NNNN and slug

List `doc/tasks/`. NNNN = next available 4-digit number after the highest existing (mirrors the ADR convention). If `doc/tasks/` does not exist, create it; start at `0001`. Slug: kebab-case, ≤6 words, derived from the user's task title.

## Step 2 — Interview to fill

Ask one question per missing field, in this order:

* **Context:** why this task exists, what problem it solves, any assumption being tested.
* **Acceptance Criteria:** measurable conditions. Each is a checkbox; pass/fail must be observable, not aspirational ("loads in under 2s", not "fast enough").
* **Plan:** concrete sequential steps with file paths where applicable. Each is a checkbox.
* **Owner:** ask.
* **Execution:** `AFK` when the task is specified enough for an agent to execute with bounded context and disjoint write scope; `HITL` when it needs human judgment, taste, external access, or frequent back-and-forth.
* **Spec ref:** ask; leave blank when no spec drives this task. When a feature spec exists at `doc/specs/NNNN-<slug>.md`, link it here so the spec's `Related → Tasks` list reciprocates.
* **Board ref:** ask; leave blank if solo work.

Status starts at `proposed`. Created: today, ISO format. Notes: empty (filled during execution). Definition of Done section: copy verbatim from the template.

**Do not invent values.** When the user does not know something, leave `<TODO>` and ask. Stop after writing the file — do not start work.

## Interview UX

When the host exposes `AskUserQuestion`, use it for multi-choice prompts (status, owner selection, Spec-ref pick from existing `doc/specs/`) and for confirmation gates with non-trivial branching. Inline text questions are the fallback only when the host lacks a structured-prompt primitive (Codex). Single card per multi-choice gate beats chained text questions.

## Step 3 — Write the file

Path: `doc/tasks/<NNNN>-<short-slug>.md`. Use the template below.

## Step 4 — Editing guidance for later turns

When the user later works on the task, edit the file by:

* Toggling checkboxes (`- [ ]` → `- [x]`).
* Appending to Notes (date each entry, `### YYYY-MM-DD`).
* Never rewriting existing sections.

Status flips to `done` only when every Acceptance Criterion and every Definition of Done item is checked.

A checkbox is checked only after everything it names has actually happened — never in anticipation. Split a bundled step (e.g. "open PR; merge on CI green") into separate items when its parts complete at different moments; a checked box claiming an unfinished step is a false record.

## Template — `doc/tasks/NNNN-<slug>.md`

````markdown
# Task `<NNNN>`: `<short imperative title>`

**Status:** `<proposed | in-progress | blocked | done>`
**Created:** `<YYYY-MM-DD>`
**Owner:** `<name or role>`
**Execution:** `<AFK | HITL>`
**Spec ref:** `<doc/specs/NNNN-<slug>.md or SPEC-NNNN — blank when no spec drives this task>`
**Board ref:** `<external ticket URL or ID — blank for solo work>`

## Context

`<Why this task exists. What problem it solves. Any assumption being tested.>`

## Acceptance Criteria

Verifiable conditions. Each as a checkbox so progress is point-editable.

- [ ] `<criterion 1>`
- [ ] `<criterion 2>`
- [ ] `<criterion 3>`

## Plan

Concrete sequential steps. Each as a checkbox. Reference file paths where applicable.

- [ ] `<step 1: action with file path if applicable>`
- [ ] `<step 2>`
- [ ] `<step 3>`

## Notes

Append-only log. Date each entry. Never rewrite past entries.

### `<YYYY-MM-DD>`

`<observation, decision, blocker, learning>`

## Definition of Done

All Acceptance Criteria checked, plus:

- [ ] Local tests pass (or N/A documented in Notes)
- [ ] Code review completed (human or fresh-context reviewer per WORKFLOW §10)
- [ ] No orphan `TODO`/`FIXME` introduced
- [ ] Status updated to `done` and Notes log closes the task
````

## Output contract

A single new file at `doc/tasks/<NNNN>-<short-slug>.md`. Status `proposed`. Notes empty. No existing tasks modified. No invented values.

Task files are decision-record artifacts and are **exempt** from the no-dates rule (Documentation Discipline §2): the `**Created:**` field anchors the task in time and the append-only `Notes` log is dated per entry by design. The remaining Documentation Discipline rules (`WORKFLOW.md` §2) apply at write time:

- No emoji anywhere in the file.
- `Context` is the business-context-first section — *why this task exists* and *what would break without it* before *Acceptance Criteria*.
- One scope: one task per file. If the user's request implies multiple deliverables, ask which to write first; the others become follow-up tasks.
- No speculation. Acceptance criteria must be measurable; do not list aspirational items ("loads in under 2s", not "fast enough").
- `Notes` is append-only and dated per entry — that is the auditability primitive, not a violation of Rule 2.

## Next

- Implement. Toggle Acceptance Criteria checkboxes and append to `Notes` as work lands.
- `/ad-review main..HEAD` (or current scope) before merge — the task DoD requires a fresh-context §10 review.
- Flip Status to `done` once every Acceptance Criterion and Definition-of-Done item is checked.
- If the task implements a spec, the spec's `Related → Tasks` list should reciprocate the link.
