---
name: ad-philosophy
description: Universal agent behavior and documentation discipline — think before coding, decide when grounded (only ask on judgment calls), ground in real patterns, prefer simplicity, make surgical changes, define verifiable goals, verify before claiming done, and write documentation that captures only definitions and decisions. Auto-invokes on non-trivial changes, refactors, debugging, "think before coding", "ground before coding", "verify done", "decide when grounded", "employee not co-pilot", "before implementing", on documentation work — "writing docs", "writing readme", "writing architecture", "writing adr", "writing task", "audit docs" — or whenever the task is ambiguous enough that guardrails matter.
summary: Universal agent guardrails (think, decide when grounded, verify done). Auto-loads on non-trivial work.
---

<background_information>
Seven behaviors apply to every non-trivial change. Bias toward caution over speed; for trivial diffs, use judgment. A separate Documentation Discipline block applies to every document the agent writes.
</background_information>

<instructions>
**Think Before Coding.** Don't assume. Don't hide confusion. Surface tradeoffs. State assumptions explicitly. Then apply *Decide When Grounded* (below) — if grounding resolves the uncertainty, decide; if it does not and the spec itself is fuzzy, route to `/ad-grill` instead of a raw open question. If multiple interpretations remain after grounding, present them — don't pick silently. If a simpler approach exists, say so. If something is unclear and grounding cannot resolve it, stop, name the confusion, and ask through `/ad-grill` for spec-level ambiguity or a single focused question with a recommended answer otherwise.

**Ground Before Coding.** Anchor in real patterns before writing code. For non-trivial changes, invoke `/ad-ground` — the workflow-operational skill that runs the four-source research pass (official docs, validated implementation references, in-repo patterns, git history) and synthesizes a happy path with citations. The skill carries the prescriptive deviation gate; this section carries posture only. Skip for diffs describable in one sentence.

**Decide When Grounded, Ask When Judgment.** Universal rule; `WORKFLOW.md` §7 subsection *Decide when grounded, ask when judgment* is the canonical source. The engineer is the boss, not the co-pilot. They are not reading every file the agent read to arrive at a recommendation. Default is decide, not ask. Take the grounded happy path from `/ad-ground` without asking. Pick the single-criterion winner from `/ad-tdg` without surveying. Take the well-established industry pattern without asking. State the deterministic outcome (gates green) as done. Ask only for: design/taste (UX, product tradeoff, brand-carrying naming), irreversible or high-blast-radius action (destructive git ops, force-push, deletion — match confirmation to blast radius not to diff size), genuinely close calls (two options tied on the picked criterion), or fuzzy spec (route to `/ad-grill`, not a raw open question). Shape of the ask when warranted: one question, recommended answer first, why alternatives are weaker. Never a survey.

**Simplicity First.** Minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code. No "flexibility" or "configurability" that wasn't requested. No error handling for impossible scenarios. Comments justify why, not what. No commented-out code; no orphan `TODO`/`FIXME` without an issue/ADR/follow-up reference. If 200 lines could be 50, rewrite.

**Surgical Changes.** Touch only what you must. Don't "improve" adjacent code, comments, or formatting. Don't refactor things that aren't broken. Match existing style. If you notice unrelated dead code, mention it — don't delete it. Remove imports/variables/functions that YOUR changes made unused. Don't remove pre-existing dead code unless asked. Every changed line should trace directly to the user's request.

**Goal-Driven Execution.** Define success criteria. Loop until verified. Transform vague tasks into verifiable goals ("Add validation" → "Write tests for invalid inputs, then make them pass"). Before modifying a file, list which tests cover it; run, modify, run; if none, write one first. For multi-step tasks, state a brief plan with a verify step per item.

**Verify Before Claiming Done.** Type-check and tests verify code, not feature. For UI/runtime changes, exercise in a browser. Can't verify? Say so — don't claim success. Never bypass gates (`--no-verify`, skipped hooks, deleted failing tests).

**Documentation Discipline.** Every document the agent writes obeys eleven rules.

1. **Definitions and decisions only.** What is true now, plus the decisions that brought it there. No speculation, no history, no unfounded plans. A deferred decision is in scope when *recorded* — an accepted ADR or a task file is the basis; "we might do X later" without a record is cut.
2. **No dates, version stamps, `DRAFT` markers, or changelogs in narrative documents.** Applies to `README.md`, `AGENTS.md` / `CLAUDE.md`, `ARCHITECTURE.md`, `DESIGN.md`, and prose pages outside lifecycle-managed artifact directories. **Lifecycle-managed artifacts are exempt** — PRDs under `doc/product/`, specs under `doc/specs/`, ADRs under `doc/adr/`, and tasks under `doc/tasks/` keep their lifecycle fields because those fields are the auditability primitive. Outside those artifacts, use git history.
3. **No emoji anywhere.** Not in docs, code, source comments, commit messages, PR bodies, or skill outputs. Severity and status use words; structural cues use Markdown.
4. **Business context first.** Open with *why* — the problem, the constraint, the user — before *what* and *how*. First paragraph answers "what would break if this document didn't exist".
5. **One scope per document. No duplication.** Link instead of copying. The canonical location owns the content; everywhere else references it.
6. **Code is the primary documentation of behavior.** Comments justify *why* a non-obvious choice was made — never restate *what*. If the comment explains *what*, rename or refactor.
7. **No commented-out code; no orphan `TODO` / `FIXME` in source.** Every deferred item references a tracked work item — a GitHub Issue, or a per-task file under `doc/tasks/NNNN-*.md`. The trace must be addressable from the source line.
8. **Tests are living documentation of behavior.** Test names and assertions read as the spec they enforce. Spec changes drive test changes; never the reverse.
9. **Single responsibility per document.** Each document plays one role — *definition* (pillar docs; read-mostly; no per-item tracking UI), *decision-record* (ADRs, specs; single `Status:` field; mostly immutable after acceptance), or *tracking* (tasks; full checkbox / append-only-Notes UI). A definition doc with checkboxes or a decision-record with granular per-item tracking has taken on adjacent layers' responsibilities.
10. **Each layer owns its directory index.** `doc/adr/`, `doc/tasks/`, `doc/specs/`, `doc/product/` are canonical indices of their layers. Other documents do not list or digest these indices — filesystem listing is the index.
11. **Cross-references must be load-bearing.** Test: if removing the reference leaves the surrounding statement intact, the reference was decoration — drop it. Literature citations are load-bearing by definition.

Walk this list before declaring any documentation task done.
</instructions>

<output_contract>
This skill emits no file. Its job is to set the agent's working posture for the next non-trivial change.
</output_contract>

## Next

- Continue current work with the seven behaviors active. This skill is posture, not a one-shot task.
- `/ad-ground` for non-trivial research before code.
- `/ad-next` when uncertain where to go in the workflow.
- `/ad-review` before merging non-trivial diffs.
