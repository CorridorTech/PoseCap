---
name: ad-tdd
description: Test-Driven Development per WORKFLOW.md §16 — red-green-refactor as deterministic LLM guardrail. Five phases — confirm regime, plan vertically, tracer bullet (one test → red → minimum code → green), incremental loop, refactor while green. Tests verify behavior through public interfaces; horizontal slicing (bulk-write tests then bulk-write code) is rejected as the named anti-pattern. Triggers on "TDD", "test-driven", "red-green-refactor", "test first", "write a failing test", "tracer bullet", "behavior not implementation", "vertical slice tests", "/ad-tdd". Distinct from `ad-tdg` (outcome-based prompting — pick implementation strategy when technique is known); routes to `ad-tdg` for strategy selection inside the GREEN phase, `ad-spike` for technique uncertainty, `ad-diagnose` for debugging. No file written; output is the verified implementation that lands through normal commits.
summary: Test-Driven Development per WORKFLOW §16. Red-green-refactor as deterministic LLM guardrail. Five phases — confirm regime, plan, tracer bullet, incremental loop, refactor. Tests verify behavior through public interfaces. Horizontal slicing rejected.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# /ad-tdd

Implements WORKFLOW.md §16. Process scaffold for the implementation phase when the change's behavior is known and expressible as a test up front. No file written — output is the verified implementation that lands through normal commits.

TDD is a deterministic LLM guardrail: a failing test is unambiguous, so "almost right" (the WORKFLOW §12 failure mode) cannot slip past. The skill keeps the agent inside red-green-refactor and blocks the named anti-pattern (horizontal slicing).

**Good tests read like a specification.** *"User can checkout with a valid cart"* tells you exactly what capability exists. **Bad tests couple to implementation** — mock internal collaborators, assert on private state, test the *shape* of things (data structures, function signatures) rather than user-facing behavior. A test that breaks on a rename but not on a behavior change was testing implementation, not behavior.

## Step 0 — Confirm regime

TDD is for the *behavior-known, test-expressible* regime. Run the skill when:

- The change has a clear behavior to express as a test (a new API capability, a bug-driven regression test, a refactor with a known contract), AND
- A test runner is wired (the project can execute one test in seconds, not minutes).

Route elsewhere when:

- The outcome (ground-truth pair) is known but the *implementation strategy* between input and output has multiple plausible paths → `/ad-tdg` (WORKFLOW §9). TDD focuses on driving code through one test at a time; TDG picks between three implementation candidates against one ground-truth pair.
- The *technique itself* is uncertain across multiple plausible approaches → `/ad-spike` (WORKFLOW §14).
- The task is bug investigation, not behavior implementation → `/ad-diagnose` (WORKFLOW §15).
- No test runner is wired and the project does not yet have a green baseline → `/ad-hooks` first to scaffold deterministic gates per WORKFLOW §11. TDD depends on a fast green/red signal.

When both TDD and TDG apply (behavior is test-expressible AND multiple implementation strategies are plausible), use TDD as the outer loop and invoke `/ad-tdg` inside the GREEN phase to pick the implementation strategy for that test cycle.

## Step 1 — Plan vertically

Before writing a test or a line of code:

1. **Read `CONTEXT.md`** if it exists — anchor the test names and interface vocabulary in the project's ubiquitous language. Tests that use canonical nouns survive renames; tests that paraphrase break.
2. **Confirm the public interface.** What is the smallest surface the caller needs to know? Types, ordering constraints, error modes. Interface design is testability design.
3. **Identify deepening opportunities** (small interface over deep implementation per WORKFLOW §8). Surface-area-light interfaces are easier to test against and survive refactors.
4. **List the behaviors to test, not the implementation steps.** Pick the **first** behavior — the one that proves end-to-end the path works. The rest are deferred until the tracer bullet lands.
5. **Test Dependency Map (TDM) for existing code.** If the change modifies existing code, list the tests already covering the surface and run them to establish the green baseline. New-code changes skip the existing-tests TDM and write the first test fresh.
6. **Get user approval on the plan.** One sentence — "I'll test behavior X first via interface Y, then iterate." User confirms or steers before any test is written.

You cannot test everything. Confirm with the user which behaviors matter most; focus on critical paths and complex logic.

## Step 2 — Tracer bullet

Write ONE test that confirms ONE behavior through the public interface. Then:

```
RED:   Write the test → run it → confirm it fails for the expected reason.
GREEN: Write the minimum code that makes the test pass → run → confirm green.
```

The test fail-reason matters. A test that fails because the function is undefined is different from a test that fails because the assertion is wrong — only the latter proves the test is verifying behavior, not just the existence of a symbol.

The tracer bullet is the end-to-end proof that the path works. Do not write a second test until this one is green.

## Step 3 — Incremental loop

For each remaining behavior:

```
RED:   Write the next test → run → fail.
GREEN: Add minimum code to pass → run → green.
```

Rules:

- **One test at a time.** The horizontal-slicing anti-pattern (write all tests, then write all code) is rejected. Bulk-written tests verify *imagined* behavior, not actual behavior; the suite becomes insensitive to real changes and the agent *outruns its headlights*, committing to test structure before understanding the implementation.
- **Only enough code to pass the current test.** Anticipating the next test bloats the implementation and couples it to assumptions not yet verified.
- **Tests verify behavior through public interfaces.** No private-method tests, no internal-collaborator mocks, no direct database/file-system assertions when the public interface is what the caller uses. If a test would couple to implementation, surface it and prompt the user — either rewrite to the public surface or accept the coupling explicitly with rationale in the task notes.
- **Keep the test name behavior-shaped.** *"user can sign in with valid credentials"* — yes. *"calls authenticate() with username arg"* — no.

## Step 4 — Refactor

Once all planned tests pass:

- [ ] Extract duplication (DRY) — when two tests duplicate setup or two code paths duplicate logic.
- [ ] **Deepen** — move complexity behind a smaller interface (WORKFLOW §8 vocabulary). The deletion test applies: a module whose interface is nearly as complex as its implementation is shallow; refactor toward depth.
- [ ] Apply SOLID where natural; never force-fit a pattern.
- [ ] Consider what the new code reveals about the existing code — opportunities to deepen pre-existing shallow modules surface during TDD because the new tests pin behavior the old code was implicitly relying on.
- [ ] Run tests after **each** refactor step. Never refactor while RED — get to GREEN first, then refactor with the green baseline as the safety net.

The refactor phase is where deepening happens. Treat the tests as a fixed contract; the implementation is free to change shape as long as the contract holds.

## Per-cycle checklist

Before moving to the next behavior:

- [ ] Test describes behavior, not implementation.
- [ ] Test uses public interface only.
- [ ] Test would survive an internal rename or method-signature shuffle that does not change observed behavior.
- [ ] Code is minimal for this test — no speculative features added.
- [ ] Green baseline holds.

If any checkbox fails, fix it before writing the next test. The cycle's contract is what makes TDD work.

## Output contract

No file written. Output is structured conversation:

1. Confirmation of regime (Step 0 — TDD, or routed elsewhere).
2. Vertical plan (Step 1) — interface, behaviors-to-test list, first behavior, approval.
3. Tracer bullet (Step 2) — test, red, minimum code, green.
4. Per-behavior incremental loop (Step 3).
5. Refactor pass with rationale (Step 4).
6. Per-cycle checklist confirmation.

When the change is committed, the behaviors covered, the deepening that surfaced, and the rejected couplings (if any) go into the commit message body. When a task file exists, the same content lands in the task's `Notes` log under a dated entry.

## Next

- After Step 4 refactor passes: commit the change. Each commit lands one or a small handful of behavior-shaped tests with their implementation; commits stay atomic.
- `/ad-review main..HEAD` (or current scope) before merge — WORKFLOW §10. TDD verifies the implementation against tested behaviors; §10 review checks coupling, edge cases, spec drift the tests did not cover.
- If the cycle surfaced a refactor opportunity larger than the GREEN-phase refactor allows: `/ad-deepen` (WORKFLOW §8; `team` / `mature` profiles only).
- If multiple tests fail in unexpected ways during the cycle (not the predicted RED for the new test): `/ad-diagnose` to investigate the regression before continuing the TDD loop.
- If the work spans multiple sessions: `/ad-task` for explicit decomposition; cite this TDD run in the task `Notes`.
