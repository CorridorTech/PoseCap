# Pragmatic Workflow: Engineering with LLMs

Engineering production code with LLMs. Agentic, not vibe coding.

**The Steve Rogers framing.** The LLM is the super-soldier serum. The engineer is Steve Rogers. The serum amplifies what the engineer already brings — solid bases, organization, investigation, care for quality, architecture, clean code, documentation, observability, maintainability. Add the serum to a disciplined engineer and you get Captain America. Add it to an undisciplined one and you get faster sloppy at scale. This document is those bases written down as principles. The discipline is the input; the LLM is the amplifier; the kit (skills, ADRs, audits, gates) is the scaffolding that keeps the discipline intact across sessions, agents, and projects.

**The principle behind the rest:** context engineering beats prompt engineering. Context is finite and decays as it fills — aim for the smallest set of high-signal tokens that gets the outcome. Operationally: one task per session, reset rather than extend. A long-running conversation crosses from the model's high-precision zone into a low-precision one as the cross-references multiply; smaller, deliberately-loaded contexts beat larger, accreted ones.

For visual maps of the recurring flows, see [`WORKFLOW-FLOWS.md`](WORKFLOW-FLOWS.md). This file remains the canonical prose contract.

## TL;DR

Agents do not replace engineering. They speed up execution, but they make specification, context, validation, and review *more* important than before.

What to keep in mind:

1. **Context is the product.** The agent performs only as well as the context you give it. Small, clear, relevant context beats large, noisy context.
2. **Spec before code.** Define rules, constraints, architecture, acceptance criteria, and expected output before any implementation.
3. **Docs are for *why*, code for *what*.** History lives in git. Comments justify non-obvious choices, never restate the line.
4. **Real examples beat generic instructions.** "Follow this existing file" lands harder than "follow best practices."
5. **Always know the canonical path.** If you deviate, do it deliberately — never by forgetting the happy path exists.
6. **Outcome before path.** Give the finish line — raw input plus exact expected output — and let the agent build the algorithm to connect them.
7. **Pin load-bearing architectural decisions.** The agent will invent what isn't specified. Lock architecture into `AGENTS.md`.
8. **A good prompt has a stop condition.** Say what to do, what not to do, and where to stop.
9. **Plan before execution.** For non-trivial work: explore, plan, review the plan, implement, verify.
10. **Format helps, but does not save bad thinking.** Markdown, XML, YAML, and JSON only reduce ambiguity. They don't replace clarity.
11. **The bottleneck is judgment, not generation.** Agents generate fast; the hard part is catching what's almost right but wrong.
12. **Review needs distance.** The context that produced a solution tends to defend it. Review with a fresh context — diff plus spec, no history.
13. **Automation needs rails.** Hooks, tests, lint, CI, sandboxing, and permissions matter more than advisory text the agent can forget.
14. **Autonomy requires observability.** If the agent makes decisions, log the trajectory: tool calls, intermediate outputs, failures.
15. **Staged spikes when the technique is uncertain.** When the *how* is unknown — a library choice, a CV technique, a multi-stage transformation — break the problem into staged spikes against golden fixtures with per-stage debug artifacts.
16. **Diagnose with discipline.** For hard bugs and performance regressions: build a fast, deterministic feedback loop *before* hypothesising. Reproduce, then generate three to five ranked falsifiable hypotheses, then change one variable at a time. The feedback loop is the skill; everything else is mechanical.
17. **TDD as deterministic guardrail.** When behavior is test-expressible up front: tracer-bullet test → minimum code → green → refactor. One test at a time; tests verify behavior through public interfaces, not implementation. Pairs with TDG inside the GREEN phase of any cycle where multiple implementation strategies are plausible.
18. **One task per session.** Reset rather than extend; reload only what the next task needs.
19. **Slice vertically, not horizontally.** Decompose a spec into thin end-to-end paths through every layer (schema, API, UI, tests) rather than one layer at a time. Each slice ships demonstrable behavior; horizontal layer-stacks ship nothing on their own.
20. **Discipline scales with project maturity.** Same principles bind every project; the artifact set scales. A spike runs posture + research + audit; a regulated product adds spec / ADR / hooks / evals. Add ceremony only where it changes agent behavior; configure at init and reconfigure as the project matures.
21. **Decide when grounded, ask when judgment.** The engineer is the boss, not the co-pilot. The agent is not being watched line by line; it is expected to bring decisions, not fork points. Grounded decisions land without a question — a canonical happy path with citations, a single-criterion winner among TDG approaches, a well-established industry pattern. Design/taste, product tradeoffs, irreversible or high-blast-radius actions, and genuinely close calls escalate with a recommendation plus why the alternatives are weaker.
22. **CI failure is a local gate gap.** Pre-push mirrors what CI runs — same commands, same matrix. If CI catches something pre-push did not, the fix is to close the gate locally, not to iterate red CI runs. Pushing red-CI diffs burns cloud minutes and normalizes broken main.

> Working with agents means trading typing for technical direction. The value is in giving the right context, setting boundaries, validating the result, and keeping "almost right" out of production.

## 1. Spec-Driven Design

Define the rules before the agent writes a line. The temptation is to dump everything into `AGENTS.md` and hope it works — but bloat causes the model to ignore the file. One topic per file.

There are two complementary frames for the artifacts the kit produces. The first is **purpose** — what each artifact is *for*. The second is **loading mechanism** — when each artifact reaches the agent's context.

### Six-layer artifact stack (purpose)

1. **Constitution** — `WORKFLOW.md` (universal engineering philosophy, kit-shipped), `AGENTS.md` (project-specific compressed rules read every session), and `GUIDELINES.md` (project-specific full engineering reference: Clean Architecture binding, SOLID application, Object Calisthenics tier, code standards, complexity discipline, API rules, performance standards, build system, static analysis, quality gates, testing strategy, git workflow, documentation, security). The trinity answers "how this project is built" at three compression levels — principles, distilled rules, full reference. `AGENTS.md` and `GUIDELINES.md` are project-owned and lazy; `WORKFLOW.md` is kit-shipped.
2. **Domain** — `CONTEXT.md` at the repo root (or `CONTEXT-MAP.md` plus per-context `CONTEXT.md` files for multi-context repos). The project's ubiquitous language: canonical nouns, the aliases to avoid, the relationships between them, and the ambiguities that have already been resolved. Direct application of Domain-Driven Design (Evans, 2003) — when an agent and a human share the project's vocabulary, the agent uses fewer tokens to say more, and the code, tests, and conversation all converge on the same names. Created lazily — first term resolved triggers the file.
3. **Product** — `doc/product/PRD.md` (single-product) or `doc/product/<slug>.md` plus `doc/product/PRODUCT-MAP.md` (multi-product). Product-level scope: target user, problem, goals, non-goals, success metrics, multi-feature roadmap, cross-feature constraints. One PRD per product; feature specs (Layer 4) inherit target user, success metrics, and constraints from the PRD. Created lazily when a product is being scoped.
4. **Spec** — `doc/specs/NNNN-<slug>.md`. Feature-level requirements: who the feature is for, what it must do, the measurable success criteria, the explicit non-goals. One spec per feature; multiple tasks implement one spec; specs reference their parent PRD for product-scope inheritance. Industry-aligned with [GitHub Spec Kit](https://github.com/github/spec-kit).
5. **Plan / Decisions** — `ARCHITECTURE.md` (system patterns and boundaries), `doc/adr/NNNN-*.md` (binding architectural decisions in Michael Nygard's pattern), `doc/tasks/NNNN-*.md` (per-work-unit plan with checkbox acceptance criteria). The *how* of building what the spec asked for. Layer 5 spans three document roles — `ARCHITECTURE.md` is definition, ADRs are decision-record, tasks are tracking — write each per its role, not as a single class.
6. **Code** — the implementation. Code is the primary documentation of behavior; comments justify non-obvious choices.

The six layers scale with project maturity (TL;DR #20 — Discipline scales). A spike or PoC profile may legitimately ship only Layers 1, 2, and 6 — adding Layers 3, 4, and 5 to a 200-line experiment is ceremony that does not change agent behavior. (Domain — Layer 2 — earns its keep even at PoC because vocabulary drift starts on day one.) A team or regulated product runs all six. The kit's profiles (`poc`, `solo`, `team`, `mature`) configure which layers auto-install per project and are changeable as the project matures; the principles in this document bind every profile, only the artifact set differs.

### New product inception order

A new product starts with tool activation, then product discovery. Tool activation means `agentic init`: install the skills and the minimum operating surface so the agent can follow the workflow. It does not mean `/ad-bootstrap` yet. `AGENTS.md` is the agent's operational guide; it should be generated after enough product context exists to avoid inventing architecture or project rules from a weak business brief.

The substantive order is:

1. **Domain and product discovery.** Clarify the target user, problem, constraints, canonical vocabulary, success metrics, and non-goals. When the idea is fuzzy, interview first; when terms are unstable, capture the domain language as it stabilizes.
2. **PRD.** Record product-level scope, metrics, constraints, and roadmap. This is the first product contract.
3. **Feature spec.** Narrow one product slice into behavior, acceptance criteria, and non-goals. The feature spec inherits target user, metrics, and constraints from the PRD.
4. **Technical plan and decisions.** Update architecture, ADRs, and tasks only for the constraints the spec actually creates.
5. **Code and gates.** Implement vertical slices, verify through tests and quality gates, then review with fresh context.

Durable repository rules belong after product framing when they would otherwise invent architecture from weak product context. The exception is a brownfield repo whose existing code already provides the product and architecture context; there, bootstrap is an audit of what is true, not a substitute for discovery.

### Three context types (loading mechanism)

- **Operational context is advisory.** `AGENTS.md` (or `CLAUDE.md` for Claude Code, which can mirror or import the same content via `@AGENTS.md`) tells the agent how to build, test, follow conventions, and where the security boundaries are. The agent reads it as a guide, not a contract. Open standard `AGENTS.md` is native in most agentic IDEs.
- **Canonical specs are constraints, not advice.** `DESIGN.md` (the visual contract — YAML tokens plus Markdown rationale, per Google Labs' open standard), `ARCHITECTURE.md`, ADRs in `doc/adr/*.md`, and feature specs in `doc/specs/*.md` are facts the agent must obey. If a token, pattern, or success criterion isn't declared here, it doesn't exist. The agent must never invent one.
- **On-demand context is `SKILL.md`.** Description loads at session start (the listing is capped at 1,536 characters per the spec) and body loads only when the skill is invoked. Use it for repeatable workflows or domain knowledge that shouldn't pay a token cost on every turn.

Three rules apply across all of the above:

- **Acceptance criteria must be measurable.** "Build a dashboard" fails. "Loads in under 2 seconds, shows 6 months of history, passes axe accessibility" succeeds.
- **Acceptance criteria must be durable, not procedural.** Describe the behavior and the interfaces — the contracts that survive a rename. Avoid file paths, line numbers, and "open file X and add line Y" wording in the criteria themselves; those rot the moment the implementation moves. Procedural execution steps belong in a separate section of the task file, not in the criteria.
- **Prune.** If removing a line wouldn't make the agent fail, cut it.

## 2. Docs vs. Code

Avoid putting implementation code in docs unless it's executable, generated, or a minimal API/contract surface. Docs define intent, constraints, contracts, and decisions; production logic lives in code.

The split is simple. **Docs are for the *why*** — decisions, not history. Git tracks history; docs explain the reasoning that won't survive otherwise. **Code is for the *what*** — clean naming and small units make logic self-evident, and the more your code does this work, the less your docs need to.

Comments are exceptions. They justify *why* a non-obvious choice was made — never *what* the line does. No commented-out code, and no orphan `TODO` or `FIXME`: every deferred item references a tracked work item — a GitHub Issue or a per-task file under `doc/tasks/NNNN-*.md`.

### Documentation Discipline

The rules below are canonical.

1. **Definitions and decisions only.** No speculation, history, or unfounded plans.
2. **No dates, version stamps, `DRAFT` markers, or changelogs in narrative documents.** Decision-record artifacts under `doc/adr/`, `doc/tasks/`, `doc/specs/`, `doc/product/` are exempt — their lifecycle fields are the auditability primitive.
3. **No emoji anywhere.**
4. **Business context first.**
5. **One scope per document. No duplication.**
6. **Code is the primary documentation of behavior.**
7. **No commented-out code; no orphan `TODO` / `FIXME` in source.** Every deferred item references a GitHub Issue or a `doc/tasks/NNNN-*.md` task.
8. **Tests are living documentation of behavior.**
9. **Single responsibility per document, named by layer.** Each document plays exactly one role — **definition** (pillar Layers 1, 2, 3 plus `ARCHITECTURE.md`; read-mostly after defined; no per-item tracking UI), **decision-record** (ADRs, Specs; single `Status:` field; mostly immutable after acceptance), or **tracking** (Tasks; full checkbox / append-only-Notes UI is their job). A document does not take on adjacent layers' responsibilities.
10. **Each layer owns its directory index. No duplication across docs.** `doc/adr/` is the canonical ADR index; `doc/tasks/`, `doc/specs/`, `doc/product/` likewise own their layers. Other documents do not list / digest / re-state these indices.
11. **Cross-references must be load-bearing.** If you can delete the reference and the surrounding statement still stands, the reference was decoration — drop it.
12. **Universal-vs-kit-state separation.** `WORKFLOW.md` ships to downstream projects and carries universal principles only — it does not cite kit-specific ADR numbers. The kit's adoption of each principle is recorded in `doc/adr/` (kit-internal). Literature citations remain (they are universal load-bearing references).

The twelve rules above are the authoritative Documentation Discipline contract. They counter recurring failure modes: session-load files bloated past relevance, README pages drifting into changelogs, decision artifacts diluted by speculation, definition documents accumulating per-item tracking UI, and pillar documents duplicating adjacent layers' indices.

## 3. Format by Evidence

Structure reduces ambiguity, but format isn't magic. Pick the right one for the surface:

- **Markdown** for repo files (`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, specs, ADRs). Readable, diffable, agent-friendly.
- **XML-style tags** inside prompts when boundaries matter: `<instructions>`, `<context>`, `<examples>`, `<input>`, `<constraints>`, `<output_format>`.
- **YAML** for metadata, frontmatter, and declarative config.
- **JSON or schema** for machine-validated output.

Use XML when the prompt mixes instructions, retrieved context, examples, user input, and expected output — the separation pays off when there's noise to fight. Skip it for simple prompts; if Markdown headings or plain text are clear enough, use them.

No format is universally best. XML separation pays off most for autonomous agents, where the prompt has to land alone without conversational refinement; interactive use (Claude Code, Codex) tolerates loose Markdown. Claude appears to respond well to XML, plausibly an artifact of training. Treat this as a working hypothesis worth testing on your own target model and task before standardizing.

**Host-aware structured prompts.** Hosts that expose structured-prompt primitives — Claude Code's `AskUserQuestion` (multi-choice cards) and Plan Mode (plan-approval cards) — reduce ambiguity at confirmation gates more reliably than inline text. Prefer the structured primitive when the host supports it; fall back to numbered text otherwise. Codex has no equivalent today; its skills stay on numbered text.

## 4–5. Research Before Implementation

Two sub-practices, joined into one indivisible pass: find the canonical baseline (Happy Path) and anchor it in project-specific examples (Ground in Real Patterns).

**Find the happy path.** Before implementing, ask: *"What is the canonical, idiomatic way to implement [X] in [stack]? Cite official docs. List common deviations and why people take them."* Mid-implementation: *"Are we still on the happy path? If we deviated, was it deliberate?"* Sometimes you can't follow the happy path — that's fine. Always know where it is and why you left it.

**Ground in real patterns.** Don't dump the codebase into context. Anchor the model in a specific, project-relevant example: *"Find an existing example of [similar feature]; use that exact structure."* Cite specific files, not "the codebase." Use just-in-time retrieval — pass paths or IDs and let the agent fetch via tools.

A research pass joining four sources — official docs, validated implementation references (public repos, Q&A forums, blog posts, gists), in-repo patterns, git history — by AND not OR, synthesizing the happy path with citations from each source, and gating any deviation behind an irrefutable justification before code is written, is the operational shape.

## 6. Explore → Plan → Implement → Commit

For non-trivial changes, four phases:

1. **Explore (read-only).** Plan mode in your agent. Read, build a mental model, no edits.
2. **Plan.** Agent writes a Markdown plan. You edit before approving. For non-trivial multi-step work, structure the plan as a per-task file (`doc/tasks/<NNNN>-<slug>.md`) with checkbox acceptance criteria and execution steps — the agent toggles checkboxes as it works rather than rewriting paragraphs, keeping edits cheap and resumable across sessions. When a spec yields more than one task, **slice vertically**: each task is a thin end-to-end path through every layer the change touches (schema, API, UI, tests), not one layer at a time. The anti-pattern is *horizontal slicing* — "first the schema task, then the API task, then the UI task" — because nothing is shippable until the last task lands. Tracer-bullet vertical slices each ship a demonstrable behavior on their own ([Hunt & Thomas, *Pragmatic Programmer*, 1999](https://en.wikipedia.org/wiki/The_Pragmatic_Programmer)). Tag each task **AFK** (specified completely enough that an autonomous agent can land it) or **HITL** (needs human judgment, taste, design review, or external access) — the dimension is orthogonal to the lifecycle status and tells parallel agents which work is theirs to take.
3. **Implement.** Execute the approved plan; verify each step before moving to the next.
4. **Commit.** One logical change per commit.

**Delegation with bounded context.** Delegate to a subagent only when the context packet can stand alone: goal, relevant sources, allowed tools and write scope, output contract, and stop criterion. Good delegation shapes are sidecar codebase research, versioned docs/API research, test design from a spec, bug reproduction with a feedback loop, a bounded worker on disjoint files, and fresh-context review. Keep product judgment, frequent back-and-forth, tightly coupled implementation, taste/design calls, and the immediate blocking step in the main session. In task files, **AFK** marks candidate work for explicit agent delegation; **HITL** marks work that needs human or main-session judgment. Use `/ad-handoff` when the packet is larger than one clean chat turn.

Skip this for diffs you can describe in one sentence.

## 7. Action Commands With Stop Criteria

Leave no room for interpretation. Tell the model where to stop.

- **Avoid:** *"Here is the data. What do you think?"*
- **Prefer:** *"Analyze this data. List the top 3 bottlenecks. Stop there — don't propose fixes unless I ask."*

The stop criterion is as important as the action. Without it, the agent generalizes outward and you end up trimming output you didn't ask for.

### Decide when grounded, ask when judgment

Stop criteria bound *what to do*; this subsection bounds *whether to ask*. The engineer running the agent is not reading every file, doc, or diff the agent read to get to its recommendation. Treat the relationship as employee-to-boss, not co-pilot-to-pilot: the agent brings decisions with a recommendation, and only escalates when the choice requires human judgment.

Default is decide, not ask:

- **Grounded happy path.** `/ad-ground` returned a canonical path with citations across all four sources — take it. Do not ask.
- **Single-criterion winner (§9 TDG).** Three approaches, one wins by the picked criterion (readability *or* performance *or* testability). Pick it. Do not survey.
- **Well-established industry pattern.** The canonical library, the standard shape, the statistically dominant approach in the stack. Take it. Do not ask.
- **Deterministic outcome.** Type-check passes, tests pass, gate scripts pass. State the result. Do not ask if it should be taken as done.

Ask only when:

- **Design or taste.** UX shape, product tradeoff, naming that carries brand — outputs a human has to look at and form an opinion about.
- **Irreversible or high blast radius.** Destructive git ops, shared-state mutations, published artifacts, force-pushes. Match the confirmation to the blast radius of the action, not to the size of the diff.
- **Genuinely close calls.** Two options tied on the picked criterion; the tie-break is a preference the agent cannot ground.
- **Fuzzy spec.** The ask itself is under-specified — route to `/ad-grill`, not a raw open question.

Shape of the ask when it is warranted: one question, recommended answer first, why the alternatives are weaker. Not a survey of every option the agent considered; that pushes the synthesis work back onto the boss.

## 8. Architectural Boundaries

Lock the load-bearing decisions into `AGENTS.md` or `CLAUDE.md` so the agent doesn't relitigate them every session:

> "Apply: **Clean Architecture** — isolate core logic from frameworks. **Small units** — single-responsibility, low indentation, no `else` chains. **Modular and testable** — no over-engineering."

The agent will follow what's specified and invent what isn't. Prefer specifying.

### Architectural vocabulary

Architectural drift accelerates with the agent's typing speed; the counter is shared vocabulary that names the shapes that matter. The canonical terms come from John Ousterhout's *A Philosophy of Software Design* (2018) and Michael Feathers's *Working Effectively with Legacy Code* (2004).

- **Module** — anything with an interface and an implementation; deliberately scale-agnostic (function, class, package, vertical slice).
- **Interface** — everything a caller must know to use the module correctly: types, invariants, ordering constraints, error modes, configuration, performance characteristics. *Not* just the type signature.
- **Implementation** — what's inside the module.
- **Depth** — leverage at the interface. A module is **deep** when a large amount of behavior sits behind a small interface; **shallow** when the interface is nearly as complex as the implementation. Depth is a property of the interface, not of line counts (rejected framing: depth-as-implementation-to-interface line ratio rewards padding).
- **Seam** (Feathers) — a place where behavior can be altered without editing in place; the *location* of an interface. Distinct from DDD's *bounded context*; the kit avoids "boundary" for this reason.
- **Adapter** — a concrete thing that satisfies an interface at a seam; a role, not a substance.
- **Leverage** — what callers get from depth: more capability per unit of interface they have to learn.
- **Locality** — what maintainers get from depth: change, bugs, knowledge concentrated at one place rather than spread across callers.

Three principles fall out of those terms:

- **Deletion test.** Imagine deleting the module. If complexity vanishes, the module was a pass-through (delete it). If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the interface, the module is probably the wrong shape.
- **One adapter is a hypothetical seam; two adapters make it real.** Don't introduce a seam unless something actually varies across it.

Architectural skills should use these terms verbatim, so suggestions and reviews land in a single language.

## 9. Outcome-Based Prompting (TDG)

Give the finish line first, not the path:

1. **Ground truth.** Raw input plus exact expected output.
2. **Command the implementation.** The algorithm that connects the two.
3. **Iterate by criterion.** Ask for three approaches; pick by *one* explicit criterion (readability, performance, *or* testability — not all three at once).
4. **Test Dependency Map as pre-flight.** Before any change, tell the agent *which* tests cover the file. *"Before modifying X.ts, list which tests cover it. Run. Modify. Run. If none cover it, write one first."* TDM is orthogonal to the implementation regime: it pairs with TDG (this section) when the implementation strategy is the uncertain axis, and with TDD (§16) when the behavior is test-expressible up front. TDM rejects cargo-cult test-first ceremony, not test-first development itself.

## 10. Reviewer With Fresh Context

The agent that wrote the code is biased about it. The same reasoning that produced the solution defends the solution.

> *"Open a fresh agent with no history. Give it only the diff and the spec. Review as a strict Senior reviewing a Junior PR. Be ruthless about bugs, coupling, edge cases."*

In Claude Code, this means a subagent (the `Task` tool, or a custom `.claude/agents/*.md` file). In Codex, use an explicit subagent workflow with a custom `.codex/agents/*.toml` file and a handoff/audit file as the bounded input. Without subagent infrastructure: fresh context, paste diff plus spec, and keep the review separate from the authoring session.

## 11. Quality Gates: Determinism Over Persuasion

`AGENTS.md` is advisory. Hooks and CI are deterministic. The difference matters: text you write hoping the agent obeys is not the same as a script that exits non-zero when a rule is violated.

- **Hooks for inviolable rules** (formatter, secret-scan, lint). Not text the agent might forget.
- **Pre-commit fast** (lint, format, secrets); **pre-push thorough** (build, unit tests, integration tests). Slow pre-commits push devs to `--no-verify`.
- **Visual or E2E for UI.** Type-check confirms the code compiles, not that the feature works. Open the browser (Claude in Chrome, DevTools MCP).
- **Sandboxing plus scoped permissions** for autonomy: allowlists, OS sandbox, classifier-reviewed auto mode. The bigger the autonomy, the more rails you need.
- **Never bypass.** No `--no-verify`. Failing tests means not ready.
- **CI failure is a local gate gap.** Pre-push must mirror what CI runs — same commands (`test`, `lint`, `typecheck`, `build`) and, when they matter for the failure surface, the same matrix (language versions, OS targets, feature flags). If CI catches something pre-push did not, the deterministic fix is to close the gate locally and re-push, not to iterate red CI runs. Skills that open pull requests verify local gates green as part of preflight; skills that scaffold hooks read the CI config and warn on drift between the two.

## 12. The Bottleneck Is Discrimination, Not Generation

Modern agents handle most routine implementation. The work has shifted to catching what they got wrong.

Industry data underlines the wall. Recent JetBrains and Stack Overflow developer surveys show a majority frustration with "AI solutions that are almost right, but not quite," and a near-majority report that debugging AI-generated code costs more time than writing it from scratch. See Sources for the surveys.

The takeaway: §10 (Reviewer) and §11 (Quality Gates) are not optional. Skipping them is where bug density grows.

Per the Steve Rogers framing in the preamble: the serum cannot manufacture discrimination — it amplifies whatever discrimination the engineer already brings. The kit's job is to encode discrimination into the agent's context (specs, ADRs, fresh-context reviews, deterministic gates) so the amplification compounds in the disciplined direction even when the engineer is sleepy, rushed, or handing off to another collaborator.

**Two roles of judgment, not one.** Agent review (§10 fresh-context) and the deterministic gates (§11) catch the *mechanical* failures: bugs, coupling, edge cases, broken contracts, missed branches. They do not — and should not be expected to — catch what is left after that: taste, product judgment, visual feel, whether the feature actually solves the user's problem. Those require a human to look at the running thing and form an opinion. Skipping fresh-context review because "the engineer will catch it" wastes engineer attention on mechanical failures the agent should have caught. Skipping the human pass because "the agent reviewed it" ships features that compile, pass, and feel wrong. The two are complements, not substitutes.

## 13. Evals for Anything Autonomous

If your agent is making decisions on its own, you need evals. A few principles:

- **Trajectory beats final output.** Output-only eval hides failures in tool calls, retrieval, and intermediate decisions that the final answer can mask. Log tool calls and intermediate states.
- **Observability before evals.** Get traces first; build the eval suite on top.
- **LLM-as-judge for breadth, humans for depth.**
- **The unit under test is prompt + scaffold + model.** Changing any of the three is a release.

## 14. Staged Spikes With Golden Fixtures

Sometimes the spec is clear but the *technique* is uncertain — you don't know which library, which CV approach, which decomposition. Don't ask the agent to solve it end-to-end. Break the problem into staged spikes and validate each one against curated ground truth.

**Spike vs. prototype.** Use a *spike* (this section) when the unknown is *how* — the technique itself is uncertain across multiple plausible approaches and validation needs golden fixtures with per-stage debug. Use a *prototype* when the unknown is *what should this feel like* — UI/UX direction, the shape of an interaction, whether a state model holds up under play. Different question, different artifact, different success criterion.

The flow has four parts:

1. **Discovery first.** Ask the agent to list canonical approaches grounded in official docs and real examples. Pick one by an explicit criterion. The output of this step is information, not code.
2. **Golden fixture.** Curate inputs with rich expected outputs. For computer vision, that means bounding boxes, sizes, lighting, difficulty tags, edge cases — not just "three circles." Keep the fixture as JSON keyed by input path.
3. **Pipeline with gates.** One technique per stage; each gate emits a debug artifact: an image to `debug/01-preprocess/`, intermediate JSON, a log row — whatever makes the stage's output inspectable.
4. **Two layers of evaluation.** End-to-end against the fixture, *and* per-stage debug to locate where things diverged when it failed.

**Why this beats end-to-end:** §9 (TDG) assumes the path is known. When you don't know it, end-to-end evaluation tells you *that* it failed, not *where*. Stage-level artifacts make the divergence inspectable, so you fix the right gate instead of guessing at the final output.

**When to use it:** the unknown is *how* — a library choice, a CV technique, a multi-stage transformation. Skip it when the *how* is routine.

## 15. Diagnose With Discipline

For hard bugs and performance regressions, the failure mode is jumping to hypotheses before there is a way to check them. The discipline below is the counter, grounded in standard debugging practice (Kernighan & Pike, *The Practice of Programming*).

### Phase 1 — Build a feedback loop

This is *the* skill. Everything else is mechanical. A fast, deterministic, agent-runnable pass/fail signal for the bug is what makes bisection, hypothesis-testing, and instrumentation effective; without one, no amount of staring at code converges. Spend disproportionate effort here.

Loop-construction techniques, in roughly increasing cost:

1. Failing test at whatever seam reaches the bug — unit, integration, e2e.
2. Curl / HTTP script against a running dev server.
3. CLI invocation with a fixture input, diffing stdout against a known-good snapshot.
4. Headless browser script (Playwright / Puppeteer) — drives the UI, asserts on DOM, console, network.
5. Replay a captured trace — saved network request, payload, event log — through the code path in isolation.
6. Throwaway harness — a minimal subset of the system that exercises the bug code path with one function call.
7. Property / fuzz loop — when the bug is "sometimes wrong output", run many random inputs and look for the failure mode.
8. Bisection harness — automate "boot at state X, check, repeat" so `git bisect run` works.
9. Differential loop — run the same input through two versions or two configs and diff outputs.
10. HITL bash script — last resort. Structure the human's clicks so the loop is still repeatable.

Treat the loop as a product: faster, sharper signal, more deterministic, every iteration. A two-second deterministic loop is a debugging superpower; a thirty-second flaky loop is barely better than no loop.

For non-deterministic bugs, the goal is not a clean repro but a *higher reproduction rate* — loop the trigger, parallelize, narrow timing windows, inject sleeps. A 50%-flake is debuggable; 1% is not.

If a loop genuinely cannot be built, stop and say so — do not proceed to hypotheses.

### Phase 2 — Reproduce

Run the loop. Confirm the failure matches the user's description (not a different failure that happens to be nearby), reproduces consistently (or at a high enough rate), and the exact symptom is captured for later phases to verify the fix against. Wrong bug = wrong fix.

### Phase 3 — Hypothesise

Generate **three to five ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes — *"if X is the cause, then changing Y will make the bug disappear / changing Z will make it worse."* If you cannot state the prediction, the hypothesis is a vibe; sharpen it or discard it.

Show the ranked list to the user before testing. Domain knowledge often re-ranks instantly ("we just deployed a change to #3"), or marks hypotheses already ruled out — a cheap checkpoint, big time saver.

### Phase 4 — Instrument

Each probe maps to a specific prediction from Phase 3. Change one variable at a time. Log enough that the result is unambiguous — a single instrument that confirms two predictions at once tends to confirm whichever one you were rooting for.

### Phase 5 — Fix and regression-test

Apply the fix. Re-run the Phase-1 loop and confirm the captured symptom is gone. Promote the loop's check into a permanent test that lives next to the code so the same failure mode cannot return silently.

## 16. Test-Driven Development (TDD)

TDG (§9) gives the agent the finish line and asks it to find the path. TDD asks the agent to express one behavior as a test, drive the minimum implementation that makes the test pass, then deepen. The two are distinct LLM disciplines; the Test Dependency Map (§9, item 4) is a pre-flight that pairs with either.

TDD is the cleanest **deterministic guardrail** when the change has a clear behavior to express up front: a failing test is unambiguous, so the "almost right but not quite" failure mode (§12) cannot ship silently. **Good tests read like a specification** — *"user can checkout with a valid cart"* tells you the capability exists. **Bad tests couple to implementation** — mock internal collaborators, assert on private state, or query the database directly when the public interface is what the caller uses. A test that breaks on a rename but not on a behavior change was testing implementation, not behavior.

### Phase 1 — Plan vertically

Before writing a test or code:

1. Read `CONTEXT.md` so test names and interface vocabulary land in the project's ubiquitous language.
2. Confirm the public interface — what does the caller need to know? Types, ordering, error modes. Interface design *is* testability design.
3. Identify deepening opportunities (Layer 2 vocabulary per §8): small interface, deep implementation.
4. List the behaviors to test, not the implementation steps. Pick the **first** behavior — the one that proves end-to-end the path works. The rest defer until the tracer bullet lands.
5. Establish the green baseline. For existing code, list the tests already covering the surface (TDM, §9.4) and run them. For new code, write the first test fresh.
6. Get the user's approval on the plan in one sentence before any test or code is written.

### Phase 2 — Tracer bullet

Write ONE test that confirms ONE behavior through the public interface. `RED → GREEN → end-to-end path proven`. The fail-reason matters: a test failing because the function is undefined is not the same as a test failing because the assertion is wrong; only the latter proves the test verifies behavior rather than the existence of a symbol.

Do not write a second test until this one is green.

### Phase 3 — Incremental loop

For each remaining behavior: `RED → minimum code → GREEN`. Three rules:

- **One test at a time.** Bulk-writing all tests first then all implementation is *horizontal slicing* — the named anti-pattern. Bulk-written tests verify *imagined* behavior, not actual behavior; the suite becomes insensitive to real changes and you outrun your headlights, committing to test structure before understanding the implementation.
- **Only enough code to pass the current test.** Anticipating the next test bloats the implementation and couples it to assumptions not yet verified.
- **Tests verify behavior through public interfaces.** No private-method tests, no internal-collaborator mocks, no direct database/file-system assertions when the public interface is what the caller uses. A test that breaks on a rename but not on a behavior change was testing implementation, not behavior.

### Phase 4 — Refactor

Once all planned tests pass: extract duplication, deepen modules (move complexity behind smaller interfaces), apply SOLID where natural. Run tests after each refactor step. **Never refactor while RED** — get to green first, then refactor with the green baseline as the safety net.

The refactor phase is where deepening (§8) happens. Treat tests as a fixed contract; the implementation is free to change shape as long as the contract holds.

### TDD vs TDG — when to use which

- **TDD** — behavior is known and test-expressible up front. The test is the contract; implementation follows.
- **TDG** — behavior may not yet be testable as a single pair, but the outcome is known. Three candidate implementations + one criterion picks the path.

When both apply (test-expressible AND multiple implementation strategies are plausible), use TDD as the outer loop and TDG inside the GREEN phase to select the strategy for that cycle.

---

These are starting points. Prune what doesn't fit your codebase.

## Provenance

This guide is operational practice, not theory. Most principles come from years of shipping production code, with and without LLMs; some were in use before the industry converged on labels for them, and once a label landed the kit adopted it to make the conversation easier.

§14 (Staged Spikes With Golden Fixtures) is the author's own working technique — each component (spike, golden dataset, stage-segmented error analysis, trajectory evaluation, visual CV debugging) has its own lineage in the literature under Sources; the combination — discovery → fixture → staged pipeline with debug artifacts → two-layer evaluation — is original to this kit.

A cross-pollination pass against [Matt Pocock's `mattpocock/skills`](https://github.com/mattpocock/skills) — a separate body of agent-engineering practice grounded in the same canonical literature (DDD, *Pragmatic Programmer*, Ousterhout, Feathers, Beck) — surfaced principles that earned their place on independent merits: the **Domain layer** (§1 Layer 2), the **architectural vocabulary** (§8), **Diagnose with discipline** (§15), **vertical slicing** and **HITL/AFK tagging** (§6), and **AI mechanical / human judgment** (§12). Where Pocock's framing sharpened our own, the borrowed phrasing is acknowledged inline; everything else stays kit-original.

External claims (specific percentages, named frameworks) are cited under Sources. Everything else is operational guidance from practice or synthesis across that material — a working model, refined over time, not academic claim.

## Sources

**§1 — Spec-Driven Design**
- DESIGN.md spec (Google Labs): https://github.com/google-labs-code/design.md
- SKILL.md spec (Anthropic): https://code.claude.com/docs/en/skills
- Domain-Driven Design (Evans, 2003) — *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Source for the Domain layer (`CONTEXT.md`) and the ubiquitous-language discipline.

**§6 — Explore → Plan → Implement → Commit**
- *The Pragmatic Programmer* (Hunt & Thomas, 1999), tracer-bullet metaphor — source for the vertical-slicing principle.
- Claude Code subagents: https://code.claude.com/docs/en/sub-agents — source for fresh-context, scoped-tool delegation in Claude Code.
- Codex subagents: https://developers.openai.com/codex/subagents — source for explicit Codex subagent workflows and `.codex/agents/*.toml` custom agents.

**§8 — Architectural Boundaries**
- *A Philosophy of Software Design* (Ousterhout, 2018) — Module / Interface / Depth vocabulary; rejected framing of depth-as-line-ratio.
- *Working Effectively with Legacy Code* (Feathers, 2004) — Seam vocabulary.

**§12 — The Bottleneck Is Discrimination, Not Generation**
- JetBrains *DevEcosystem 2025*: https://devecosystem-2025.jetbrains.com/artificial-intelligence
- Stack Overflow *2025 Developer Survey* (AI section): https://survey.stackoverflow.co/2025/ai

**§14 — Staged Spikes With Golden Fixtures**
- Spike (XP) — Wikipedia: https://en.wikipedia.org/wiki/Spike_(software_development)
- Golden datasets — Arize: https://arize.com/resource/golden-dataset/
- Stage-segmented error analysis — Hamel Husain's evals FAQ: https://hamel.dev/blog/posts/evals-faq/
- Trajectory evaluation — LangSmith docs: https://docs.langchain.com/langsmith/trajectory-evals
- Visual CV debugging — OpenCV cvv tutorial: https://docs.opencv.org/3.4/d7/dcf/tutorial_cvv_introduction.html

**§15 — Diagnose With Discipline**
- *The Practice of Programming* (Kernighan & Pike, 1999) — chapters on debugging and testing.
- Falsifiability framing — Karl Popper, *The Logic of Scientific Discovery* (1959).

**§16 — Test-Driven Development (TDD)**
- *Test-Driven Development: By Example* (Kent Beck, 2002) — canonical red-green-refactor framing.
- *Working Effectively with Legacy Code* (Feathers, 2004) — seams as test surfaces.
- *Unit Testing Principles, Practices, and Patterns* (Khorikov, 2020) — behavior-vs-implementation test classification.
- [`mattpocock/skills` engineering/tdd](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/SKILL.md) — vertical-tracer-bullet framing adopted with attribution.
