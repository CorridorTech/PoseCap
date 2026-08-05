---
name: ad-level-up
description: Curate the project's rule-set — add, refine, merge, or retire a convention. The companion to `ad-audit` — where ad-audit audits against the rules, this evolves them, leanly. Every candidate must clear four anti-overfitting gates (recurrence-or-deliberate-decision, generalisation, load-bearing root cause, proportionate cost) plus an effectiveness pass (is it a genuine improvement, does it duplicate an existing rule, does it catch real observed behaviour) or it is rejected out loud. Every drafted candidate then passes an adversarial multi-lens review — is it already covered? does it hold up? is it placed right? — and only survivors reach you. HARD human-in-the-loop — it NEVER writes without explicit approval; it presents a proposal with a plain-language rationale and applies only on your OK, one item at a time. Use on "add a convention", "update the rules", "new rule", "merge these rules", "we keep hitting X, make it a rule", "retire this rule", "/ad-level-up", or a rule-gap handoff from `ad-audit`.
summary: Human-gated rule-set curation, companion to ad-audit. Four anti-overfitting gates + effectiveness pass + adversarial multi-lens review of each candidate, then a HARD human-approval gate — never writes unprompted, one item at a time. Writes to the ADR-0035 machine store or the ADR-0043 project layer (.agentic/rules/).
allowed-tools: Read, Glob, Grep, Bash, Task, Edit, Write
---

# /ad-level-up

Evolve the rule-set without bloating it. Where `ad-audit` audits work against the rules, this skill curates the rules — adding only the generalising survivors, leanly, with evidence, and **never without your explicit approval**.

## Prime directive — HARD human gate

A full or drifting context, or a model having an off moment, must never edit the rule-set unsupervised — that is exactly when a bad write slips in. So: **NEVER write without explicit human approval.** Always present the proposal plus a plain-language rationale first; apply only on the user's OK, one item at a time. No batch writes, no "while I'm here" edits. This gate is enforced by this contract, not by tool permissions — hold to it even though `Edit` is available.

## Rules target

Two curated layers exist (ADR-0035 + ADR-0043); every accepted candidate targets exactly one:

- **Machine store** — a you-everywhere convention: `$AGENTIC_RULES_DIR` if set, else `~/.agentic/rules/`.
- **Project rules** — a this-project convention: `.agentic/rules/` at the repo root. On genuine conflict, a project rule shadows a machine-store rule (the audit reports the shadowing), so curate a project rule when the project deliberately deviates from the practitioner's global set.

Recommend the layer from the rule's own content (does it generalize beyond this repo?); the user confirms. Read the target layer before proposing (the edit needs a prior read; voice-matching needs the current text). If the target layer does not exist yet, say so — offer to create it on approval, rather than inventing a path. **First project-rule creation:** ask whether `.agentic/rules/` is **committed** (versions with the repo; the team inherits it) or **machine-local**; in machine-local mode, on approval, write the `.agentic/rules/` entry into `.git/info/exclude` yourself — never `.gitignore`, which is committed and team-visible. When you find an `.agentic/rules/` that is neither committed nor excluded (e.g. a fresh clone), re-offer the choice. A convention that belongs in a repo binding doc (`AGENTS.md`, `GUIDELINES.md`) or is bigger than a rule line routes to `/ad-adr` or `/ad-guidelines` instead — this skill owns the terse rule-set.

## Step 1 — State candidate + evidence

One sentence plus the citation (a finding, PR, transcript, or `file:line` — or the `ad-audit` handoff that surfaced it). If it cannot be cited, stop — it is not grounded, and a lone uncited slip is a memory note, not a rule.

## Step 2 — Trace to root cause

Where was this *seeded*? Attach the candidate to the upstream cause (an investigation / grounding / verification gap), not the surface symptom.

## Step 3 — Four anti-overfitting gates

All four must pass; reject the rest **out loud**:

1. **Recurrence or deliberate decision** — it recurs / matches a known prior pattern, OR it is a deliberate forward-looking standardisation. A lone accidental slip with neither is a memory note, not a rule.
2. **Generalisation** — it helps a whole class of future work, not just re-prevents this exact scenario.
3. **Load-bearing root cause** — an upstream cause that cascaded, not a leaf symptom.
4. **Proportionate cost** — it earns its keep against every reader carrying it forever (each extra rule lowers adherence to all the others). A rule preventing a rare, cheaply-caught-downstream slip is a net negative — reject it.

## Step 4 — Effectiveness pass

- **Classify:** improvement · correction · increment · **merge into an existing rule** · **extend an existing rule** · **reject**. Prefer sharpening / merging / extending over adding a new line.
- **Redundancy:** does an existing rule (or a repo binding doc) already watch this? If so, merge — never add an overlapping rule.
- **Real behaviour:** does it catch a defect actually observed (cite it), or a hypothetical? A rule guarding a defect nobody has hit is dead weight — reject or shelve as a note.
- **Dead-rule sweep:** if an existing rule no longer maps to real behaviour or is subsumed by another, flag it for retirement in the same proposal.

## Step 5 — Deterministic placement

Place by grounding-target / failure-mode, never by nearest heading. Assign the rule to the group whose grounding-target it matches. Keep the group set minimal — a NEW group only when a defect class is demonstrably uncovered by every existing group; split a group only when its rule count grows too large (then split along its grounding-target). Give the rule the next stable id in its group.

## Step 6 — Draft the minimal edit

Read the target rule file(s) first. Write the terse imperative rule under its group, and — when there is a why worth keeping — its rationale alongside. One rule, lean. Do not write to disk yet.

## Step 7 — Adversarial multi-lens review of the candidate

Fan out fresh-context reviewers (one `Task` call per lens, routing to the bundled `rule-candidate-reviewer`), each trying to REFUTE the candidate against the ACTUAL current rule files — never assume. Run all three lenses.

- **(a) already-covered** — is this rule or its effect already enforced by an existing rule / binding doc? Cite the covering rule. If covered, the disposition is **reject** (fully covered) or **merge** (sharpen the existing rule).
- **(b) coherence + necessity** — does it hold up? Is it the minimal change? Does it clear the four gates and the placement principles?
- **(c) placement** — is the group / id right, or does it belong elsewhere?

The review filters and reclassifies (survive-as-add / merge / reject); it never writes and never bypasses the human gate.

## Step 8 — Report + gate

Present:

- the proposed delta (exact old → new per file, at the resolved rule-set path);
- the gate table (candidate · recurrence · generalisation · root-cause · cost · verdict);
- the effectiveness line (classification · redundancy · real-behaviour · dead-rule sweep result);
- the adversarial-review verdicts per lens (citing the covering rule on any reject/merge);
- a plain-language rationale (one short paragraph);
- a "considered but rejected as overfitting" list, each with the gate it failed.

**Apply only on the user's explicit approval, one item at a time.** On approval, make the minimal change — `Edit` an existing rule file, or `Write` to create the rule-set file at the resolved location when it does not exist yet; then stop and await the next item.

## Output contract

- A proposal (delta + gate table + effectiveness line + adversarial verdicts + rationale + rejected-as-overfitting list) — **presented, not applied**.
- One `Task` invocation of `rule-candidate-reviewer` per lens.
- On explicit approval: the minimal edit to the rule-set at the ADR-0035 location, one item at a time. Nothing written without approval.

## Next

- Re-run `/ad-audit` after a rule lands to confirm it catches what it was written for.
- For a decision bigger than a rule line: `/ad-adr` (architectural) or `/ad-guidelines` (engineering standards).
- `ad-audit`'s Step 8 handoff is this skill's Step 1 candidate.
